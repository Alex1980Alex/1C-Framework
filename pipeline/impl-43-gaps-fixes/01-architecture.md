# 01 — Планирование: закрытие пробелов 43.5 (ТОП-3 + остаток)

## Задача
Реализовать фиксы из глубокого адверсариального анализа `43.5_СКВОЗНАЯ_КАРТА.md`
(`pipeline/docs-43-gaps-deep-analysis/01-planning.md`): сначала ТОП-3, затем остаток.

## Источник
Адверсариальный анализ (заземлён на код) выявил: 3 заявленных пробела переоценены,
7 скрытых (H1–H7) ценнее. Vector BSL уже реиндексится на commit; реальные дыры — call-graph,
межсессионный gate, false-advance.

## Объём (scope)
| # | Пробел | Sev | Тип |
|---|---|---|---|
| H2 | нет per-task сводки петель | med | code (ТОП) |
| call-graph | `bsl_call_graph.db` manual-only | med | code (ТОП) |
| H5 | gate слеп к межсессионным задачам | med | code (ТОП, **реальный баг**) |
| H7 | advance_for_artifact по имени файла → false-advance | low | code (latent) |
| H6 | G4 авто-approve без человека | med | skill |
| H1 | tool-effectiveness пишется-в-никуда | low-med | docs (честный статус) |
| H3 | W per-task не исполняется | low | docs+code (видимость) |
| H4 | apply_pattern неизмерим | low | by-design (без кода) |

## Инвариант
Anti-deadlock: фикс, вводящий false-block, ХУЖЕ исходного тонкого места. Все хуки — graceful (exception → не блок).
