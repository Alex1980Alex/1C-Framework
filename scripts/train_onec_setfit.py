#!/usr/bin/env python3
"""ADR-025: обучение SetFit-гейта детектора 1С (бинарный is_1c, слой ②).

Контрастно дообучает sentence-transformer на размеченных кейсах из
`data/1c-detector-ground-truth.json` (поле `is_1c` = таргет), затем обучает
логистическую голову. Сохраняет модель в `models/onec-setfit/` (подхватывает
`onec_setfit_gate.setfit_prob` при `ONEC_SETFIT_ENABLE=1`).

Выбор базовой модели (ADR-025):
  * `cointegrated/rubert-tiny2` (дефолт) — RU-native, 29M, старт по умолчанию;
  * `intfloat/multilingual-e5-small` (--model) — апгрейд-ступень, если tiny не добьёт recall.

Данные: SetFit — few-shot, но контраст-пары жидкие при <~150 примерах. Сейчас GT мал
(см. ADR-025) → скрипт ПРЕДУПРЕЖДАЕТ, но обучает (для smoke/baseline). Реальная активация —
после разметки до ~150–300.

Usage:
    python scripts/train_onec_setfit.py --dry-run          # валидация датасета без deps/обучения
    python scripts/train_onec_setfit.py                    # обучить rubert-tiny2 → models/onec-setfit/
    python scripts/train_onec_setfit.py --model intfloat/multilingual-e5-small
    python scripts/train_onec_setfit.py --epochs 4 --batch-size 16 --out models/onec-setfit

Тяжёлые зависимости (setfit, datasets, torch) импортируются ЛЕНИВО — `--dry-run` и
data-shaping функции работают на чистом stdlib (тестируемы без ML-стека).
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
MIN_RECOMMENDED = 150  # ниже этого SetFit-контраст жидкий → предупреждаем (не блокируем)


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


def partition(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    train = [r for r in rows if split_of(r["text"], r) == "train"]
    test = [r for r in rows if split_of(r["text"], r) == "test"]
    return train, test


def to_examples(rows: list[dict], model_name: str = DEFAULT_MODEL) -> tuple[list[str], list[int]]:
    """(texts, labels) для SetFit. label = int(is_1c). e5-модели — префикс `query: ` (model card)."""
    prefix = "query: " if "e5" in model_name.lower() else ""
    texts = [prefix + str(r["text"]) for r in rows]
    labels = [int(bool(r["is_1c"])) for r in rows]
    return texts, labels


def summarize(rows: list[dict]) -> dict:
    """Сводка датасета: размеры, баланс классов, train/test split."""
    train, test = partition(rows)
    pos = sum(1 for r in rows if r.get("is_1c"))
    return {
        "n": len(rows),
        "pos": pos,
        "neg": len(rows) - pos,
        "train": len(train),
        "test": len(test),
        "train_pos": sum(1 for r in train if r.get("is_1c")),
        "test_pos": sum(1 for r in test if r.get("is_1c")),
    }


def dry_run(rows: list[dict]) -> dict:
    """Проверить датасет без обучения: баланс/сплит/целостность. Возврат — сводка (тестируемо)."""
    s = summarize(rows)
    print("=" * 56)
    print("SetFit-гейт 1С — DRY-RUN датасета")
    print("=" * 56)
    print(f"всего:   {s['n']}  (pos/is_1c={s['pos']}  neg={s['neg']})")
    print(f"train:   {s['train']}  (pos={s['train_pos']})")
    print(f"test:    {s['test']}  (pos={s['test_pos']})")
    bad = [i for i, r in enumerate(rows) if not str(r.get("text", "")).strip() or "is_1c" not in r]
    if bad:
        print(f"⚠ проблемные строки (пустой text / нет is_1c): {bad[:10]}")
    if s["n"] < MIN_RECOMMENDED:
        print(f"⚠ данных мало ({s['n']} < {MIN_RECOMMENDED}) — для активации разметить до ~150–300 (ADR-025)")
    if s["train_pos"] == 0 or s["train_pos"] == s["train"]:
        print("⚠ train содержит только один класс — обучение бессмысленно")
    print("OK: датасет читается, форма корректна" if not bad else "ИТОГ: есть проблемные строки")
    return s


def _prf(y_true: list[int], y_pred: list[int]) -> dict:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    pr = tp / (tp + fp) if (tp + fp) else 0.0
    rc = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * pr * rc / (pr + rc) if (pr + rc) else 0.0
    return {"precision": round(pr, 4), "recall": round(rc, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn}


def train(rows: list[dict], model_name: str, out_dir: Path, epochs: int, batch_size: int) -> int:
    """Обучить SetFit и сохранить в out_dir; напечатать test-метрики. 0 OK / 2 нет deps / 3 данные."""
    try:
        from datasets import Dataset
        from setfit import SetFitModel, Trainer, TrainingArguments
    except Exception as e:  # любой сбой импорта = нет ML-стека
        print(f"ОШИБКА: нет зависимостей SetFit ({e}).", file=sys.stderr)
        print("Установите: pip install setfit datasets", file=sys.stderr)
        return 2

    train_rows, test_rows = partition(rows)
    tr_texts, tr_labels = to_examples(train_rows, model_name)
    te_texts, te_labels = to_examples(test_rows, model_name)
    if len(set(tr_labels)) < 2:
        print("ОШИБКА: train содержит < 2 классов — нечему учиться.", file=sys.stderr)
        return 3
    if len(rows) < MIN_RECOMMENDED:
        print(f"⚠ данных мало ({len(rows)} < {MIN_RECOMMENDED}) — обучаю baseline, качество ограничено.")

    model = SetFitModel.from_pretrained(model_name, labels=[0, 1])
    train_ds = Dataset.from_dict({"text": tr_texts, "label": tr_labels})
    args = TrainingArguments(batch_size=batch_size, num_epochs=epochs)
    trainer = Trainer(model=model, args=args, train_dataset=train_ds)
    trainer.train()

    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    print(f"модель сохранена → {out_dir}")

    if te_texts:
        preds = [int(x) for x in model.predict(te_texts)]
        print("test-метрики (is_1c):", _prf(te_labels, preds))
    else:
        print("⚠ test пуст — метрики не посчитаны")
    print("Активация: ONEC_SETFIT_ENABLE=1 (порог — ONEC_SETFIT_THRESHOLD, калибровать eval --setfit)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Train SetFit gate for 1С detector (ADR-025)")
    ap.add_argument("--ground-truth", default=str(GROUND_TRUTH))
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help="базовый sentence-transformer (дефолт rubert-tiny2; апгрейд multilingual-e5-small)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="каталог сохранения модели")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--dry-run", action="store_true", help="только валидация датасета (без deps/обучения)")
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
    return train(rows, args.model, Path(args.out), args.epochs, args.batch_size)


if __name__ == "__main__":
    raise SystemExit(main())
