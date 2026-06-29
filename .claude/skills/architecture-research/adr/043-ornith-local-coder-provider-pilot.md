# ADR-043: Внедрение Ornith-1.0 как локального Coder-провайдера (пилот за флагом)

**Дата:** 2026-06-30
**Статус:** proposed
**Исследование:** [ornith-1.0-agentic-coding-model-2026.md](../cache/ornith-1.0-agentic-coding-model-2026.md)

## Контекст

Во фреймворке есть слот «Coder»: паттерн Opus=Planner / Z.AI=Coder, `llm-rotation` (мульти-провайдер
OpenAI-формат + fallback), `ZAIWriteGuard` форсит делегацию >15 строк. Анализ внедрения (2026-06-30)
показал: delegation-слой **ненадёжен** (Z.AI `llm_complete` таймаутил дважды за сессию) и его ROI
**не измерен** (3/2055 записей с quality_score). Ornith-1.0 (DeepReinforce, MIT, OpenAI-совместимый,
SWE-Bench-V 9B=69.4 / 397B=82.4) — кандидат заменить/дополнить флаки-Z.AI локальной моделью `[web]`.

## Решение

**Пилот, не roll-out.** Добавить **Ornith-1.0-9B-Q4 GGUF** доп-провайдером в `llm-rotation` за
фиче-флагом, на **CPU/llama.cpp** (не трогая GPU-эмбеддер). Промоут — только после закрытия
delegation-телеметрии и прохождения гейта на golden-set. `[own]`

**Гейт промоута:** на наборе реальных Python-задач фреймворка Ornith-9B обходит Z.AI по `quality_score`
И по латентности. Без этого замера внедрение = вера, не эффективность.

## Последствия

### Положительные
- Offline, 0 API-cost, MIT; убирает сетевую зависимость и futile-таймауты (связано с graceful
  `ZAIWriteGuard` из коммита `cb609c6ad` — гард уже provider-aware).
- OpenAI-формат ⇒ встаёт в `llm-rotation` без переписывания логики.

### Отрицательные / ограничения
- **BSL/1С не покрывается** — Ornith обучена на общем SW (Gemma4/Qwen3.5), 1С не знает; правило
  «BSL = только Opus» сохраняется. Адресуемая поверхность = Python-срез `src/`/`scripts/` (домены
  `hook`/`skill`/`bsl` — `Never`-delegate). `[exp]`
- **GPU-конфликт:** единственный 24GB GPU занят TEI-эмбеддером+reranker (~18GB, ADR-040); 9B-bf16 (19GB)
  рядом не помещается, 35B-Q4 вытеснит retrieval. Локальная GPU-модель воюет с ядром поиска → пилот на CPU. `[own]`
- `qwen3_xml` tool-парсер ≠ нативный Claude Code формат → адаптер в `llm-rotation`.

## Альтернативы
- **35B-MoE / 397B на GPU** — skip: датацентр / вытеснение эмбеддера.
- **Оставить Z.AI** — статус-кво: но он флаки и ROI не измерен (мета-проблема не решается заменой вслепую).
- **2-й GPU под локальный Coder** — вне текущего железа; пересмотреть при апгрейде.

## Связанные файлы
`src/shared/llm_rotation/`, `.claude/hooks/z-ai-write-guard.py`, `.claude/hooks/shared/llm_health.py`,
`data/delegation-outcomes.jsonl` (нужна quality-телеметрия). Зеркалит лестницу ADR-012..015 (tooling-adoption).
