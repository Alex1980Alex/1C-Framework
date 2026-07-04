# Pipeline (compact) — Верификация P0 роадмапа 260704 (приоритет: код)

**Класс:** complex (7 пунктов × параллельная проверка), но правки точечные
**Дата:** 2026-07-04

## Планирование
Проверить исправление P0.1–P0.8 роадмапа `260704_ROADMAP_DOCS_DEEP_AUDIT.md`,
приоритет — расхождения в коде. 7 параллельных Explore-агентов (по пункту),
каждый сверяет доку с фактическим кодом/конфигом.

## Дизайн
Код = истина. Вердикт агента FIXED → отметить в роадмапе; NOT-FIXED/хвост →
править (код первым). Найденные code-level дефекты чинить немедленно.

## Кодирование (фактические правки)
Вердикты: **все 7 док-пунктов уже были исправлены** ранее. Дозачищены хвосты:
- **КОД:** `scripts/reindex_bsl_fast.ps1` — хардкод `--pooling-mode late-chunking`
  (SUPERSEDED 2026-05-20) → `standard` + переписаны SUPERSEDED-ноты (:5-7, :19-22, :92)
- `.claude/skills/bsl-reindex/SKILL.md:31` — «Full → qwen3-st (Late Chunking)» → std-pool
- Worktree-копия 40.8 — redact фрагмента утёкшего ключа (последний след на диске)
- `scripts/hooks/learning/__pycache__/*.pyc` — удалён след фантомной XSkill
- 22.5:30 — фантомная команда `/analyze-1c-task:research` → скрипт + предупреждение
- 32.7:177,:233 + 32.1:116 — «systemMessage»/«parallel async» → stdout/sync (по коду хука)
- Роадмап: P0.1–P0.8 отмечены ✅ DONE с verify-нотами

## Тестирование / верификация
- ps1: Parser::ParseFile → PARSE OK; `reindex_bsl_qwen3.py --pooling-mode` default="standard",
  choices содержит "standard" (флаг валиден)
- grep фрагмента утёкшего ключа по репо → 0 вхождений после redact
- reviewer-субагент по код-правке ps1 — см. отчёт сессии
