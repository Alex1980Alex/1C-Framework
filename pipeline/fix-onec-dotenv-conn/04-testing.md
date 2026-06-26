# 04 Тестирование — Fix conn + _dotenv

## Inline граничные кейсы парсера (6/6 PASS)
| Вход | Ожидание | Факт |
|---|---|---|
| `PLAIN=hybrid` | `hybrid` | OK |
| `WRAPPED="value"` | `value` (парные сняты) | OK |
| `TOKEN=squ_abc123` | без изменений | OK |
| `PATH1=C:\Program Files (x86)\1cv8` | без изменений | OK |
| `CONN=Srvr="H";Ref="DB";` | внутренние кавычки сохранены | OK |
| `CONN2=Srvr="H";Ref="DB"` | хвостовая `"` НЕ срезана | OK |

## code-verify (bug-fix-validation)
Reviewer-субагент: **PASS** (14/14 кейсов, корень устранён, регрессий нет, фикс минимален). Маркер `[CODE-VERIFY-PASS]`.

## Остаточный известный gap (вне scope)
Раннер всё ещё не стартует из-за CLI-контракта jar v0.5.1 (нужен Spring-профиль `app.*`) — отдельный трек (тест-ИБ), по решению пользователя.
