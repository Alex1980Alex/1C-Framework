# ADR-025: SetFit-гейт детектора 1С (stage-2a′) — обучаемая замена TF-IDF, opt-in каркас

**Дата:** 2026-06-18
**Статус:** accepted + РЕАЛИЗОВАНО (Этап 3 done — обучено на 230 GT, интегрировано, opt-in OFF по умолч.); backend ST+LR (setfit-пакет несовместим с transformers 5.x)
**Исследование:** [../cache/intent-detection-routing-best-practices.md](../cache/intent-detection-routing-best-practices.md)
**Связано:** ADR-023 (TEI rejected), ADR-024 (LLM-tail net-neutral; §Активация п.2 называет SetFit), #3 stage-2a (TF-IDF, ПРИНЯТО)

## Реализация (Этап 3, 2026-06-18)
**Backend сменён `setfit` → sentence-transformers + LR-голова.** Пакет `setfit` 1.1.3 несовместим с
transformers **5.x** в окружении (`default_logdir` removed; `config_setfit.json` 404 на новом
huggingface_hub). «SetFit-голова» реализована НАПРЯМУЮ на рабочем стеке фреймворка:
`SentenceTransformer` (rubert-tiny2, RU-native) → `LogisticRegression` (sklearn). **Ключ:** на RU
natural-language тайтлах задач frozen-эмбеддинги rubert-tiny2 НЕ коллапсируют (≠ Qwen3 на BSL-КОДЕ из
ADR-023 — content matters), поэтому даже без контрастного fine-tune тела голова бьёт baseline. [exp]

**Данные:** GT 68 → 230 ([`scripts/bootstrap_1c_gt.py`](../../../../scripts/bootstrap_1c_gt.py) —
майнинг реальных тайтлов из `configuration/*/docs/` + курируемые hard-кейсы; pos 134 / neg 96).
**Результаты:** CV F1 0.94 ± 0.03; **интегрированный каскад (regex+SetFit) на 230-GT: is_1c F1
0.883 → 0.974, Recall 0.813 → 0.978 (+16.5pp), precision 0.965 → 0.970, FN 25 → 3** — SetFit поймал
22 из 25 hard-кейсов, что regex упускал, без потери precision. [exp]

**Артефакты:** трейнер [`train_onec_setfit.py`](../../../../scripts/train_onec_setfit.py) (ST+LR, 5-fold
CV + калибровка порога → `models/onec-setfit/{st,head.pkl,meta.json}`, **gitignored** ~120МБ,
регенерируемо); гейт [`onec_setfit_gate.py`](../../../hooks/shared/onec_setfit_gate.py) грузит ST+LR
через `_STHead` (контракт `predict_proba` и инвариант безопасности «промоут только ask_1c» — прежние).
Контрастный fine-tune тела (полный SetFit) + `multilingual-e5-small` апгрейд — опциональные следующие
шаги. Активация: `ONEC_SETFIT_ENABLE=1` (по умолчанию OFF; порог из `meta.json`).

## Контекст
Семантический слой ② детектора 1С (`route_1c_task`, неуверенные входы confidence<0.7) сейчас — TF-IDF
(`onec_semantic_fallback.semantic_sim`, ПРИНЯТ #3 stage-2a). Его потолок: bag-of-words не различает
near-domain по СМЫСЛУ («обмен данными 1С» vs «обмен микросервисами kafka»). Две попытки поднять потолок
на **frozen**-представлениях отклонены: TEI-эмбеддинги Qwen3 коллапсируют на коротком РУ 1С-тексте
(ADR-023, [[feedback-bsl-embedding-collapse]]); LLM-on-tail на доступной qwen2.5:7b net-neutral (ADR-024,
F1 0.976 == TF-IDF baseline, недетерминизм). ADR-024 §Активация п.2 прямо называет **SetFit** масштабным
путём: контрастный fine-tuning энкодера адаптирует пространство под задачу — бьёт коллапс там, где
frozen-эмбеддинги и слабый LLM не справились. [exp]

## Решение
**SetFit как обучаемый слой ② (stage-2a′), подключён opt-in и по умолчанию СПИТ.** Каркас реализован;
активация — после разметки данных и обучения. [own]
- Модуль [`onec_setfit_gate.py`](../../../hooks/shared/onec_setfit_gate.py): `setfit_prob(text) → float|None`.
  None при `ONEC_SETFIT_ENABLE` не задан / нет `setfit` / нет модели / ошибка → caller (`_semantic_signal`)
  деградирует на TF-IDF. На module-level ТОЛЬКО stdlib (torch грузится лениво) — импорт из хука дёшев.
- Проводка в [`route_1c_task`](../../../hooks/shared/pipeline_1c_bridge.py): `_semantic_signal` пробует
  SetFit, при None — TF-IDF. Disabled (дефолт) ⇒ поведение **идентично** прежнему (существующие тесты зелены).
  Добавлен ключ `semantic_source ∈ {setfit, tfidf, skipped}` для наблюдаемости.
- **Бинарный** (is_1c), НЕ мультикласс по сложности: мультикласс требует ~×3 разметки/класс — отдельная
  ступень. Сложность остаётся за `estimate_effort` (③).
- Базовая модель: старт `cointegrated/rubert-tiny2` (RU-native, 29M); апгрейд `intfloat/multilingual-e5-small`
  (`--model`). MiniLM-L12-v2 отклонён: при равной памяти строго хуже e5-small на RU-MTEB. [own]
- Обучение [`train_onec_setfit.py`](../../../../scripts/train_onec_setfit.py) поверх
  `data/1c-detector-ground-truth.json`; калибровка порога [`eval_1c_detector.py --setfit`](../../../../scripts/eval_1c_detector.py).

## Инвариант безопасности
SetFit — **МЯГКИЙ** сигнал (как TF-IDF): положительный вердикт промоутит вход лишь в `ask_1c` (вопрос),
НИКОГДА в `confident`/`auto`. Recall ↑; ошибочный флип деградирует в вопрос — blast-radius безопасен. [own]

## Последствия
**Положительные:** путь к закрытию near-domain потолка TF-IDF, на который frozen-подходы (023/024) не
сгодились; каркас не рискует (dormant, graceful → TF-IDF); проводка готова (1 env-флаг). [own]
**Отрицательные:** требует разметки ~150–300 (GT сейчас мал) — главная стоимость; + 2 рантайм-зависимости
(`setfit`, `torch`) при активации (не тянутся, пока выключено). [own]

## Активация (условие пересмотра)
1. Разметить до ~150–300 поверх GT: silver из regex-high-confidence (лёгкая масса) + ручная разметка
   hard/ambiguous **границы** — именно её regex пропускает, на ней смысл SetFit; обучать только на
   regex-метках = скопировать regex, recall не вырастет. [own]
2. `python scripts/train_onec_setfit.py` (старт tiny2) → модель в `models/onec-setfit/`.
3. Калибровать порог `eval_1c_detector.py --setfit`; `ONEC_SETFIT_ENABLE=1` + A/B против TF-IDF на hold-out.

## Альтернативы (отклонены/отложены)
- TF-IDF финальным слоем (статус-кво) — near-domain потолок (мотив этого ADR).
- TEI-эмбеддинги (cosine/probe) — ADR-023, коллапс.
- LLM-on-tail на доступной модели — ADR-024, net-neutral.
- Мультикласс SetFit (is_1c × сложность) — отложено (×3 разметка); сложность за `estimate_effort`.

## Связанные файлы
- `.claude/hooks/shared/onec_setfit_gate.py` (новый), `scripts/train_onec_setfit.py` (новый)
- `.claude/hooks/shared/pipeline_1c_bridge.py` (`_semantic_signal`), `scripts/eval_1c_detector.py` (`--setfit`)
- `tests/unit/test_onec_setfit_gate.py` (новый), doc `docs/framework documentation/43_ПАЙПЛАЙН_1С/43.5_СКВОЗНАЯ_КАРТА.md`
