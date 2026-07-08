# 04 - Тестирование

- Полный сабмодуль-suite: **352 unit passed** (+12 новых: `TestConfigSrcMap` [парсинг map вкл. Windows-пути с ':', малформленные, alias-роутинг default/mapped, cache-изоляция], `TestActiveConfig` [active-alias роутит module-level resolve], `TestSrcFingerprint` [shape, none-при-missing, nested-edit/add/remove инвалидируют кэш]). Изоляция module-глобалов через `reset_uuid_globals` fixture.
- **code-verify** reviewer PASS (behavior-preservation + quality-review, 7/7 пунктов; подтвердил byte-identical default routing при незаданном env + корректность fingerprint + thread-safety реестра).
- ruff: 0 новых ошибок (стиль `Optional[]` предсуществующий, 13 UP045 в HEAD-версии; `tools/` линтится только собственным CI сабмодуля, парент CI = `src/ scripts/ .claude/hooks`).

Осталось (отложено): B5.c/B5.d file-cleanup; W2 B1 (persistent JOB, ADR-049) + B3 (long-poll ping).
