# Pipeline: Эвал + ADR cc-1c-skills (offline-редактор .mxl/.mxlx и .dcs)

**Тип:** medium (research + live-eval + ADR) · **Дата:** 2026-06-21

## 1. План
Доказать на реальных файлах проекта, что cc-1c-skills решает offline-правку табличных документов (.mxl/.mxlx) и DCS (.dcs), и оформить решение adopt/skip (ADR).

## 2. Дизайн
Клонировать cc-1c-skills (MIT) → запустить Python-порты скиллов (mxl-decompile/compile, dcs info/edit) против боевых `.mxlx`/`.dcs` через драйвер (пути литералами, обход bash-mojibake) → проверить round-trip без потери контента + чтение DCS, которое codepilot отдавал пустым + правку DCS на КОПИИ (оригинал неизменен) → ADR.

## 3. Реализация
- Клон `Nikolay-Shirokov/cc-1c-skills` (409★, MIT, Python+lxml) в temp.
- Драйвер live-теста (temp, вне репо).
- ADR-031 + регистрация в adr/_index.json; кеш `1c-form-skd-spreadsheet-tooling-2026.md` дополнен LIVE-VERIFIED; память обновлена.

## 4. Тест / результат
3 теста PASS на боевых файлах:
- MXL round-trip `ПФ_MXL_АктРасхожденияВеса_by.mxlx`: текст-значения 84/84, потеряно 0.
- DCS read `гкс_РеестрОтгрузки`: 1 набор/10 полей/запрос/4 ресурса/3 параметра/2 варианта (codepilot отдавал 0).
- DCS add-parameter на КОПИИ: rc=0, 4 параметра, оригинал не тронут (md5).
Вердикт: **ADOPT** (ADR-031). Открытый риск R-1 — рендер-verify recompiled .mxlx через update_database.
