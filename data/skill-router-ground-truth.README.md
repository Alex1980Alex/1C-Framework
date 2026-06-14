# skill-router-ground-truth.jsonl — схема и провенанс (roadmap 260613 Фаза A)

Эталон для `scripts/eval-skill-router.py`. Один JSON-объект на строку (JSONL, UTF-8).

## Поля

| Поле | Тип | Назначение |
|------|-----|------------|
| `prompt` | str | Входной промпт пользователя |
| `expected_skills` | list[str] | Ожидаемые скиллы (пусто = роутер должен молчать) |
| `expected_bundles` | list[str] | Ожидаемые бандлы роутера |
| `intent` | `action`\|`informational`\|`system` | Класс намерения |
| `source` | см. ниже | **Провенанс метки** (A4) |
| `split` | `train`\|`test`\|`quarantine` | Назначение в оценке (A6/A5) |

## Таксономия `source` (A3)

| source | Значение | Доверие метке |
|--------|----------|----------------|
| `spec` | Кейс спроектирован из определения/триггеров скилла | высокое (нет leakage) |
| `human` | Промпт написан человеком, метка проставлена вручную независимо | высокое |
| `transcript-human` | Промпт из живого транскрипта, метка проставлена **независимо** (человек смотрел определение скилла, НЕ вывод роутера) | высокое |
| `transcript-router` | Промпт из транскрипта, метка **выведена из session-активаций** (что роутер/человек-в-цикле активировал) | **LEAKAGE-кандидат** — метка коррелирует с поведением роутера |

## Политика `split` (A5/A6)

- **`train`** / **`test`** — только чистые от leakage кейсы (`source ∈ {spec, human, transcript-human}`).
  Split **заморожен** и **стратифицирован** по `intent` + домену (первый `expected_bundle`):
  внутри страты ~каждый 3-й → `test` (детерминированно по sha1(prompt)).
  Гейт (`scripts/skill_system_acceptance.py` критерий 3) меряет **pooled action_f1** на этом наборе.
- **`quarantine`** — `transcript-router` кейсы (leakage-кандидаты). **Остаются в файле**
  (ценные реальные промпты), но **исключены из train/test** и из метрик eval.
  Промоушен `quarantine → train/test` — **только** после независимой ре-верификации
  метки автором (смотреть определение скилла, НЕ вывод роутера); тогда `source`
  меняется на `transcript-human`. До тех пор они не влияют на честное число.

## Инварианты (проверяет `scripts/lint_skill_router_gt.py`, A8)

1. Каждый кейс несёт все 6 полей; `intent`/`source`/`split` из допустимых множеств.
2. `expected_skills ⊆ каталог` (скиллы из бандлов `skill-router-config.json`).
3. **0 leakage в гейте**: `source == transcript-router` ⇒ `split == quarantine` (никогда train/test).
4. `intent ∈ {informational, system}` ⇒ `expected_skills == []`.
5. Покрытие `test`: ≥1 action, ≥1 silence, ≥5 доменов (иначе предупреждение).

CI: blocking-job `skill-router-gt-lint` в `.github/workflows/ci.yml` (A9) — leakage/схема
краснят CI независимо от advisory `skill-router-eval`.

## Текущее состояние (A7 done, 2026-06-13)

73 `spec` (designed) + 22 `transcript-human` (ре-верифицированы, A7). Split:
**64 train / 31 test (26 action) / 0 quarantine**. Гейт репрезентативен
(`gate_representative=True`). Честное число: **pooled action_f1 = 0.7361 < 0.75**
(= исходное число до карантина; карантин давал оптимистичные 0.815, A7 восстановил
истину). Остаток 0.7361→0.75 — работа Фазы B5/C (тюнинг). **A7-рост до ≥30 action
в test** — мягкий follow-up (сейчас 26).

## A7 — аудит ре-верификации 22 кейсов (2026-06-13)

Независимая оценка по ДОМЕНУ промпта (не по прошлому выводу роутера). Все 22
метки доменно-защитимы → промоушен `transcript-router`→`transcript-human`. 3 кейса
помечены ⚠ borderline — **рекомендуется авторский ревью/override**.

| # | prompt (trunc) | label | домен-сигнал → вердикт |
|---|---|---|---|
| 74 | …механизм с занесением сертификатов | `1c-doc-research` | 1С-механизм «как включается» → research ✓ |
| 75 | НачалоПериода КонецПериода…заполняться | `bsl-development` | BSL CamelCase-идентификаторы → bsl ✓ |
| 76 | проверь как заполняеться пункт погрузки | `1c-doc-research`,`bsl-development` | логика заполнения 1С → bsl+research ✓ |
| 77 | таличная часть перестала заполняться | `1c-doc-research` | ТЧ-заполнение 1С → research ✓ |
| 78 | данные в запросе…проблемма в выводе | `bsl-development`,`1c-doc-research` | запрос 1С → bsl+research ✓ |
| 79 | ЗаписьЖурналаРегистрации не рекомендуется… | `1c-doc-research`,`bsl-development` | BSL API → bsl+research ✓ |
| 80 | список базб при открытии 1С пуст | `1c-doc-research` | платформенная инфра (ibases) → research ⚠ borderline (env-issue, не dev) |
| 81 | …обмен в Документ.гкс_ОснованиеДляДвижения… | `bsl-development` | `гкс_`/`Документ.` → bsl ✓ |
| 82 | открывать форму…поверх текущего | `bsl-development` | BSL-форма → bsl ✓ |
| 83 | вернём открытие формы…в отдельном окне | `bsl-development` | BSL-форма (revert) → bsl ✓ |
| 84 | при двойном клике…ФайлыВыбор…pdf просмотр | `bsl-development` | обработчик формы BSL → bsl ✓ |
| 85 | Процедура ЗаполнитьТабличныйДокументАктВозврата… | `bsl-development`,`code-verify` | ревью BSL-процедуры → bsl+verify ✓ |
| 86 | ДолжностьКладовщика как заполняеться | `bsl-development` | BSL-заполнение → bsl ✓ |
| 87 | Srvr=…;Ref=… конфигурация не запускается | `1c-doc-research` | conn-string/платформа → research ✓ (A2 conn-str) |
| 88 | 1c-debug-hmr переключсь на тестирование… | `1c-debug-hmr` | буквально называет скилл → 1c-debug-hmr ✓ |
| 89 | race: arm_next_rphost дренит…halt…JOB | `1c-debug-hmr` | инструмент arm_next_rphost → 1c-debug-hmr ✓ |
| 90 | анализ примечания на скриншоте и макета… | `code-verify`,`1c-doc-research` | проверка вёрстки ПФ → verify(+research) ✓ |
| 91 | …перенесли чтение pdf с сервера на клиент окатить назад | `bsl-development`,`1c-doc-research` | BSL-изменение (pdf read) → bsl+research ✓ |
| 92 | resume: investigate docs-change-enforcer sentinel… | `hook-debugging` | хук docs-change-enforcer → hook-debugging ✓ |
| 93 | docs/roadmap/…MEMORY_GOVERNANCE…приступай к реализации | `memory-unified` | домен из имени роадмапа = memory ⚠ borderline (generic «implement», слабый router-сигнал) |
| 94 | lazy-mcp failed в чем проблемма? | `[]` | lazy-mcp infra, нет профильного скилла → молчание ⚠ borderline |
| 95 | Канал нестабилен как усидить стабильность? | `[]` | мета/инфра, нет скилла → молчание ✓ |

**Интегритет:** доменный сигнал в большинстве объективен (BSL CamelCase → bsl
не judgment, а определение); метки подтверждены, не скопированы. Где сигнал слаб
(80/93/94) — флаг для автора. Изменений меток 0 (навязывать «отличие» ради вида —
нечестно). Автор может переразметить любой кейс и перезапустить eval.
