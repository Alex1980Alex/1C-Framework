#!/usr/bin/env python3
"""ADR-025 stage-2a′: SetFit-гейт детектора 1С — обучаемая замена TF-IDF (слой ②).

`setfit_prob(text) -> float ∈ [0,1] | None` — калиброванная вероятность того, что
вход является 1С-задачей, по бинарному SetFit-классификатору (контрастно дообученный
sentence-transformer). Включается **opt-in** и по умолчанию **спит**:

    None  ⟸  ONEC_SETFIT_ENABLE не задан  ИЛИ  setfit не установлен
             ИЛИ  обученной модели нет     ИЛИ  любая ошибка
        → вызыватель (`route_1c_task._semantic_signal`) деградирует на TF-IDF
          (`onec_semantic_fallback.semantic_sim`) — текущий каскад не ломается ни в одной точке.

Инвариант безопасности (как у TF-IDF, ADR-023/024): SetFit — **МЯГКИЙ** сигнал. Положительный
вердикт промоутит вход лишь в `ask_1c` (вопрос пользователю), НИКОГДА в `confident`/`auto`-прогон.
Recall ↑, но ошибочный флип деградирует в вопрос — blast-radius безопасен.

Контракт лёгкости: на module-level — ТОЛЬКО stdlib. `import setfit`/torch выполняется ЛЕНИВО
внутри `_load_model()`, поэтому импорт этого модуля из хука (свежий процесс на каждый вызов)
стоит микросекунды и не тянет ML-стек, пока гейт выключен.

Активация (см. ADR-025): разметить ~150–300 кейсов поверх `data/1c-detector-ground-truth.json`,
обучить `scripts/train_onec_setfit.py` (старт `cointegrated/rubert-tiny2`; апгрейд
`intfloat/multilingual-e5-small`), затем `ONEC_SETFIT_ENABLE=1`. Калибровка порога —
`scripts/eval_1c_detector.py --setfit`.

CLI (отладка):
    python .claude/hooks/shared/onec_setfit_gate.py info             # статус: enable/deps/модель
    python .claude/hooks/shared/onec_setfit_gate.py predict "текст"  # вероятность 1С (или None)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# .claude/hooks/shared/onec_setfit_gate.py → parents[3] = repo root
PROJECT_ROOT = Path(__file__).resolve().parents[3]

_DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "onec-setfit"
_UNSET = object()  # sentinel «модель ещё не пробовали грузить» (отличим от None = «грузили, нет»)
_model_cache: object = _UNSET


def is_enabled() -> bool:
    """Гейт активен? opt-in через ONEC_SETFIT_ENABLE (1/true/yes/on). По умолчанию выключен."""
    return os.environ.get("ONEC_SETFIT_ENABLE", "").strip().lower() in ("1", "true", "yes", "on")


def model_dir() -> Path:
    """Каталог обученной модели: ONEC_SETFIT_MODEL_DIR или models/onec-setfit/ под корнем репо."""
    env = os.environ.get("ONEC_SETFIT_MODEL_DIR")
    return Path(env) if env else _DEFAULT_MODEL_DIR


def threshold() -> float:
    """Порог вероятности для «семантического хита» (env ONEC_SETFIT_THRESHOLD, дефолт 0.5).

    Откалиброванный порог — отдельный от TF-IDF-порога (0.70): шкала вероятностей SetFit
    не совпадает со шкалой косинуса bag-of-words. Подбирается `eval_1c_detector.py --setfit`.
    """
    try:
        return float(os.environ.get("ONEC_SETFIT_THRESHOLD", "0.5"))
    except (TypeError, ValueError):
        return 0.5


def _have_setfit() -> bool:
    """Установлен ли пакет setfit? (без фактической загрузки тяжёлого стека)."""
    import importlib.util

    return importlib.util.find_spec("setfit") is not None


def _load_model():
    """Лениво загрузить SetFitModel из model_dir(); кэш на процесс. None при отсутствии deps/модели.

    Кэшируется ДАЖЕ отрицательный результат (None) — повторная загрузка в рамках процесса не
    предпринимается (хук всё равно живёт один вызов). Тесты обходят кэш, передавая model= напрямую.
    """
    global _model_cache
    if _model_cache is not _UNSET:
        return _model_cache
    _model_cache = None  # пессимистичный дефолт: считаем «нет», пока не загрузим успешно
    d = model_dir()
    if not d.exists():
        return None
    try:
        from setfit import SetFitModel
    except Exception:
        return None  # setfit/torch не установлены — спим, caller падает на TF-IDF
    try:
        _model_cache = SetFitModel.from_pretrained(str(d))
    except Exception:
        _model_cache = None
    return _model_cache


def _positive_prob(proba) -> float | None:
    """Вероятность позитивного класса (is_1c=1) из predict_proba. None при нераспознаваемой форме.

    proba — массив/тензор формы (1, n_classes). Модель обучается с метками [0, 1]; sklearn-голова
    хранит classes_ отсортированными → последний столбец = метка 1 = is_1c. Толерантна к
    list / numpy.ndarray / torch.Tensor (через .tolist при наличии).
    """
    try:
        row = proba[0]
        vals = [float(x) for x in (row.tolist() if hasattr(row, "tolist") else row)]
    except Exception:
        return None
    if not vals:
        return None
    if len(vals) == 1:  # вырожденный одно-классовый выход — берём как есть
        return vals[0]
    return vals[-1]  # метки [0,1] → последний столбец = P(is_1c)


def setfit_prob(text: str, model=None) -> float | None:
    """Вероятность того, что text — 1С-задача, по SetFit-гейту. None = гейт спит/ошибка (→ TF-IDF).

    best-effort: НИКОГДА не кидает. `model` (опц.) — внедрить модель в обход кэша/файла (для тестов).
    """
    if not is_enabled():
        return None
    try:
        m = model if model is not None else _load_model()
        if m is None:
            return None
        proba = m.predict_proba([text or ""])
        return _positive_prob(proba)
    except Exception:
        return None


def status() -> dict:
    """Снимок состояния гейта (для CLI info / диагностики)."""
    d = model_dir()
    return {
        "enabled": is_enabled(),
        "setfit_installed": _have_setfit(),
        "model_dir": str(d),
        "model_present": d.exists(),
        "threshold": threshold(),
    }


def _setup_io() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    _setup_io()
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "info":
        st = status()
        for k, v in st.items():
            print(f"{k}: {v}")
        if not st["enabled"]:
            print("→ гейт ВЫКЛЮЧЕН (ONEC_SETFIT_ENABLE не задан) — route падает на TF-IDF")
        elif not st["setfit_installed"]:
            print("→ setfit НЕ установлен: pip install setfit")
        elif not st["model_present"]:
            print("→ модели нет: обучите scripts/train_onec_setfit.py")
        return 0
    if len(args) >= 2 and args[0] == "predict":
        p = setfit_prob(args[1])
        print(p if p is not None else "None (гейт спит / нет модели / ошибка)")
        return 0
    print("usage: onec_setfit_gate.py info | predict <text>")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
