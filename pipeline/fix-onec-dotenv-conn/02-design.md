# 02 Дизайн — Fix conn + _dotenv

## Решения
1. **`.env:74`** → `ONEC_TEST_CONN=Srvr="DESKTOP-TNU600C";Ref="ИБTransportManagementDevelop";`
   - Завершающая `;` валидна для 1С и дополнительно страхует от strip-бага.
2. **`scripts/_dotenv.py`** — снимать кавычки только парой по краям (matched pair), а не любые краевые символы:
   ```python
   val = val.strip()
   if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
       val = val[1:-1]
   ```

## Альтернативы
- Только `.env`-фикс + завершающая `;` — обходит баг, но не лечит корень парсера (любое quoted-значение, кончающееся на `"`, осталось бы битым). Отклонено в пользу matched-pair (root cause).

## Behavior-preservation
- `KEY="value"` → `value` (намеренное legacy сохранено).
- Значения без кавычек (API-ключи, пути Windows, `SONAR_TOKEN`) — без изменений.
- `env > .env` приоритет и best-effort семантика не тронуты.

## Одобрение
Дизайн одобрен (минимальная хирургическая правка, корень устранён).
