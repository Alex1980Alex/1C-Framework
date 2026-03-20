# Форматы логирования AutoResearch v2

## TSV — autoresearch-results.tsv

Компактный табличный лог для быстрого анализа и dashboard.

**Колонки:**
```
iteration	timestamp	commit	change	metric_before	metric_after	delta	tests	verdict	reason
```

**Пример:**
```tsv
1	2026-03-15T14:32:00Z	abc1234	Add response caching	142	135	-7	pass	KEEP	-7ms, stable
2	2026-03-15T14:37:00Z	def5678	Async DB queries	135	128	-7	pass	KEEP	-7ms, stable
3	2026-03-15T14:42:00Z	ghi9012	Inline serializer	128	131	+3	pass	REVERT	+3ms regression
4	2026-03-15T14:47:00Z	jkl3456	Connection pooling	128	128	0	pass	SKIP	no change
```

## JSONL — autoresearch.jsonl

Полный лог экспериментов со всеми деталями.

**Формат записи:**
```json
{
  "iter": 1,
  "ts": "2026-03-15T14:32:00Z",
  "domain": "python-performance",
  "commit": "abc1234",
  "change": "Add response caching",
  "metric_before": 142,
  "metric_after": 135,
  "delta": -7,
  "tests_pass": true,
  "verdict": "KEEP",
  "reviewer_reason": "-7ms, tests pass",
  "files_changed": ["src/api/routes/search.py"],
  "diff_lines": 12
}
```

## Living Document — autoresearch.md

Секции, обновляемые после каждой итерации:

| Секция | Обновляется | Кем |
|--------|-------------|-----|
| `## Goal` | Phase 0 | Wizard |
| `## Scope` | Phase 0 | Wizard |
| `## Metric` | Phase 0 | Wizard |
| `## Baseline` | Phase 0 | Wizard |
| `## Current Best` | Phase 8 (если KEEP и новый рекорд) | Script |
| `## History` | Phase 8 (каждая итерация) | Reviewer |
| `## Dead Ends` | Phase 8 (если REVERT) | Reviewer |
| `## Next Ideas` | Phase 8 (отмечает выполненные) | Executor |
| `## Comparator Reviews` | Phase 7 (каждые 5 итераций) | Comparator |
