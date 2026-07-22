# fix-skip-kat-workspace (trivial)

## Проблема
В корне репозитория появился EDT-workspace `TransportManagementDevelop_KAT/` (создан вместе с
инфобазой `TransportManagementDevelop_KAT` на кластере DESKTOP-TNU600C:1541).
`docs-change-enforcer` посчитал его product-кодом и жёстко заблокировал завершение сессии
как `UNMAPPED` — требуя документацию для каталога, который документации не требует.

## Решение
Добавить `"TransportManagementDevelop_KAT/"` в `SKIP_PATTERNS`
[docs-change-enforcer.py](.claude/hooks/docs-change-enforcer.py) — ровно тот же класс,
что уже закрыт для `ИБTransportManagementDevelop/`, `TransportManagementDevelop_SVETLY/`, `MFM/`.

## Реализация
1 строка + комментарий-обоснование рядом с соседними workspace-исключениями.

## Проверка
- `python -c "import docs_change_enforcer"`-эквивалент: compile-smoke файла.
- Прогон Stop-хука: область `TransportManagementDevelop_KAT` больше не всплывает в UNMAPPED.

## Тестирование
Синтаксическая проверка + повторный прогон гейта в этой же сессии.
