# Усиление тонких мест — Планирование (глубокий анализ)

## Запрос
Исправить все тонкие места 1С-пайплайна (4 из 43.5) + глубокий анализ тонких/потенциально-тонких мест.

## Глубокий анализ (адверсариальный субагент, заземлён на код) — N1–N12

| # | Тонкое место | Тип | Severity | Решение |
|---|---|---|---|---|
| N1 | Stop-каскад: 3 enforcer блокируют по очереди (3 Stop-цикла) | fragility/UX | med | **FIX** — превью в block-сообщении pipeline-protocol-stop |
| N2 | session_start=None → все 3 enforcer exempt | false-allow | med | by-design (graceful); N3 снижает корень |
| N3 | tail 2 МБ обрезает ранний recall/research в длинной сессии → false-block | false-block | med | **FIX** — TRANSCRIPT_TAIL_BYTES=8 МБ |
| N4 | title-coupling `startswith("1С-задача")` в 6 местах + дубль предиката (divergence) + рассинхрон скобки (bridge без `(`, хуки с `(`) | fragility/false-allow | **high** | **FIX** — `_1C_TITLE_PREFIX`+`is_1c_task_title()` в bridge, единый предикат |
| N5/N9 | AUTO авто-approve обходит G4 (дизайн не ревьюится) | bypass | med | by-design + **FIX** audit-метка `approved_by="auto"` |
| N6 | memory capture `.md`: `/memory/` over-match (src/memory/, docs/*/memory/) | false-allow (latent) | low | **FIX** — сузить до `.claude/`-пути курируемой памяти |
| N7 | research засчитывает любой WebSearch (gaming) | bypass | low | **by-design** (relevance-check = false-block) + opt-out audit |
| N8 | git-fallback denylist неполон (data/memory_drafts) | false-block (edge) | low | defer (porcelain не показывает ignored → риск ниже) |
| N10 | opt-out env blanket-bypass | bypass | low | by-design + **FIX** audit-log `allow-optout` |
| N11 | AUTO-капкан: /run-1c-task без recall+capture+WebSearch → тройной Stop | fragility/UX | med | **FIX** — under-steps в run-1c-task SKILL.md |
| N12 | advance этапов по имени файла, не содержимому | false-allow (мягкий) | low | by-design (ADR-019 F-1.5 best-effort) |

## Вывод
**Чиню (genuine, без false-block):** N4 (высш.), N3, N6, N5/N9 (audit), N1, N11, N10 (audit).
**Оставляю by-design (фикс = false-block / противоречит замыслу):** N7 (research relevance), N9 (G4 в AUTO —
смысл режима), N12, apply_pattern (нельзя enforce «apply»), N2/N8 (graceful/edge). Каждое — с честным обоснованием в 43.5.
