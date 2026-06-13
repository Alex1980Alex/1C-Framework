# pipeline/ — постоянное хранилище артефактов SDLC-пайплайна

Папка-архив артефактов generic 4-stage пайплайна **Планирование → Дизайн → Кодирование →
Тестирование** ([ADR-017](../.claude/skills/architecture-research/adr/017-generic-4stage-pipeline-slash-state.md)).
**НЕ удалять — ни папку, ни задачи в ней.** Каждая задача навсегда остаётся подпапкой
`pipeline/<slug>/` (audit-trail: что планировали, как проектировали, что реализовали, чем тестировали).

> Домен-агностичный пайплайн разработки фреймворка. НЕ путать с 1С-цепочкой
> (`/analyze-1c-task → …`) — у неё свои артефакты в `features/<task>/`.

## Структура

```
pipeline/
├── README.md                    # этот файл (держит папку в git постоянно)
├── .gitignore                   # игнорит ТОЛЬКО transient (CURRENT-указатель, *.tmp)
├── CURRENT                      # (не в git) указатель на активную задачу
├── add-cache-x/                 # задача 1 — остаётся навсегда
│   ├── .pipeline-state.json     # состояние этапов (статусы, approved, current_stage)
│   ├── 01-architecture.md       # /pl-plan   — Планирование архитектуры
│   ├── 02-design.md             # /pl-design — Дизайн реализации
│   ├── 03-implementation.md     # /pl-code   — Кодирование (gated: дизайн approved)
│   └── 04-testing.md            # /pl-test   — Тестирование
└── another-task/                # задача 2 — остаётся навсегда
    └── …
```

## Персистентность (важно)

- **Папка постоянна** — этот `README.md` держит её в git даже пустой.
- **Задачи НЕ удаляются** — после прохождения всех этапов подпапка `<slug>/` и её артефакты
  остаются в репозитории навсегда (коммитятся как deliverables). Код пайплайна
  ([`pipeline_state.py`](../.claude/hooks/shared/pipeline_state.py)) только **создаёт/обновляет**
  файлы — **нигде не удаляет** папки задач (проверено: ни `rmtree`/`rmdir`/`unlink`).
- **Трекается git'ом:** `<slug>/0N-*.md` + `<slug>/.pipeline-state.json` (постоянный архив).
- **Игнорится** (`.gitignore`): `CURRENT` (волатильный указатель «активная задача») + `*.tmp`
  (временные файлы атомарной записи). Это НЕ данные задач.

## Использование

```
/pl-plan <описание задачи>     # создаёт pipeline/<slug>/ + 01-architecture.md
# ревью 01-architecture.md → /pl-design → ревью 02-design.md →
.venv/Scripts/python.exe .claude/hooks/shared/pipeline_state.py approve <slug>
/pl-code → /pl-test
```

Состояние любой задачи в любой момент:
```
.venv/Scripts/python.exe .claude/hooks/shared/pipeline_state.py status [slug]
```
