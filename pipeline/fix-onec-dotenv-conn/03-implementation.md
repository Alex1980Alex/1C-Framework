# 03 Кодирование — Fix conn + _dotenv

## Изменённые файлы
- `.env:74` — корректная строка подключения (`DESKTOP-TNU600C` / `ИБTransportManagementDevelop`, завершающая `;`).
- `scripts/_dotenv.py` — matched-pair снятие кавычек (3 строки + комментарий вместо `.strip('"').strip("'")`).

## Проверка применения (runtime)
`load_dotenv()` отдаёт `ONEC_TEST_CONN = 'Srvr="DESKTOP-TNU600C";Ref="ИБTransportManagementDevelop";'` — обе внутренние кавычки на месте.
