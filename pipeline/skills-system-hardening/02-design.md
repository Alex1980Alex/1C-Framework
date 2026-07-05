# 02 — Дизайн: Skills-system hardening

## Решения по пунктам

### 1. Pending-очередь — триаж, не слепой confirm
Политика: **reject** только явный шум (todo/протокол-напоминания, не паттерны);
**confirm** — конкретные переиспользуемые знания (BSL/1C/error-fix + инженерные уроки).
Итог: 5 reject (ШАГ-N hook-todo, «Сохранить в кеш» ×3), 73 confirm → detach-harvest.
Через MCP (не прямой jsonl-edit) — сохраняет идемпотентный point_id + epoch.bump.

### 2. skill-lint
Реальных errors нет — 48 были из устаревшего снапшота (до `%20`-unquote фикса).
Действие: refresh `data/_skill_lint.json`. 2×BODY500 (framework-config 542, triad-factory
534) НЕ режем: 34–42 строки сверх бюджета = анти-паттерн FRAGMENTED (плато-дисциплина G6),
это advisory-варнинги, CI гейтит только errors.

### 3. Нерутуемые скиллы — routed vs intentional
13 скиллов с уникальными доменными триггерами → новые bundles (keywords из их же описаний).
13 slash/делегация/meta → документирующий ключ `_unrouted_intentional` (absence = решение).
`_archived` исключён (не скилл). Инвариант: keywords не должны давать FP на чужой домен
(проверка через eval-skill-router: ни один новый скилл не появился в FP-списке).

### 4. CLAUDE.md
45→66 bundles, skill_library 80→98, learned_patterns 44→124 (после confirm).

### 5. eval-покрытие
Baseline LLM-driven и project-aware (delta=0) — прогон сейчас неинформативен. Долговечный
актив = **кейсы** (expect-якоря из реальных фактов скилла). 10 evals.yaml для топ-активированных
(1c-doc-research, langgraph/langchain-core, doc-to-skill, create-hook, framework-cli,
audit-docs, hooks-triad, doc-to-cache, framework-mcp-ui). Измерятся после фикса baseline.

## Approve
Дизайн одобрен (self-approve, maintenance-задача без внешних потребителей).
