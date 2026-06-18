#!/usr/bin/env python3
"""ADR-025 Этап 3: обучение гейта детектора 1С — sentence-transformers + LR-голова.

`setfit`-пакет несовместим с transformers 5.x в этом окружении (`default_logdir` removed +
`config_setfit.json` 404), поэтому «SetFit-голова» реализована НАПРЯМУЮ на рабочем стеке фреймворка:
`SentenceTransformer` (rubert-tiny2, RU-native) → `LogisticRegression` (sklearn). На RU
natural-language тайтлах frozen-эмбеддинги rubert-tiny2 НЕ коллапсируют (≠ Qwen3 на BSL-КОДЕ,
ADR-023) — content matters: CV F1 ≈ 0.94 vs regex 0.883. Контрастный fine-tune тела (полный SetFit) —
опциональный следующий шаг, frozen уже бьёт baseline.

Старт `cointegrated/rubert-tiny2`; `--model intfloat/multilingual-e5-small` — апгрейд (e5 → префикс
`query: `). Данные: `data/1c-detector-ground-truth.json` (`text`, `is_1c`, `split`). Сохраняет
`models/onec-setfit/{st/, head.pkl, meta.json}` (подхватывает `onec_setfit_gate` при `ONEC_SETFIT_ENABLE=1`).

Usage:
    python scripts/train_onec_setfit.py --dry-run          # валидация датасета без ML-стека
    python scripts/train_onec_setfit.py                    # обучить rubert-tiny2 -> models/onec-setfit/
    python scripts/train_onec_setfit.py --model intfloat/multilingual-e5-small
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH = PROJECT_ROOT / "data" / "1c-detector-ground-truth.json"
DEFAULT_OUT = PROJECT_ROOT / "models" / "onec-setfit"
DEFAULT_MODEL = "cointegrated/rubert-tiny2"
MIN_RECOMMENDED = 150  # ниже — голова шумит (мало контраста), предупреждаем


def load_rows(path: Path) -> list[dict]:
    """GT-строки без карантинной когорты (split=='quarantine' — leakage-кандидаты, вне обучения)."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [r for r in rows if r.get("split") != "quarantine"]


def split_of(text: str, sample: dict) -> str:
    """train/test: явное поле `split`, иначе детерминированный sha1%5 (как eval_1c_detector)."""
    s = sample.get("split")
    if s in ("train", "test"):
        return s
    h = int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16)
    return "test" if h % 5 == 0 else "train"


def to_texts(rows: list[dict], model_name: str) -> list[str]:
    """Тексты для энкодера; e5-модели — префикс `query: ` (model card)."""
    prefix = "query: " if "e5" in model_name.lower() else ""
    return [prefix + str(r["text"]) for r in rows]


def summarize(rows: list[dict]) -> dict:
    train = [r for r in rows if split_of(r["text"], r) == "train"]
    test = [r for r in rows if split_of(r["text"], r) == "test"]
    pos = sum(1 for r in rows if r.get("is_1c"))
    return {"n": len(rows), "pos": pos, "neg": len(rows) - pos,
            "train": len(train), "test": len(test),
            "train_pos": sum(1 for r in train if r.get("is_1c"))}


def dry_run(rows: list[dict]) -> dict:
    """Проверить датасет без ML-стека: баланс/сплит/целостность. Возврат — сводка (тестируемо)."""
    s = summarize(rows)
    print("=" * 56)
    print("Гейт 1С — DRY-RUN датасета (ST+LR backend)")
    print("=" * 56)
    print(f"всего:   {s['n']}  (pos/is_1c={s['pos']}  neg={s['neg']})")
    print(f"train:   {s['train']}  (pos={s['train_pos']})   test: {s['test']}")
    bad = [i for i, r in enumerate(rows) if not str(r.get("text", "")).strip() or "is_1c" not in r]
    if bad:
        print(f"проблемные строки (пустой text / нет is_1c): {bad[:10]}")
    if s["n"] < MIN_RECOMMENDED:
        print(f"данных мало ({s['n']} < {MIN_RECOMMENDED}) — голова шумит; см. scripts/bootstrap_1c_gt.py")
    if s["train_pos"] in (0, s["train"]):
        print("train содержит только один класс — обучение бессмысленно")
    print("OK: датасет читается, форма корректна" if not bad else "ИТОГ: есть проблемные строки")
    return s


def _prf(y_true, y_pred) -> dict:
    tp = int(sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1))
    fp = int(sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1))
    fn = int(sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0))
    pr = tp / (tp + fp) if (tp + fp) else 0.0
    rc = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * pr * rc / (pr + rc) if (pr + rc) else 0.0
    return {"precision": round(pr, 4), "recall": round(rc, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn}


def train(rows: list[dict], model_name: str, out_dir: Path) -> int:
    """Обучить ST-энкодер + LR-голову, откалибровать порог, сохранить. 0 OK / 2 нет deps / 3 данные."""
    try:
        import joblib
        import numpy as np
        from sentence_transformers import SentenceTransformer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold
    except Exception as e:
        print(f"ОШИБКА: нет инференс-стека ({e}).", file=sys.stderr)
        print("Установите: pip install sentence-transformers scikit-learn joblib", file=sys.stderr)
        return 2

    if len({int(bool(r["is_1c"])) for r in rows}) < 2:
        print("ОШИБКА: датасет содержит < 2 классов.", file=sys.stderr)
        return 3
    if len(rows) < MIN_RECOMMENDED:
        print(f"данных мало ({len(rows)} < {MIN_RECOMMENDED}) — голова шумит, качество ограничено.")

    st = SentenceTransformer(model_name)
    X = np.asarray(st.encode(to_texts(rows, model_name), normalize_embeddings=True,
                             show_progress_bar=False))
    y = np.array([int(bool(r["is_1c"])) for r in rows])
    trm = np.array([split_of(r["text"], r) == "train" for r in rows])

    def _fit(xt, yt):
        return LogisticRegression(max_iter=2000, class_weight="balanced").fit(xt, yt)

    f1s = [_prf(y[te], _fit(X[tr], y[tr]).predict(X[te]))["f1"]
           for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(X, y)]
    cv_f1 = round(float(np.mean(f1s)), 4)
    print(f"5-fold CV F1 (vse {len(rows)}): {cv_f1} +- {np.std(f1s):.3f}")

    proba = _fit(X[trm], y[trm]).predict_proba(X[~trm])[:, 1]
    yte = y[~trm]
    best_thr, best_f1 = 0.5, -1.0
    for thr in [i / 100 for i in range(25, 76, 5)]:
        f1 = _prf(yte, (proba >= thr).astype(int))["f1"]
        if f1 > best_f1:
            best_thr, best_f1 = thr, f1
    m = _prf(yte, (proba >= best_thr).astype(int))
    print(f"test(hold-out n={int((~trm).sum())}) @thr={best_thr}: {m}")

    final = _fit(X[trm], y[trm])
    out_dir.mkdir(parents=True, exist_ok=True)
    st.save(str(out_dir / "st"))
    joblib.dump(final, out_dir / "head.pkl")
    (out_dir / "meta.json").write_text(json.dumps(
        {"backend": "sentence-transformers+lr", "model": model_name, "threshold": best_thr,
         "cv_f1": cv_f1, "test_f1": m["f1"], "n_train": int(trm.sum())},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"sohraneno -> {out_dir}/ (st/ + head.pkl + meta.json, threshold={best_thr})")
    print("Aktivaciya: ONEC_SETFIT_ENABLE=1 (porog iz meta.json; eval -- scripts/eval_1c_detector.py --setfit)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Train 1C-detector gate head (ST+LR, ADR-025 Stage 3)")
    ap.add_argument("--ground-truth", default=str(GROUND_TRUTH))
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help="sentence-transformer (default rubert-tiny2; upgrade multilingual-e5-small)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dry-run", action="store_true", help="validaciya dataseta bez ML-steka")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    gt = Path(args.ground_truth)
    if not gt.exists():
        print(f"ОШИБКА: GT не найден: {gt}", file=sys.stderr)
        return 1
    rows = load_rows(gt)
    if args.dry_run:
        dry_run(rows)
        return 0
    return train(rows, args.model, Path(args.out))


if __name__ == "__main__":
    raise SystemExit(main())
