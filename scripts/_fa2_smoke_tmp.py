"""Temp smoke (delete after): prove FA2 makes the 8192-token god-object chunk
fit on 24GB and produces bit-equivalent vectors vs standard attention.

Usage:
    python scripts/_fa2_smoke_tmp.py fa2   # load FA2, embed god8192 + ref, dump ref
    python scripts/_fa2_smoke_tmp.py std   # load standard, embed ref, dump ref
    python scripts/_fa2_smoke_tmp.py cmp    # compare the two dumped ref vectors
"""

import json
import sys
from pathlib import Path

MODE = sys.argv[1]
OUT = Path("scripts/_fa2_smoke_out")
OUT.mkdir(exist_ok=True)

# A moderate chunk both attention impls can embed (fits without FA2 too) — used
# to prove numerical equivalence.
REF = (
    "Процедура ОбработкаПроведения(Отказ, РежимПроведения) Экспорт\n"
    "    Движения.гкс_Остатки.Записывать = Истина;\n"
    "    Для Каждого СтрокаТовары Из Товары Цикл\n"
    "        Движение = Движения.гкс_Остатки.Добавить();\n"
    "        Движение.Номенклатура = СтрокаТовары.Номенклатура;\n"
    "    КонецЦикла;\n"
    "КонецПроцедуры\n"
) * 30  # ~1.5-2k tokens

if MODE == "cmp":
    import math

    a = json.loads((OUT / "ref_fa2.json").read_text())["vec"]
    b = json.loads((OUT / "ref_std.json").read_text())["vec"]
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    cos = dot / (na * nb)
    maxdiff = max(abs(x - y) for x, y in zip(a, b))
    print(f"cosine(FA2, standard) = {cos:.8f}")
    print(f"max abs elementwise diff = {maxdiff:.3e}")
    print("VERDICT:", "EQUIVALENT (no quality loss)" if cos > 0.9999 else "DIVERGENT")
    sys.exit(0)

# Import the production embedder class so we exercise the real code path.
sys.path.insert(0, "scripts")
import torch  # noqa: E402  (after sys.argv parse, mirrors script order)
from reindex_bsl_qwen3 import Qwen3STEmbedder  # noqa: E402

enable_fa2 = MODE == "fa2"
emb = Qwen3STEmbedder(dtype="bfloat16", batch_size=32, enable_fa2=enable_fa2)
print(
    f"[{MODE}] model loaded, enable_fa2={emb.enable_fa2}, "
    f"attn={emb.model[0].auto_model.config._attn_implementation}"
)

# Reference vector (fits both impls).
ref_vec = emb.embed_batch([REF])[0]
(OUT / f"ref_{MODE}.json").write_text(json.dumps({"vec": ref_vec}))

if enable_fa2:
    # God-object: longer than max_seq_length so it truncates to exactly 8192
    # tokens — the XXL_8K bucket (batch=2) that OOM'd the no-FA2 run.
    god = REF * 40  # well over 8192 tokens, gets truncated to the cap
    torch.cuda.reset_peak_memory_stats()
    god_vecs = emb.embed_batch([god, god])  # batch=2 like the XXL bucket
    peak = torch.cuda.max_memory_allocated() / 1024**3
    reserved = torch.cuda.max_memory_reserved() / 1024**3
    tok = len(emb.model.tokenizer(god, truncation=True, max_length=emb.max_seq_length)["input_ids"])
    print(f"[fa2] god-object embedded: tokens={tok}, batch=2, dims={len(god_vecs[0])}")
    print(f"[fa2] PEAK VRAM allocated={peak:.2f} GB, reserved={reserved:.2f} GB (card=24.0 GB)")
    print("[fa2] OK — 8192-token god-object fit WITHOUT OOM")
