# Глубокий анализ пробелов 43.5 (адверсариальный, заземлён на код)

## Ответ «это исправлено?»: НЕТ — W rollup и граф-store НЕ исправлены (были документированы как кандидаты).

## Переоценка 3 заявленных
- **Gap #1 W rollup — ПЕРЕОЦЕНЁН.** Per-task W + `tool-effectiveness.jsonl` уже в run-1c-task шаг 9;
  «корректировка плана» без потребителя. Остаток XS: `--rollup` в файл.
- **Gap #2 граф — ЧАСТИЧНО ПЕРЕОЦЕНЁН.** Vector BSL реиндексится на commit (`git_post_commit_reindex.py`) =
  read+write догоняют. Реальная дыра — **call-graph `bsl_call_graph.db` + `graph_embeddings` manual-only**.
- **Gap #3 прогон — приёмка, не код.** 1 живой прогон.

## Скрытые (H1–H7)
| # | Пробел | Реальность | Sev | Fix |
|---|---|---|---|---|
| H1 | `tool-effectiveness.jsonl` пишется-в-никуда (только `--rollup` читает) | да | low-med | подключить консьюмера ИЛИ честно «отчётный» |
| H2 | нет per-task сводки петель (recall/capture/research/skill/pipeline + opt-out) | да | med | `_collect_signals`→`task_loops_report.py`→`LOOPS.md` [ТОП payoff] |
| H3 | TOOL-PLAN не сверяется с фактом; ни одного TOOL-USAGE-REPORT.md → W per-task не исполняется | да | low | diff plan↔actual |
| H4 | apply_pattern неизмерим | by-design | low | оставить |
| H5 | gate слеп к межсессионным задачам (S2 не видит pipeline `updated_at<start_S2`) | да | med | детект «1С-pipeline не-done» вместо session-window [реальный баг] |
| H6 | G4 авто-approve в AUTO без человека | by-design | med | опц. preflight-чек полноты ТЗ |
| H7 | advance_for_artifact по имени файла → false-advance (пустой ANALYSIS-REPORT) | latent | low | min-size/section guard |

## ТОП-3 на реализацию: H2 (сводка петель, S) · Gap#2 call-graph (S-M) · H5 (межсессионный gate, S-M).
Все без over-engineering / false-block. Главное: H2/H5/H1 (скрытые) ценнее заявленных (#1 переоценён, #2 частично).
