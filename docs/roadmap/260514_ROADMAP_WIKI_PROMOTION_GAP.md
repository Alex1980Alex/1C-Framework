# 260514 — Wiki Promotion Gap (L2 → L5 drafts)

**Status:** open
**Owner:** TBD
**Discovered:** 2026-05-14 during D4 wiki-pipeline closure session
**Effort:** small (data backfill + hook wiring) — actual «full activation» is medium-large

## Контекст

`docs/wiki/drafts/` (L5 layer per [[SCHEMA]]) пуст. Причины — две, ортогональные:

### Причина 1. WikiPromoter не запускается автоматически

`src/memory/librarian/wiki_promoter.py:WikiPromoter.scan_and_promote()` — единственный путь L2 (`learned_patterns`) → L5 (`docs/wiki/drafts/`). До коммита follow-up к этому roadmap'у он был импортирован **только** из `tests/integration/test_wiki_promoter.py`. Сейчас обёрнут в CLI:

```
python -m scripts.export_graph_to_wiki promote-patterns
```

Но нет cron/hook/daemon, который дёргает его периодически. Эквивалент `IncrementalWikiSync` для L2→L5 не написан.

### Причина 2. Корпус `learned_patterns` не дотягивает до spec-thresholds

Snapshot 2026-05-14 (44 точки в коллекции):

| Параметр | spec threshold | actual |
|---|---|---|
| `confidence ≥ 0.8` | required | 0 точек (макс встречается 0.7, у 11/44) |
| `usage_count ≥ 5` | required | 0 точек (поле отсутствует у **всех** 44) |
| eligible (AND) | — | **0** |

Поле `usage_count` не создаётся ни одним местом, которое пишет в `learned_patterns`. Поле `confidence` записывается, но никем не пересчитывается после первичного assignment, поэтому застряло на initial value (0.7).

Hooks-кандидаты, которые должны обновлять эти поля при успешном применении паттерна:
- [`session-memory-save.py`](../../.claude/hooks/session-memory-save.py) — Stop, сохраняет сессию (включая использованные паттерны)
- [`posttooluse-quality-feedback.py`](../../.claude/hooks/posttooluse-quality-feedback.py) — PostToolUse, реагирует на качество

Нужно подтвердить через grep, что эти хуки умеют bumping `usage_count` и recomputing `confidence`. Если нет — добавить.

## Что нужно сделать

| Задача | Effort | Заметка |
|---|---|---|
| 1. Подтвердить через grep что memory-hooks НЕ обновляют `usage_count`/`confidence` в `learned_patterns` | 15 min | Подтверждает root cause |
| 2. Добавить инкремент `usage_count` в hook когда паттерн успешно применён | 30-60 min | Нужен критерий "успешно применён" (e.g., от `posttooluse-skill-metrics`) |
| 3. Добавить пересчёт `confidence` (e.g., bayesian update) | 1-2h | Алгоритм TBD: успех ↑ confidence, фейл ↓ |
| 4. Backfill миграция: `usage_count = 0` для всех 44 существующих точек | 15 min | Чтобы фильтр Qdrant пропускал их (Range gte=0 на отсутствующее поле = исключение) |
| 5. Periodic invocation: либо cron, либо `SessionStart`-hook, либо daemon | 30 min | Самый простой вариант — добавить в `session-memory-save.py` (Stop) опциональный вызов `promote-patterns` |
| 6. Eval: смоук-тест что после прогрева сессии (>= 5 паттернов применилось) drafts/ реально наполняется | 30 min | Run end-to-end |

## Текущий workaround (until done)

CLI вызывается вручную:

```bash
# spec defaults — 0 promotions until data shape fixed
python -m scripts.export_graph_to_wiki promote-patterns

# realistic for current corpus (после задачи 4 backfill)
python -m scripts.export_graph_to_wiki promote-patterns --min-confidence 0.7 --min-usage 0
```

См. [[wiki-pipeline]] SKILL.md §«Состояние L5 drafts/ (2026-05-14)».

## Связано

- Wire-up CLI: commits 2026-05-14 (этот session, follow-up roadmap)
- Phase 9.1 memory hooks alignment (commit ac91c4b7): зафиксил dim mismatch для `skill_library`; не трогал ни `confidence`, ни `usage_count` semantics
- Spec: [openspec/changes/hermes-llm-wiki/specs/wiki-librarian/spec.md](../../openspec/changes/hermes-llm-wiki/specs/wiki-librarian/spec.md)
