# ADR-004: BSL Refactoring Architecture — Scenario 3 (ast-grep primary)

**Date**: 2026-04-17
**Status**: Accepted
**Context**: §5.5 BSL Refactoring v4.5 — R0 Research Validation

## Decision

**Выбран Scenario 3: ast-grep + tree-sitter-bsl как primary механизм**, с multilspy lifecycle для future fallback.

## Context

Требуется реализовать cross-file rename для BSL (1C:Enterprise) кода. Исследованы 3 подхода:

### R0.1 multilspy + BSL LS — FAIL
- BSL Language Server **не индексирует workspace** — только single-file анализ
- Cross-file references: **0 найденных**
- Cross-file rename: **1 edit** (только в файле определения)
- bulk preload через ExitStack не помог — ограничение BSL LS, не протокола

### R0.2 tree-sitter-bsl coverage — PARTIAL
- Покрывает: preprocessor, compile directives, Экспорт, async/await, regions
- **GAP: query language** (ВЫБРАТЬ/ГДЕ) — в строках, не парсится
- **187 ERROR nodes** на 3 модулях — скобочные выражения в присваиваниях
- Достаточно для rename операций (не нужен query parsing)

### R0.3 ast-grep — VIABLE
- 3 YAML правила созданы и валидированы
- customLanguages BSL через tree-sitter-bsl .dll
- Быстрый (Rust-based), JSON output, --update-all для in-place
- `expandoChar: _` для BSL ($ конфликтует)

### R0.4 Bulk preload pattern — NOT HELPFUL
- multilspy ref-counted open_file + ExitStack работает
- Но BSL LS не использует открытые файлы для cross-file анализа

## Decision Rationale

| Критерий | Scenario 1 (multilspy) | Scenario 2 (BSL LS fork) | Scenario 3 (ast-grep) |
|----------|----------------------|------------------------|---------------------|
| Cross-file rename | FAIL | Possible (Java) | PASS (text search) |
| Сложность | Низкая | Высокая (Java fork) | Средняя |
| Скорость | Медленно (Java subprocess) | Медленно | Быстро (Rust) |
| Поддержка | multilspy стабильный | Fork — ручной support | ast-grep активный |
| Coverage | Ограничен BSL LS | Полный | Частичный (query gap) |
| Time-to-value | 0 (не работает) | 2-3 недели | 1 неделя |

**Scenario 2 отклонён**: Java fork BSL LS — высокая стоимость поддержки.
**Scenario 1 отклонён**: Не работает (доказано R0.1).
**Scenario 3 выбран**: Работает, быстро, достаточно для rename.

## Consequences

### Positive
- Быстрый time-to-value (ast-grep rules работают уже сейчас)
- Rust performance (<1s на 2000 файлов)
- YAML rules — легко читаемые, расширяемые
- tree-sitter-bsl покрывает 95%+ BSL constructs для rename

### Negative
- Нет semantic analysis (ast-grep не понимает типы, scopes)
- Динамика `Выполнить("Метод()")` не покрывается — нужен regex fallback
- Query language не парсится — rename внутри запросов = manual
- 187 parse errors в tree-sitter-bsl на сложных модулях

### Mitigations
- Semantic gaps: fallback на text-search + confirmation dialog
- Query language: отдельный tree-sitter-1c-query grammar (R2.2)
- Parse errors: форк tree-sitter-bsl с патчами для скобочных выражений

## Implementation Path

- **R1 → R2 merge**: Пропускаем R1 (multilspy rewrite), идём прямо на R2 (ast-grep)
- **R2.1**: tree-sitter-bsl как git submodule
- **R2.2**: Форк + фиксы скобочных выражений
- **R2.3**: 4+ YAML правил для rename
- **R2.4**: ast-grep runner (Python wrapper)
- **R2.5**: Fallback chain: ast-grep → text search → manual prompt
- **R3-R5**: SCIP + Orchestrator + Benchmark как planned

## References
- `tools/bsl-ls/multilspy_recon.py` — R0.1 артефакт
- `tools/bsl-ls/tree-sitter-coverage.md` — R0.2 results
- `tools/bsl-ls/ast-grep-rules/` — R0.3 rules
- `docs/roadmap/multilspy-pattern-notes.md` — R0.1 + R0.4 analysis
