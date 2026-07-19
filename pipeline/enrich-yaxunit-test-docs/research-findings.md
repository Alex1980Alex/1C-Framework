# Research findings (для слоя B обогащения) — атрибутированные факты

## Агент 2 — CI/раннеры/coverage/сравнение (получен 2026-07-19)

### mcp-onec-test-runner = alkoleft/METR
- Репо: [alkoleft/mcp-onec-test-runner](https://github.com/alkoleft/mcp-onec-test-runner) (101★, Kotlin, v0.5.2 2026-03). «METR — MCP 1C:Enterprise Test Runner». Это ИМЕННО наш сервер.
- Tools: `run_all_tests` `run_module_tests` `build_project` `dump_config` `launch_app` `list_modules` `get_configuration` `check_platform` `check_syntax_edt` `check_syntax_designer_config`(CheckConfig) `check_syntax_designer_modules`(CheckModules).
- YAML-конфиг: `app.base-path`, `app.platform-version`, `app.connection.connection-string` (`File='…';`),
  `app.source-set[]` = `{path, name, type: CONFIGURATION|EXTENSION, purpose: [TESTS, YAXUNIT]}` ← где объявляется тест-расширение,
  `app.tools.builder: DESIGNER|IBCMD` (сам строит БД, vrunner НЕ нужен), `app.tools.edt-cli`.
- Поток: детект формата (EDT/Designer) → опц. EDT→XML → builder обновляет БД с YAxUnit-расширением → прогон `RunUnitTests` → JUnit.

### vrunner (vanessa-runner) — CI-раннер
- [vanessa-opensource/vanessa-runner](https://github.com/vanessa-opensource/vanessa-runner) (259★, `opm install vanessa-runner`).
- Прогон YAxUnit: `vrunner run --command 'RunUnitTests=<config.json>'` (платформа в enterprise, ключ `/C"RunUnitTests=…"`).
- v3.0: `vrunner test` (xUnit+BDD), `vrunner infobase update`; расширение `YAxUnit.cfe` ставится как обычное расширение.
- Источники: [infostart 1976659](https://infostart.ru/1c/articles/1976659/), [1cfullstack.ru](https://1cfullstack.ru/yaxunit-freymvork-modulnogo-testirovaniya-dlya-1s/).

### Coverage41C — покрытие в Sonar (ADOPT для нас)
- [1c-syntax/Coverage41C](https://github.com/1c-syntax/Coverage41C) (110★, Java+EDT libs; переехал из pumbaEO).
- Цепляется как debugger-клиент по HTTP-отладке (`http://127.0.0.1:1550/`), пишет исполненные строки → `genericCoverage.xml` (SonarQube Generic Test Coverage).
- CLI: `start|stop|check|clean|dump|convert`; `start -i <ib> -u <dbgURL> -s <srcDir>|-P <edtProj> -o <out>`.
- Sonar: `sonar.coverageReportPaths=./genericCoverage.xml` ([docs.checkbsl.org](https://docs.checkbsl.org/content/11_ДополнительныеИнструменты/)).
- Использование: `Coverage41C start` → `vrunner run … RunUnitTests` → `Coverage41C stop` → sonar-scanner. Согласуется с нашей RDBG-инфрой.

### CI-шаблон (GitLab/GHA)
- База — [jugatsu/onec-docker](https://github.com/jugatsu/onec-docker) / [firstBitMarksistskaya/onec-docker](https://github.com/firstBitMarksistskaya/onec-docker) (headless через Xvfb). Нет официального `onec/1ce`.
- Стадии `build→test→sonar`, `test:yaxunit` ∥ `sonar` через `needs:`; JUnit артефакт `reports: junit:`.

### Сравнение фреймворков
- **YAxUnit** [bia-technologies/yaxunit](https://github.com/bia-technologies/yaxunit) (312★, v25.12 2025-12, активен) — **де-факто стандарт** unit-тестов BSL, EDT-плагин, JUnit/Allure.
- **xUnitFor1C** [xDrivenDevelopment/xUnitFor1C](https://github.com/xDrivenDevelopment/xUnitFor1C) (362★, заморожен 2017) — SKIP (предшественник).
- **1Unit** — исторический, SKIP.
- **Vanessa-ADD/automation** [pr-mex/vanessa-automation](https://pr-mex.github.io/vanessa-automation/) — BDD/UI слой, КОМПЛЕМЕНТ (не конкурент); наш va-bdd-testing.

### ⚠ КОРРЕКЦИЯ понятия «smoke» (важно для рек.3)
Три РАЗНЫХ вещи, не путать:
- **(a) YAxUnit `ДымовыеТесты`** = ФУНКЦИОНАЛЬНЫЙ smoke в RUNTIME: `ОткрытиеФорм`/`ПроведениеДокументов`/
  `ПроверкаПрав`/`ЗаписьСправочников` по ВСЕЙ конфе ([docs/features/smoke](https://bia-technologies.github.io/yaxunit/docs/features/smoke/)).
  НЕ компиляция. Настройка объект `"ДымовыеТесты"`.
- **(b) Реализация smoke** = отдельное НЕЗРЕЛОЕ расширение [alexandr-yang/yaxunit-smoke](https://github.com/alexandr-yang/yaxunit-smoke)
  (20★, «not for production», портирован из Vanessa-ADD). SKIP.
- **(c) Компиляция/метаданные-чек** = ДРУГОЙ путь: syntax check (`CheckModules`/`CheckConfig`/EDT-validate),
  через `check_syntax_designer_modules`/`check_syntax_edt` METR или `vrunner syntax-check`.

**Для рек.3-«смоук»:** правильная трактовка = быстрый unit-прогон затронутого модуля `run_module_tests`
(+ опц. syntax check) — POST-change комплемент impact-чека. НЕ встроенный ЮТДымовыеТесты (тяжёлый nightly
whole-config functional), НЕ расширение yaxunit-smoke. → Моё Part-B в 01 («ЮТДымовыеТесты = compile-check»)
уточняется: это functional smoke; правку внести в доки.

## Агент 1 — официальные доки API (получен 2026-07-19) — подтверждает ground truth + обогащает

Источник: [bia-technologies.github.io/yaxunit](https://bia-technologies.github.io/yaxunit/) (v25.12; механизмы стабильны 24/25).
⚠ Caveat агента: длинные BSL-блоки — реконструкция через web-fetch summarizer; ИМЕНА методов/ключей
сверены verbatim и надёжны, но точное форматирование сверять с исходником перед вставкой.

- **Ловушка имён**: `ЮТТесты` (двойная Т) = регистратор; `ЮТест` (одна Т) = фасад утверждений.
- **Lifecycle-события** = АВТО-детект по имени (экспортная процедура БЕЗ параметров в тест-модуле):
  `ПередВсемиТестами ПередТестовымНабором ПередКаждымТестом ПослеКаждогоТеста ПослеТестовогоНабора
  ПослеВсехТестов`. Опц. override: `.Перед("Имя")`/`.После("Имя")` при регистрации (module/suite/test).
  Грабли: в клиент-серверных модулях хендлеры зовутся ДВАЖДЫ (клиент+сервер); before-each ВНУТРИ
  per-test транзакции, before-all — СНАРУЖИ (важно для очистки). [features/events](https://bia-technologies.github.io/yaxunit/docs/features/events)
- **Data-driven (2 механизма + не путать с 3-м)**:
  - `.СПараметрами(зн1, зн2, ...)` (до 10, каждый набор = ИЗОЛИРОВАННЫЙ прогон, своя строка отчёта) —
    ПРЕДПОЧТИТЕЛЬНО; варианты `.СПараметрамиНаКлиенте/НаСервере`. [features/variants](https://bia-technologies.github.io/yaxunit/docs/features/variants)
  - `ЮТест.Варианты("Кол1,Кол2").ДобавитьКомбинации(М1, М2).СписокВариантов()` — декартово произведение,
    цикл ВНУТРИ одного теста (одна строка отчёта).
  - `Контексты` = ось ИСПОЛНЕНИЯ (клиент/сервер), 4-й арг `ДобавитьТест` + `filter.contexts` — НЕ параметризация.
  - `ЮТест.Контекст()` = мешок данных между тестами/хендлерами (`КонтекстТеста/Набора/Модуля`) — ДРУГАЯ фича.
  - **`.СКонтекстом(...)` в доках НЕ найден** → подтверждает: `ДобавитьСерверныйТестСКонтекстом` (скилл) = галлюцинация.
- **Теги**: `.Тег("Имя")` или арг `ТегиСтрокой` (через запятую); фильтр `config.json` `filter.tags:[...]`.
- **Изоляция данных** (2 независимых механизма, оба — модификаторы регистрации):
  - `.ВТранзакции([Булево])` — откат транзакции после теста. НЕ спасает от коммитов ВНЕ транзакции
    (фоновые задания, отдельные сессии, COM) — general-1C знание, в доках не перечислено.
  - `.УдалениеТестовыхДанных([Булево])` — НЕ транзакция: запоминает объекты/записи РС, созданные ЧЕРЕЗ
    `ЮТест.Данные()`-API, и удаляет их; **изменения НЕ откатывает**. Не трекает: созданное вне API,
    внутри тестируемого кода, клиент-данные через серверные callbacks. [test-data-deletion](https://bia-technologies.github.io/yaxunit/docs/features/test-data/test-data-deletion)
  - `ЮТест.Данные()` фабрика: `.КонструкторОбъекта(...)`/`.КонструкторДвижений(...)`, `.Фикция("Рекв")`,
    `.ФикцияОбязательныхПолей()`, `.ТабличнаяЧасть(...)`, `.ДобавитьСтроку()`, `.Провести()`/`.Записать()`.
- **Мокито — ПОДТВЕРЖДАЕТ ground truth дословно**: `&Вместо("Метод")`+`МокитоПерехват.АнализВызова(<Об>,"Метод",
  Мокито.МассивПараметров(...),ПрерватьВыполнение)` обвязка ОБЯЗАТЕЛЬНА (нет runtime-патчинга; заём `&Вместо`+
  `ПродолжитьВызов`). Поток `Обучение(Об).Когда("М",Мокито.МассивПараметров(...)).Вернуть(зн).Прогон()` →
  вызов → `Проверить(Об).КоличествоВызовов("М").Равно(1)`. Глаголы: `Вернуть/ВыброситьИсключение/Пропустить/
  Наблюдать(spy)/ВыполнитьМетод`. НЕЛЬЗЯ мокать: платформенные/глобальные/методы расширений/внешних обработок
  → обёртка своей функцией + мок обёртки ([cook-book/platform-mocking](https://bia-technologies.github.io/yaxunit/docs/cook-book/platform-mocking)). Готовые заглушки: `HTTPСервисЗапрос HTTPОтвет HTTPСоединение` и др.
  - ⚠ **«Безопасный режим» для Мокито — HONEST GAP**: в доках НЕ подтверждён; вероятно инференс из свойства
    «безопасный режим» расширения 1С (привилегированные операции запрещены → ломает `МокитоПерехват`). Наш
    known-issue безопасного режима (17.6 §7) — про ЧТЕНИЕ config.json расширением YAXUNIT, это ДРУГОЕ; не смешивать.
- **Запуск**: `1cv8c ENTERPRISE /IBName … /C RunUnitTests=<config.json>` (thin/thick/EDT). YAxUnit **НЕ** использует
  `/TESTMANAGER` (подтверждает 17.6 §7). `config.json` ключи: `filter{extensions[деф "tests"],modules,tests,suites,
  tags,contexts}`, `reportFormat` "jUnit"(деф)/"JSON"/"allure", `reports[]{format,path}`, `reportPath`,
  `closeAfterTests`(true), `showReport`(true), `logging{file,enable,console,level}`, `exitCode`(файл 0/1 для CI),
  `projectPath`, `workspacePath`, `rpc`. Спеллинг — **`jUnit`**. [run/configuration](https://bia-technologies.github.io/yaxunit/docs/getting-started/run/configuration)
  - ⚠ vrunner: доки YAxUnit его НЕ упоминают; `vrunner xunit` гонит Vanessa-ADD/xUnitFor1C, НЕ YAxUnit. Для YAxUnit
    авторитетно — прямой `1cv8c /C RunUnitTests=` или passthrough `vrunner run --command`. Наш путь = METR (native-launch).
- **Дискавери (доки)**: extension-scan НЕзаимствованного общего модуля с `ИсполняемыеСценарии()`, скоуп `filter.extensions`
  (деф `["tests"]`). Про подсистему `ЮТТ_ЮТПодключаемыеМодули`/`Модульные` доки МОЛЧАТ.

### 🔑 Разрешение дискавери (сверка с ИСХОДНИКОМ — авторитетно для v24.x)
`ЮТПодключаемыеМодулиСлужебный` перечисляет модули **по СОДЕРЖИМОМУ ПОДСИСТЕМ**:
`ПодключаемыеМодулиПодсистемы(ИмяПодсистемы, ...)` (подсистемы «ФормированиеОтчета»/«Кодогенерация»/«ДымовыеТесты»,
`ПодсистемыПодключаемыхМодулей()`). Тест-модули = подсистема `Модульные` под маркером `ЮТТ_ЮТПодключаемыеМодули`.
→ **Регистрация в `Модульные.<Content>` = ОБЯЗАТЕЛЬНА** (это и есть «extension-scan» доков, конкретизированный
подсистемой). Имя модуля свободное (`гкс_…Тест` работает; ЮТТ — префикс ПОДСИСТЕМЫ, не модулей). Скилл «ничего
делать не нужно» — НЕВЕРНО; 17.6 §5 (регистрация в подсистеме) — ВЕРНО, но «имя должно начинаться с ЮТТ» — НЕВЕРНО.

## Агент 3 — Infostart/официальные практики (получен 2026-07-19)

- **Раскладка тестов** (structure.md): (1) вместе с движком YAxUnit — есть контекстная подсказка API, но
  движок обновляется сложнее; (2) отдельным расширением UnitTests — подсказки нет, зато замена движка простая.
  Наш проект = вариант (2).
- **Официальная схема имён модулей**: `[Префикс типа_][Объект]{_Суффикс}` — `ОМ_`(общий), `Док_`/`Спр_`/`РН_`/`РС_`,
  суффиксы `_МО`/`_ММ`/`_НЗ`; пример `ОМ_ОбщегоНазначения`, `Спр_Пользователи_МО`. ⚠ наш проект использует свой
  `гкс_<Объект>Тест` — оба валидны (дискавери по подсистеме, не по имени). Наименование теста: набор = `Вид Объект.
  [Модуль.] Метод`, тест = `Метод_Уточнение` (2-частный офиц.); 3-частный `Метод_Условие_Ожидание` (AAA) — community.
  «Всегда создавать тест-набор, даже для одного теста». Ассертов: «одна зона ответственности», не «1 физический assert».
- **Изоляция** (test-data-deletion.md): `.ВТранзакции()` оборачивает ТОЛЬКО серверный тест (клиентский игнор);
  только тело+ПередКаждым/ПослеКаждого в транзакции, `ПередВсемиТестами` — вне (не откатывается). НЕ спасает:
  клиентский тест, тестируемый метод с вложенными транзакциями, данные вне теста. Случайные данные → флаки (офиц.
  предупреждение). `ОбменДанными.Загрузка = Истина` = общая 1С-практика (не YAxUnit-специфика).
- **Мокито `&Вместо` шаблон** (mockito.md): `<Объект>` = ССЫЛКА НА МОДУЛЬ для общего модуля (НЕ `ЭтотОбъект`!),
  `ЭтотОбъект` для объектов, `Справочники.Пользователи` для менеджера. Обучение через менеджер = мок всех объектов
  типа; через объект = конкретный; через ссылку = для этой ссылки. ⚠ danger: в фазе `.Обучение()` вызовы обучаемого
  объекта возвращают инфо-о-вызове, НЕ делают полезной работы. Цепочку предикатов закрывать `.Получить()`.
  DI параметром ПРЕДПОЧТИТЕЛЬНЕЕ мока. Заглушки: `ЮТест.Данные().HTTPСервисЗапрос()/HTTPОтвет/HTTPСоединение`.
- **🔑 Безопасный режим — ПОДТВЕРЖДЁН официально** (run.md :::caution): «После загрузки расширения ОТКЛЮЧИТЬ
  безопасный режим и защиту от опасных действий» — иначе не работают перехваты Мокито И чтение config.json И
  `closeAfterTests`. (Закрывает honest-gap Агента 1: safe-mode реален, документирован.)
- **Headless**: `/C RunUnitTests` (не внешний тест-менеджер); `/TESTMANAGER` — для Vanessa, НЕ YAxUnit (моё
  разъяснение по механике, перепроверять на контуре). CI: `closeAfterTests=true`+`showReport=false`+`exitCode`-файл.
  С 25.09 — override параметров в строке запуска. Конфликты лицензий при параллельных прогонах (= наш W13). EDT 25.01+
  «прогон без перезапуска» шлёт ТОЛЬКО текущий модуль → stale-snapshot аналог. Пример CI config.json — в отчёте агента.
- **Unit vs BDD**: server-код/алгоритмы/`ОбработкаПроведения`+`ПередЗаписью` прямым вызовом (+ проверка движений через
  `ОжидаетЧтоТаблицаБазы`) → YAxUnit; UI-сценарии (АРМ/формы/диалоги) → Vanessa. Жёсткой границы нет (эвристика).
- **Anti-patterns**: зависимость от порядка; связка с данными прод/образа; хардкод UUID/ссылок; запись в прод без
  отката; over-mocking → хрупкость; тест платформы вместо логики; нет negative/boundary; тавтологичные ассерты;
  флаки от случайных данных. Эталон-границы First Bit `ЧетноеЧисло`: `2,1,0,-1,-2,100,99`.
- Источники: [structure](https://bia-technologies.github.io/yaxunit/docs/getting-started/structure) · [test-naming](https://bia-technologies.github.io/yaxunit/docs/cook-book/test-naming) · [run.md](https://bia-technologies.github.io/yaxunit/docs/getting-started/run/) · [firstBitSportivnaya/PSSL](https://github.com/firstBitSportivnaya/PSSL) · [1cfullstack.ru](https://1cfullstack.ru/yaxunit-freymvork-modulnogo-testirovaniya-dlya-1s/) · Infostart 2434874/2595697/1976659/2418640.

## Сводка «что фолдить куда»
- **SKILL.md** (методология): корректный API (матчеры/Мокито/регистрация/дискавери), `ЮТест.Пропустить`, data-driven,
  теги, lifecycle, БД-утверждения, `&Вместо`+DI, anti-patterns, нота рек.3. Полный справочник → `references/`.
- **17.6** (глава): фикс §3/§4/§5, новая секция CI/раннеры (METR/vrunner/Coverage41C/onec-docker + config.json ключи),
  безопасный режим (подтверждён), нота рек.3, unit-vs-BDD уточнение.
- **write-1c-unit-tests.md** (команда): хирургический фикс Мокито/ОжидаетВыброс/регистрация-в-подсистеме/3-арг.
