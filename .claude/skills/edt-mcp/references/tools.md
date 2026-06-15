# EDT-MCP — полный справочник инструментов (70 tools, v2.3.1)

Источник: `DitriXNew/EDT-MCP` `docs/tools/*.md` (генерируется из живого сервера `get_tool_guide`).
За исчерпывающими примерами одного тула в рантайме: `get_tool_guide('<tool>')`.

Соглашения, общие для всех тулов:
- **FQN-адресация**: `Type.Name` (топ-объект) или `Type.Name.Kind.Name` (член). TYPE/KIND-токены **двуязычны (ru/en)**; части `Name` — **программные имена, НЕ синонимы**.
- **Текстовые vs модельные тулы**: `search_in_code` — буквальный текст (НЕ ru/en-aware); `find_references`/`go_to_definition`/`get_method_call_hierarchy`/`validate_query` — модельные (находят идентификатор в любом написании).
- **Confirm-preview гейт** (двухфазно: без `confirm` → превью без изменений, `confirm=true` → выполнить): `delete_metadata`, `rename_metadata_object`, `update_database`, `delete_project`, `delete_launch_config`, `delete_infobase`.
- `persisted=false` в ответе write-тула = правка в памяти прошла, но экспорт в `.mdo` не подтверждён — перепроверь.

---

## Core (всегда видимы)

### list_projects
- Purpose: список всех проектов воркспейса + состояние.
- Params: нет.
- Returns: Markdown-таблица — Name, State (ready/building/closed), Path, Open, EDT Project, Natures.
- Gotchas: building-проект небезопасен для чтения/записи модели — дождись ready или `clean_project`. Используй колонку Name дословно как `projectName`.

### list_modules
- Purpose: перечислить BSL-модули проекта (path, type, parent) для поиска путей перед чтением/правкой.
- Params: projectName (req); metadataType (default `all`: documents/catalogs/commonModules/informationRegisters/… unknown→ошибка со списком); objectName (Name родителя, не синоним); nameFilter (substring по ПУТИ, напр. `Forms/`); limit (200, max 1000).
- Returns: Markdown-таблица; пути src/-относительные → прямо в read/write.
- Gotchas: тип модуля выводится из имени файла (`Module.bsl` под `Forms/`→FormModule).

### read_module_source
- Purpose: прочитать BSL-модуль (весь/диапазон строк) + revision-токен `contentHash` для round-trip в write.
- Params: projectName (req); modulePath (req, src/-относительный); startLine/endLine (1-based, inclusive).
- Returns: YAML-frontmatter (`contentHash`, startLine/endLine, totalLines, при усечении `truncated:true`+`nextStartLine`) + fenced `bsl` блок чистого исходника.
- Gotchas: `contentHash` считается по ВСЕМУ файлу даже при range-чтении (write правит весь модуль). Большой файл: при `truncated:true` повторяй с `startLine=nextStartLine`. Для одного метода — `read_method_source`; для оглавления — `get_module_structure`.

### get_module_structure
- Purpose: оглавление ОДНОГО модуля — процедуры/функции с диапазонами строк, export, &AtServer/&AtClient, регион, параметры.
- Params: projectName (req); modulePath (req); includeVariables (false); includeComments (false); responseFormat (`concise` default / `detailed`).
- Returns: Markdown — счётчики, список регионов, таблица методов (#, Type, Name, Export, Context, Lines, Region [+Parameters/Description в detailed]); футер — extension-interception ссылки.
- Gotchas: один модуль; имена резолвятся в любом ru/en. `concise` намеренно без сигнатур — бери `detailed`+`includeComments=true`. Building-проект → «BSL model is not available».

### get_metadata_objects
- Purpose: плоский список объектов метаданных (Markdown-таблица) для discovery.
- Params: projectName (req); metadataType (default `all`: documents/catalogs/informationRegisters/accumulationRegisters/commonModules/enums/constants/reports/dataProcessors/exchangePlans/businessProcesses/tasks/commonAttributes/eventSubscriptions/scheduledJobs); nameFilter (substring по Name); limit (100, max 1000); language (код синонима en/ru).
- Returns: Markdown — Name, Synonym, Comment, Type, ObjectModule, ManagerModule + Total.
- Gotchas: nameFilter по программному Name, не синониму. Дальше — `get_metadata_details`.

### get_metadata_details
- Purpose: подробные свойства одного/нескольких объектов (basic / `full`); рендерит и структуру формы, и схему присваиваемых свойств.
- Params: projectName (req); objectFqns (req, массив `Type.Name`); full (false — все секции); assignable (false — вернуть СХЕМУ settable-свойств: вид значения/текущее/ДОПУСТИМЫЕ enum-литералы; FQN может адресовать член); language.
- Returns: Markdown, секция на объект через `---`; ошибки по объектам — в хвостовой `## Errors` (не валит весь вызов).
- Gotchas: FQN формы (`Catalog.X.Form.ItemForm`/`CommonForm.Name`) рендерит СТРУКТУРУ формы. `assignable:true` — обязательный шаг перед `modify_metadata` (узнать имена свойств + допустимые значения).

### search_in_code
- Purpose: буквальный/regex полнотекстовый поиск по всем `.bsl` под src/.
- Params: projectName (req); query (req); isRegex (false, Java regex); caseSensitive (false); limit (100, max 500); contextLines (2, max 5; full); fileMask (substring пути); metadataType (фильтр по папке-семейству); outputMode (`full`/`count`/`files`).
- Returns: full=матчи+контекст по файлам; count=итоги; files=кол-во на файл.
- Gotchas: **НЕ ru/en-aware** — англ. `Procedure` не найдёт `Процедура`. Матч однострочный. Только `.bsl` (не формы/XML). Для идентификаторов — `find_references`/`get_symbol_info`/`get_method_call_hierarchy`.

### get_edt_version
- Purpose: версия запущенного 1C:EDT (liveness-check).
- Params: нет.
- Returns: строка вида `2025.2.6.4`, либо «Unknown».
- Gotchas: для порта/протокола/версии плагина/счётчиков — `get_server_status`.

### get_server_status
- Purpose: самодиагностика сервера (порт, версии, счётчики тулов, render/preference-флаги).
- Params: нет.
- Returns: JSON — port, running, protocolVersion, pluginVersion, edtVersion, enabledTools/totalTools, plainTextMode, checksFolderConfigured, authEnabled, formRenderFlags{nativeFormBufferedLayoutRender, nativeFormLayoutRender}.
- Gotchas: объясняет пустой скрин формы (флаг рендера) и plainText-ответы. enabledTools<totalTools — норма при progressive disclosure.

### list_toolsets
- Purpose: список тулсет-групп (progressive disclosure) + видимость в tools/list.
- Params: нет.
- Returns: JSON — progressiveDisclosure(on/off), toolsets[]{id,title,description,tools,toolCount,visible,core}.
- Gotchas: при OFF (дефолт) все видимы (enable нечего делать). `core` всегда видим.

### enable_toolset
- Purpose: показать/скрыть тулсет-группы.
- Params: toolsets (req, массив id из list_toolsets, напр. ["code","debug"]); disable (false=показать, true=скрыть).
- Returns: JSON — action, applied, invalid, ignored(core), visibleToolsets, progressiveDisclosure.
- Gotchas: **после показа ОБЯЗАТЕЛЬНО переснять `tools/list`** (иначе новые тулы не видны; по открытому SSE прилетает `notifications/tools/list_changed`). При OFF — записывается, но эффект только если disclosure включён в EDT Preferences → MCP Server.

### get_tool_guide
- Purpose: полный how-to тула (описание, все параметры с типами/допустимыми значениями, расширенные примеры).
- Params: toolName (req, точное имя из tools/list).
- Returns: текст гайда (= ресурс `guide://<toolName>`).
- Gotchas: неизвестное имя → ошибка с отсылкой к tools/list.

---

## Code (BSL: правка/чтение/навигация)

### write_module_source
- Purpose: записать BSL в ОДИН модуль — хирургический фрагмент / замена файла / append; перед записью проверка баланса ключевых слов.
- Params: projectName (req); source (req, ≤500000 символов; `\r\n`→`\n`, файл всегда оканчивается newline). **modulePath XOR objectName** (ровно ОДИН): modulePath=src/-относительный `.bsl`; objectName=`Type.Name` + moduleType. moduleType (только с objectName): `ObjectModule`(default)/`ManagerModule`/`FormModule`/`CommandModule`/`RecordSetModule`/`Module`. mode: `searchReplace`(default)/`replace`/`append`. oldSource (req для searchReplace, должен матчиться РОВНО один раз). formName (req для FormModule, кроме CommonForm). commandName (req для CommandModule, кроме CommonCommand). expectedHash (contentHash из read — guard потерянного апдейта для ЛЮБОГО mode). expectedSource (полный прошлый контент — guard для mode=replace). overwrite (bool). skipSyntaxCheck (false).
- Returns: результат записи; при синтакс-ошибке запись БЛОКИРУЕТСЯ; при mismatch guard — отказ.
- Gotchas: `searchReplace`/`append` требуют СУЩЕСТВУЮЩИЙ файл; создать модуль может ТОЛЬКО `replace` (+ создаёт папки). `replace` поверх существующего без expectedHash/expectedSource/overwrite — отказ. `oldSource` с 0 или >1 совпадений — отказ (читай заново / бери больший фрагмент). Резолв по программному Name; двуязычен только TYPE-токен. Перехват метода в расширении = обычный аннотированный BSL (`&Before`/`&After`/`&Around`/`&ChangeAndValidate`) verbatim, но host-модуль расширения должен уже существовать.

### read_method_source
- Purpose: прочитать одну процедуру/функцию по имени (исходник + метаданные); при отсутствии — список доступных методов.
- Params: projectName (req); FQN/objectName + methodName (см. get_tool_guide). Возврат — исходник метода. Для всего модуля — read_module_source.

### find_references
- Purpose: все ИСПОЛЬЗОВАНИЯ объекта по конфигурации — BSL (с номерами строк), метаданные, формы, роли, подсистемы, предопределённые.
- Params: projectName (req); objectFqn (req, `Type.Name`); limit (100, max 500 — кап ОБЩИЙ, не по категориям).
- Returns: Markdown, сгруппировано по категориям.
- Gotchas: модельный (любое ru/en написание), резолв по Name. Truncation → подними limit. Обратное — go_to_definition; граф вызовов метода — get_method_call_hierarchy.

### go_to_definition
- Purpose: где ОПРЕДЕЛЁН символ (обратное к find_references) — локация, сигнатура, регион, опц. тело.
- Params: projectName (req); symbol (req: `ModuleName.MethodName` / голый `MethodName`+modulePath / FQN `Type.Name`); modulePath (req для голого имени метода); includeSource (true).
- Returns: YAML-frontmatter + опц. fenced bsl.
- Gotchas: голое имя без modulePath — отказ. `ModuleName.MethodName` резолвит только методы ОБЩИХ модулей; для объектных/менеджер/формных — голое имя+modulePath. Порядок 2-частей: общий модуль → потом FQN.

### get_method_call_hierarchy
- Purpose: граф вызовов метода в одну сторону — кто вызывает (callers) / что вызывает (callees) через семантический AST.
- Params: projectName (req); modulePath (req, модуль ОПРЕДЕЛЕНИЯ); methodName (req); direction (`callers` default / `callees`); limit (100, max 500).
- Returns: Markdown-таблица.
- Gotchas: ru/en-aware (лучше search_in_code для идентификаторов). modulePath должен указывать на ОПРЕДЕЛЯЮЩИЙ модуль. callees не резолвит вызываемые до их модулей.

### get_symbol_info
- Purpose: hover «что это?» в позиции — выведенные типы, сигнатура, документация.
- Params: projectName (req); modulePath (alias filePath); line (req), column (req) — 1-based, на идентификатор.
- Returns: Markdown (как EDT hover).
- Gotchas: позиции бери из get_module_structure / read_module_source-frontmatter / search_in_code.

### get_content_assist
- Purpose: автодополнение в 1-based каретке (члены, глобальные, локальные — напр. после `.`).
- Params: projectName (req); modulePath (alias filePath); line (req), column (req, каретка слева от символа; для `Object.` ставь на 1 правее точки); limit (100, max 1000); offset (0); contains (CSV substring-фильтр); extendedDocumentation (false).
- Returns: JSON {totalProposals, returnedProposals, proposals:[{displayString[, documentation]}]}.
- Gotchas: «Xtext editor not ready … retry» на холодном вызове — повтори. `contains` — буквальный, не ru/en-aware.

### validate_query
- Purpose: валидация текста запроса 1С (QL) против метаданных проекта — синтаксис+семантика с номерами строк (ничего не пишет/не выполняет).
- Params: projectName (req); queryText (req; параметры `&X` допустимы без привязки); dcsMode (false; true только для запросов СКД).
- Returns: JSON {valid, errorCount, warningCount, issues:[{severity, message, line, column, offset}]}.
- Gotchas: `success:true` = тул отработал; смотри `valid`. Двуязычно (ключевые слова/типы en/ru). Поле, которого нет в ЭТОМ проекте — семантическая ошибка.

### get_platform_documentation
- Purpose: документация API платформы для встроенных типов (ValueTable/Array/Structure) и глобальных функций.
- Params: typeName (req, en/ru); category (`type` default / `builtin`); memberName (фильтр); memberType (`method`/`property`/`constructor`/`event`/`all`); projectName (пин версии); limit (50, max 200); language (en/ru — только вывод); responseFormat (`concise`/`detailed`).
- Returns: Markdown — Type Info + члены.
- Gotchas: это API ПЛАТФОРМЫ, не метаданные конфигурации. `concise` для инвентаря → `detailed` для сигнатур.

---

## Metadata (объекты: discovery / CRUD / подсистемы / конфигурация)

### create_metadata
- Purpose: создать узел метаданных по FQN — топ-объект (`Catalog.Products`) или член (`Catalog.Products.Attribute.Weight`, `InformationRegister.Prices.Dimension.Product`, `Enum.Colors.EnumValue.Red`). Вид выводится из FQN. Заменяет старые create_metadata_object/add_metadata_attribute.
- Params: projectName (req); fqn (req); properties (массив `[{name,value,language?}]` — на создании только `synonym`/`comment`; остальное через modify_metadata); expectedNotExists (false); normalizeYo (true — `ё`→`е` в Name/synonym/comment, иначе нарушение стандарта `mdo-ru-name-unallowed-letter`); setAsDefault (форма-ОБЪЕКТ: сделать формой по умолчанию); callType (Before/After/Instead — перехват события формы в РАСШИРЕНИИ); commonModuleKind (Server/ServerCall/ClientManaged/ClientOrdinary/ClientServer/Global — для CommonModule); serverCall/privileged/returnValuesReuse (CommonModule); targetNamespace (XDTOPackage).
- Returns: JSON — action='created', нормализованный fqn, kind (EClass), name, persisted, эхо synonym/language/callType.
- Особое — **формы**: форма-объект `Catalog.X.Form.FormName` (4 части, токен `Form/Forms/Форма/Формы`) создаёт MD-форму + рендерящийся пустой `Form.form` (с autoCommandBar). Содержимое формы — члены `…Form.F.<Kind>.Name` (Attribute/Command/Group/Decoration/Field/Button); Field привязывается через `dataPath`, Button через `command`. Обработчик события — `…Form.F.Handler.<Event>` (или item-level `…Field.Price.Handler.OnChange`); имя события резолвится в любом ru/en (`OnOpen`/`ПриОткрытии`); имя процедуры — свойство `procedure`.
- **Перехват события в расширении**: форма должна быть ADOPTED; адресуй FQN обработчика item + `callType` (Before/After/Instead [=Override на диске]); пишет `form:EventHandlerExtension`, СОСУЩЕСТВУЕТ с базовым обработчиком; саму BSL-процедуру добавляй `write_module_source`.
- Gotchas: дубликат FQN — отказ. Члены создаются с ДЕФОЛТНЫМИ свойствами (правь modify_metadata). НЕ confirm-gated (обратимо через delete_metadata).

### modify_metadata
- Purpose: задать присваиваемые свойства узла (топ-объект ИЛИ член, включая item/attribute/command формы); также move/reorder item формы, переназначить handler/button, задать значение StyleItem.
- Params: projectName (req); fqn (req); properties (req, `[{name,value,language?}]`, ≥1); normalizeYo (true).
- Returns: JSON — action='modified', нормализованный fqn, applied, persisted; move также возвращает destination.
- Gotchas: НЕ confirm-gated и БЕЗ undo — откат вызовом с прежним значением (прочитай через get_metadata_details). Rename здесь ЗАПРЕЩЁН → rename_metadata_object. Settable-свойства + допустимые enum-литералы — через get_metadata_details(assignable:true); либо всё валидно, либо НИЧЕГО не пишется.
  - Структурные значения: `type` → `{types:[{kind,...}]}` (String/Number/Boolean/Date с квалификаторами; ref `{kind:'Ref',ref:'Type.Name'}`, составной = несколько). Один ref → `value:'Type.Name'`; СПИСОК ref (напр. Subsystem `content`) → `value:['Type.Name',...]` ЗАМЕНЯЕТ весь список (`[]` чистит). StyleItem → `{color:{red,green,blue}}`/`{color:'auto'}` ЛИБО `{font:{...}}`.
  - FQN члена формы: `Catalog.X.Form.F.<Kind>.Name`; `type` контекстно-зависим (Attribute = valueType `{types:[...]}`; Field/Button/Decoration = display-kind ENUM). `id` item-а задать нельзя.
  - Переназначить обработчик: FQN существующего Handler + свойство `procedure` (только переуказание). Перепривязать кнопку: Button FQN + `command` (существующая команда формы; нельзя комбинировать).
  - Move/reorder: `parent` (контейнер/группа, `AutoCommandBar`/`MyTable.AutoCommandBar`, имя формы/"" для корня) и/или `position` (`first`/`last`/`before:<name>`/`after:<name>`/индекс). Move структурный — НЕЛЬЗЯ совмещать с обычными правками свойств (сначала move, потом modify).

### rename_metadata_object
- Purpose: переименовать объект или член (Attribute/TabularSection/Dimension/Resource) с каскадом по BSL/формам/метаданным (LTK).
- Params: projectName (req); objectFqn (req); newName (req, только Name, синонимы не трогает); confirm (false=превью); disableIndices (CSV `#`-индексов ОПЦИОНАЛЬНЫХ точек для пропуска, напр. `'2,3,5'`); maxResults (20, 0=без лимита).
- Returns: превью → таблица точек изменения (`#`, файл/локация, Optional, Enabled-by-default); execute → применяет по ТЕМ ЖЕ `#`.
- Gotchas: двухфазно; `#`-индекс стабилен между превью/execute — читай disableIndices из СВЕЖЕГО превью. disableIndices игнорируется для обязательных точек. Каскад + трудно откатить — на ревёртируемой конфиге, после — get_project_errors.

### delete_metadata
- Purpose: удалить узел (топ-объект, член, форма-объект, член формы) по FQN с каскадной очисткой ссылок в BSL/формах/метаданных.
- Params: projectName (req); fqn (req); confirm (false=превью); force (false; true=удалить даже при неавтоочищаемых входящих metadata-ссылках, оставив dangling).
- Returns: превью → заголовок/items + `blocking`/`blockingReferences`/`blockingReferencesCount`; execute → action='executed' или 'blocked'.
- Gotchas: `confirm` (гейт) и `force` (override ссылок) независимы. BSL/form-привязки автоочищаются и НЕ блокируют; metadata-ссылки (напр. Catalog как тип реквизита) БЛОКИРУЮТ confirm=true без force. Член формы БЕЗ каскада — кросс-ссылки (dataPath/command) не переписываются, перепроверь get_metadata_details.

### adopt_metadata_object
- Purpose: «принять» объект/член базовой конфигурации в РАСШИРЕНИЕ (EDT 'Add To Extension'), чтобы расширение могло переопределять/перехватывать. BSL-методы НЕ покрывает.
- Params: projectName (req, БАЗОВАЯ конфигурация-владелец, не расширение); fqn (req); extensionProjectName (req только если расширений >1).
- Returns: JSON — action('adopted'/'alreadyAdopted'), fqn, extensionProject, objectBelonging='ADOPTED', persisted.
- Gotchas: только МЕТАДАННЫЕ (перехват BSL-метода — `&Before/&After/&Around/&ChangeAndValidate` через write_module_source). Принятие члена неявно принимает и владельца. Откат — delete_metadata против расширения. После — get_project_errors на расширении.

### get_configuration_properties
- Purpose: свойства верхнего уровня конфигурации/расширения.
- Params: projectName (опц.; пусто = первый config-проект).
- Returns: YAML — name, synonym, comment, scriptVariant, compatibilityMode, defaultLanguage, vendor, version и др.
- Gotchas: `defaultLanguage` — код (ru/en), которым ключуется каждый синоним (важно когда синоним пуст).

### list_subsystems
- Purpose: подсистемы конфигурации плоской таблицей; карта дерева.
- Params: projectName (req); nameFilter (substring по Name); recursive (true); limit (100, max 1000); language.
- Returns: Markdown — FQN, Synonym, Comment, InCommandInterface, content count, children count.
- Gotchas: FQN вложен: `Subsystem.Sales.Subsystem.Orders` → в get_subsystem_content.

### get_subsystem_content
- Purpose: одна подсистема детально — свойства, объекты, дочерние подсистемы.
- Params: projectName (req); subsystemFqn (req); recursive (false — вложить объекты дочерних); language.
- Returns: Markdown — Properties / Content (Type/Name/Synonym/FQN) / Child Subsystems.

### get_tags
- Purpose: список пользовательских тегов проекта (оверлей EDT-MCP, НЕ часть метаданных 1С).
- Params: projectName (req).
- Returns: Markdown — #, Name, Color, Description, Objects(count).

### get_objects_by_tags
- Purpose: объекты с любым из заданных тегов (union).
- Params: projectName (req); tags (req, точные имена); limit (100, max 1000).
- Returns: Markdown, сгруппировано по тегу (FQN объектов); неизвестные — под «Tags not found».
- Gotchas: точное совпадение имени — бери из get_tags. FQN → в get_metadata_details/go_to_definition.

---

## Debug (отладка: launch/attach, BP, step/resume, variables, eval)

> В этом проекте для живого BP-trace по умолчанию используется skill `1c-debug-hmr` (RDBG). Debug-тулы EDT-MCP — альтернатива внутри EDT; для серверного кода нужен Attach-конфиг.

### debug_launch
- Purpose: стартовать debug-сессию EDT: существующий конфиг по launchConfigurationName (runtime client ИЛИ Attach — Attach нужен для серверного кода), или runtime-client по projectName+applicationId.
- Params: launchConfigurationName (точное имя; единственный режим для Attach) ЛИБО projectName+applicationId; updateBeforeLaunch (true — тихий апдейт БД до запуска, авто-подтверждает модалку обновления в любой локали; Attach игнорирует); restartIfRunning (false=short-circuit `alreadyRunning:true`; true=неинтерактивно убить старую КЛИЕНТСКУЮ сессию и перезапустить).
- Returns: JSON — launchConfiguration, configurationType, attach, mode, status:"launching" (асинхронно); либо `alreadyRunning:true`.
- Gotchas: Attach достижим ТОЛЬКО через launchConfigurationName. `alreadyRunning:true` — успех, не ретраить. Запуск асинхронный — поллируй debug_status, потом wait_for_break; ошибка запуска уходит в EDT error log, не в ответ. Запуск клиента ПОВЕРХ уже работающего debug-сервера того же приложения — разрешён.

### debug_status
- Purpose: активные debug-сессии: applicationId (реальный/`attach:<name>`/`launch:<name>`), конфиг, mode, suspended, threadCount, строка верхнего кадра; плюс debugServerTargets (`ServerApplication.<app>`).
- Params: applicationId (опц. фильтр).
- Returns: JSON — launches[]; count; registry. «Где я?» для сессии.
- Gotchas: только EDT/1C-запуски. Для attach без appId используй `attach:<configName>` как applicationId.

### set_breakpoint
- Purpose: line-BP на BSL-модуле.
- Params: modulePath (req, EDT-путь `CommonModules/Foo/Module.bsl` или абсолютный `.bsl`); lineNumber (req, 1-based); projectName (req когда modulePath — EDT-путь).
- Returns: JSON {breakpointId, modulePath, resolvedFile, lineNumber}; `degraded:true`+warning при marker-only.
- Gotchas: `degraded:true` = может НЕ остановить (проверь в EDT Breakpoints view). Полезен только с debug-сессией. Building-проект → ошибка.

### remove_breakpoint
- Purpose: снять BP.
- Params: breakpointId (надёжнее) ЛИБО projectName+modulePath+lineNumber.
- Returns: JSON {removed: true|false}.
- Gotchas: `removed:false` — не ошибка. Восстанови id через list_breakpoints.

### list_breakpoints
- Purpose: активные line-BP, опц. по проекту.
- Params: projectName (опц.).
- Returns: JSON {breakpoints:[{breakpointId, project, file, lineNumber, enabled, modelId}], count}.
- Gotchas: `modelId` = 1C BSL модель → реальный suspend-capable BP (vs degraded marker-only).

### wait_for_break
- Purpose: блокироваться до suspend (BP hit) и вернуть снимок thread/frame.
- Params: applicationId (опц. если активна одна сессия; принимает любой id-формат, в т.ч. `ServerApplication.<app>`); timeout (60, max 600).
- Returns: hit → JSON {hit:true, threadId, threadName, frames:[{frameIndex, frameRef, name, line, modulePath, project}], topFrameRef}; timeout → {hit:false, reason:"timeout"}.
- Gotchas: храни `frameRef`/`topFrameRef` для get_variables/evaluate_expression; `threadId` для step/resume. На timeout launch не убивается — зови снова.

### get_variables
- Purpose: переменные кадра приостановленного потока.
- Params: frameRef (предпочтительно, из wait_for_break/step) ЛИБО threadId+frameIndex (0-based); ни то ни другое → верхний кадр единственной сессии; expandPath (точечный путь вглубь Структуры/Соответствия/Массива).
- Returns: JSON {variables:[{name, value, type}], count}; длинные значения усечены.
- Gotchas: `frameRef` протухает после КАЖДОГО step/resume — бери свежайший. Для произвольного BSL — evaluate_expression.

### evaluate_expression
- Purpose: вычислить BSL-выражение в области приостановленного кадра (watch/immediate).
- Params: frameRef (req); expression (req).
- Returns: JSON {type, value}; длинное → truncated:true+fullLength.
- Gotchas: исполняет ПРОИЗВОЛЬНЫЙ BSL — возможны side-effects. frameRef протухает после step/resume. Короткий timeout. Для чистого чтения — get_variables.

### step
- Purpose: шаг приостановленного потока (over/into/out), блокирует до новой остановки.
- Params: threadId (req); kind (req: `over`/`into`/`out`); timeout (30, max 600).
- Returns: как wait_for_break (свежие frameRef/topFrameRef).
- Gotchas: frameRef меняются после каждого шага. «stale threadId» → wait_for_break заново. Невозможный шаг (`out` на верхнем кадре) → ясная ошибка.

### resume
- Purpose: продолжить поток или все потоки таргета.
- Params: threadId (один поток) ЛИБО applicationId (все потоки таргета; любой id-формат); без аргументов → авто-резолв единственной сессии.
- Returns: JSON {resumed:true, scope:"thread"|"target", applicationId, autoResolved}.
- Gotchas: 1С резюмит на уровне потока. После resume — wait_for_break для следующей остановки.

### terminate_launch
- Purpose: завершить/отсоединить запуски ЭТОГО EDT (внешние клиенты не трогает).
- Params: ровно ОДИН режим: launchConfigurationName ЛИБО projectName+applicationId ЛИБО all=true (требует confirm=true); force (false; эскалация до OS-kill, может потерять несохранённое, Attach игнорирует); timeout (10, [1,120]); includeAttach (true).
- Returns: код на запуск ∈ terminated/force_terminated/detached/timeout/already_terminated/error + отчёт о чистке реестра.
- Gotchas: Attach ОТСОЕДИНЯЕТСЯ, не убивается (сервер/rphost живёт, `detached`). Ничего не совпало → `not_found` (не ошибка). timeout на runtime → ретрай с force=true.

### get_applications
- Purpose: приложения (инфобазы) проекта с id/name/type/updateState; applicationId → update_database/debug_launch/profiling.
- Params: projectName (req).
- Returns: JSON {applications:[{id, name, type, updateState (UPDATED/INCREMENTAL_UPDATE_REQUIRED/FULL_UPDATE_REQUIRED), updateStateDescription, requiredVersion?}], count, defaultApplicationId}.
- Gotchas: updateState≠UPDATED → схема отстаёт, сначала update_database. Building-проект → отказ.

---

## Testing (YAXUnit)

### run_yaxunit_tests
- Purpose: прогнать YAXUnit и вернуть JUnit-Markdown; с debug=true — DEBUG-режим (BP срабатывают).
- Params: launchConfigurationName (предпочтительно) ЛИБО projectName+applicationId; фильтры extensions/modules/tests (Module.Method; CSV или массив, AND); timeout (60; истёк → **Pending**); updateBeforeLaunch (true — recompute проекта+расширений, sweep клиента, тихий апдейт, отказ при рассинхроне; false — legacy, может прогнать stale расширение); updateScope (`all`/`configuration`/`extension:<Name>`); debug (false=poll+report; true=DEBUG, игнорит timeout, сразу возвращает handle → wait_for_break).
- Returns: Markdown JUnit (+ `report.md` рядом с `junit.xml`); при истечении окна — **Pending** (запуск НЕ убит); debug=true → launch handle.
- Gotchas: при Pending повтори с ИДЕНТИЧНЫМИ аргументами (re-attach по run-key=config+фильтр); готовый результат отдаётся matching-вызову ОДИН раз, потом identical-вызовы запускают заново. Debug-цикл: `set_breakpoint → run_yaxunit_tests(debug=true) → wait_for_break → get_variables/evaluate_expression/step → resume`; пин ОДНОГО `tests` чтобы сработал ровно один BP. Нужен runtime-client конфиг + установленный YAXUnit.

### debug_yaxunit_tests
- Purpose: **deprecated** алиас `run_yaxunit_tests(debug=true)`. Предпочитай run_yaxunit_tests(debug=true).
- Params: как run_yaxunit_tests минус timeout. Возвращает launch handle → wait_for_break.

---

## Profiling

### start_profiling
- Purpose: включить line-level замер (счётчики вызовов+тайминг, = покрытие) на активной DEBUG-сессии.
- Params: applicationId (req, работающая DEBUG-сессия).
- Returns: JSON {active, started, applicationId, message}.
- Gotchas: нужна DEBUG-сессия (не run). Идемпотентно (повтор → «already active»). Данные видны только после stop_profiling + get_profiling_results.

### stop_profiling
- Purpose: остановить замер, финализировать сбор.
- Params: applicationId (req).
- Returns: JSON {active:false, stopped, applicationId, message}.
- Gotchas: идемпотентно. Дальше — get_profiling_results.

### get_profiling_results
- Purpose: последний замер — per-module/per-line вызовы, тайминг, %.
- Params: moduleFilter (substring); minFrequency (≥N вызовов, 1); applicationId; responseFormat (`concise`/`detailed` — добавляет код, сигнатуру, dur/pureDur).
- Returns: JSON {count(0|1), profilingActive, results:[{name, totalDurability, modules:{module→[lines]}}]}; кап 200 строк/модуль.
- Gotchas: только САМЫЙ свежий сеанс. Пусто → start_profiling не звали / не финализировано (stop_profiling). При кап-200 — сузь moduleFilter/minFrequency.

---

## Forms (WYSIWYG-рендер)

> Оба тула требуют запуск EDT с JVM-флагом `-DnativeFormBufferedLayoutRender=true` (в `1cedt.ini` секция `-vmargs`), иначе результат пустой. Это НЕ ошибка вызова — добавь флаг и перезапусти EDT.

### get_form_screenshot
- Purpose: PNG-скрин WYSIWYG-редактора формы.
- Params: formPath (FQN `Catalog.Products.Forms.ItemForm`/`CommonForm.MyForm`; пусто = активный редактор); projectName (req когда задан formPath); refresh (false=форс ре-рендер).
- Returns: IMAGE (PNG), файл по имени последнего сегмента FQN.
- Gotchas: без JVM-флага — пусто (не ретраить/не менять аргументы — добавь флаг). formPath без projectName — отказ. Нужен живой workbench Display (не headless).

### get_form_layout_snapshot
- Purpose: YAML-снимок рассчитанной раскладки (bounds x/y/w/h, типы элементов, display-свойства, размер формы) как ТЕКСТ.
- Params: formPath (FQN; пусто=активный); projectName (req когда задан formPath); refresh (true); mode (`compact` default / `full`).
- Returns: TEXT (YAML).
- Gotchas: тот же JVM-флаг. «No calculated element bounds» = форма не дорендерилась → retry/refresh=true. Для PNG — get_form_screenshot.

---

## Translation (LanguageTool)

> Требует установленный LanguageTool в EDT (не входит в комплект).

### generate_translation_strings
- Purpose: сгенерить строки перевода (.lstr/.trans/.dict) — скан переводимых фич, запись ключей в хранилища.
- Params: projectName (req, configuration-проект, НЕ dictionary storage/extension); targetLanguages (req, массив кодов); storageId (default "edit:default"); collectInterface (true); collectModel (true); collectModelType (ANY/NONE/COMPUTED_ONLY/UNKNOWN_ONLY/TAGS_ONLY); fillUpType (NOT_FILLUP/FROM_SOURCE_LANGUAGE/FROM_PROVIDER); providerId (req только при FROM_PROVIDER).
- Returns: Markdown-сводка.
- Gotchas: частая ошибка — не тот тип проекта (запускай на configuration, не на dictionary storage/extension).

### translate_configuration
- Purpose: EDT 'Translate configuration' — читает словари из привязанных хранилищ, регенерит перевод.
- Params: projectName (req, обычно source-конфиг, напр. ru); targetLanguages (req).
- Returns: Markdown + YAML-frontmatter.
- Gotchas: нужны привязанные словари (нечего привязано — нечего переводить). Setup смотри get_translation_project_info.

### get_translation_project_info
- Purpose: LanguageTool-метаданные проекта — хранилища переводов + доступные provider id.
- Params: projectName (req).
- Returns: Markdown — Storages + Translation providers (+ counts). Примеры storageId: edit:default, dictionary:common-camelcase, context:model.
- Gotchas: пустые Storages = словарь не привязан (настраивается в EDT вручную: обычный Eclipse-проект + привязка; НЕ через мастер 'Dependent translation project').

---

## Project (clean/revalidate, БД, XML, проблемы, инфобазы/конфиги)

### update_database
- Purpose: применить изменения конфигурации к инфобазе приложения (полное/инкрементальное) — «Обновить конфигурацию БД».
- Params: launchConfigurationName (предпочтительно; Attach отклоняется) ЛИБО projectName+applicationId; confirm (false=превью/резолв таргета без мутации, true=применить); fullUpdate (false=инкремент, true=полная перезагрузка); terminateRunningClients (true=убить клиента ЭТОГО EDT для эксклюзивного лока).
- Returns: JSON — updateType (FULL/INCREMENTAL), stateBefore, stateAfter (успех=UPDATED), terminatedClient, message.
- Gotchas: деструктивно/необратимо — confirm-gated, только по явному запросу пользователя. Реструктуризацию БД авто-подтвердить нельзя (EDT покажет диалог; если stateAfter≠UPDATED — подтверди в UI или fullUpdate=true). На standalone-server (`applicationId` начинается с `ServerApplication.`) ЗАПУСКАЕТ сервер в RUN-режиме — лучше доверь это debug_launch/run_yaxunit_tests(updateBeforeLaunch=true). BEING_UPDATED → ошибка, подожди.

### clean_project
- Purpose: полная пересборка+ревалидация проекта (refresh с диска, сброс маркеров, ждёт завершения).
- Params: projectName (опц.; пусто = все проекты).
- Returns: JSON — success, projectsCleaned, projects, message (возврат ПОСЛЕ завершения, до ~3 мин/проект).
- Gotchas: НЕ деструктивно, но **отбрасывает несохранённые in-memory правки модели** (пересчёт с диска) — сохрани раньше. Building-проект → отказ. Тяжёлое; легче — revalidate_objects.

### revalidate_objects
- Purpose: ре-валидация всего проекта или конкретных объектов (refresh с диска).
- Params: projectName (req); objects (массив FQN; пусто/нет = весь проект).
- Returns: Markdown + YAML-frontmatter (status, mode, counts) + секции Validated/Not found/Skipped.
- Gotchas: full-режим = инкрементальная сборка (тяжело на больших). Результат — get_problem_summary/get_project_errors. Для застрявшего состояния — clean_project.

### resync_to_disk
- Purpose: bulk ре-синк in-memory BM-модели на диск (src/.mdo), восстановить пропавшие файлы; отчёт/удаление dangling-ссылок в Configuration.mdo.
- Params: projectName (req); cleanDanglingReferences (false=report-only; true=УДАЛИТЬ orphan-прокси, деструктивно — переписывает Configuration.mdo); fullExport (false=только пропавшие; true=все, медленно); revalidate (false; true=полная сборка после).
- Returns: JSON — objectsExported, missingBefore/stillMissing, danglingFound/danglingDetails{field,lostFqn,position}, danglingRemoved, message.
- Gotchas: лечит «object file does not exist» (update_database/XML-import) и `md-reference-intergrity`. Идемпотентно. cleanDanglingReferences=true деструктивно — сначала report-only, проверь danglingDetails.

### get_project_errors
- Purpose: детальный список маркеров валидации (per-marker) с фильтрами; BSL-проблемы несут Module+Line.
- Params: projectName (пусто=все); severity (ERRORS/BLOCKER/CRITICAL/MAJOR/MINOR/TRIVIAL/NONE — точное, не >=); checkId (substring/символьный/короткий UID `SU23`); objects (массив FQN, substring); limit (100, max 1000); responseFormat (`concise`/`detailed`).
- Returns: Markdown — Description | Location | Module path | Line | Check code.
- Gotchas: для счётчиков — get_problem_summary. severity точное. Короткие FQN over-match — давай полный Type.Name. Неразрешённые маркеры → clean_project/revalidate_objects.

### get_problem_summary
- Purpose: счётчики проблем по проекту и severity.
- Params: projectName (пусто=все).
- Returns: Markdown — Overall Totals + By Project (если >1) + «No problems found».
- Gotchas: только счётчики; детали — get_project_errors, закладки/задачи — get_markers.

### get_markers
- Purpose: закладки и/или задачи (TODO/FIXME/XXX/HACK) воркспейса.
- Params: markerKind (bookmark/task; пусто=оба); projectName; filePath (substring); priority (high/normal/low — только task); limit (100, max 1000).
- Returns: Markdown — Kind, Type, Priority, Message, Path, Line.
- Gotchas: для проблем валидации — get_project_errors. (Заменил старые get_bookmarks/get_tasks из 1.x.)

### get_check_description
- Purpose: полное описание EDT-проверки по id (объяснение, примеры, как чинить).
- Params: checkId (req, символьный `begin-transaction` ИЛИ короткий UID `SU23`); projectName (нужен только для резолва короткого UID).
- Returns: Markdown-документация проверки.
- Gotchas: нужна папка check-descriptions в EDT Preferences → MCP Server. Для UID добавь projectName.

### export_configuration_to_xml
- Purpose: экспорт конфигурации в каталог XML (= DumpConfigToFiles).
- Params: projectName (req); outputPath (req, каталог; создаётся; ошибка если путь — файл).
- Returns: Markdown + YAML-frontmatter; флаг `outsideWorkspace` если вне воркспейса.
- Gotchas: пишет в ФС (можно вне воркспейса) — проверь outputPath. Нужен плагин `com._1c.g5.v8.dt.cli.api`. Обратное — import_configuration_from_xml.

### import_configuration_from_xml
- Purpose: импорт конфигурации из каталога XML в НОВЫЙ EDT-проект.
- Params: importPath (req, КАТАЛОГ XML, существующий); projectName (req, НОВЫЙ, не должен существовать); projectNature (опц., пусто=авто); xmlVersion (опц., пусто=авто).
- Returns: Markdown — имя проекта + нормализованный путь.
- Gotchas: проект НОВЫЙ (существующее имя — отказ). importPath = каталог, не один .xml. Нужен плагин `com._1c.g5.v8.dt.cli.api`.

### create_project
- Purpose: создать новый 1С-проект в воркспейсе.
- Params: projectKind (req: `configuration`/`extension`/`externalObjects`); name (req, валидный 1С-идентификатор); projectName (опц.; default extension→`<base>.<name>`); version (`8.3.27`, config/externalObjects); baseProjectName (req для extension); prefix (extension); synonym/comment; purpose (Customization/AddOn/Patch, extension); compatibilityMode (extension); scriptVariant (Russian default/English; extension отклоняет); standardChecks/commonChecks (true, только при установленном com.e1c.v8codestyle).
- Returns: JSON с результатом + codestyle-нотами.
- Gotchas: имя должно быть новым. extension: база = конфигурация, не расширение. После создания дождись `state=ready` перед adopt_metadata_object.

### create_infobase
- Purpose: создать FILE-инфобазу ИЛИ зарегистрировать существующую и привязать к config-проекту (появится в get_applications).
- Params: projectName (req); mode (`create` default — новая, нужен зарег. рантайм платформы; `register` — существующая по infobaseFile, без запуска платформы); infobaseFile (req, абсолютный путь к КАТАЛОГУ); infobaseName (опц.); platform (`8.3.25`, create); setDefault (false); applicationKind (`infobase` default / `standaloneServer` — автономный сервер с web URL для HTTP-тестов, нужен рантайм ≥8.3.23; порт авто, в ответе `port`/`webUrl`).
- Returns: JSON — action(created/registered), applications, applicationId (для update_database), message.
- Gotchas: FILE-only (server/web отклоняются). create без зарег. платформы → ошибка (юзай register). Фоновый Job до 120с. Новая ИБ пустая → update_database. Для standalone-server грузи конфиг через debug_launch/run_yaxunit_tests(updateBeforeLaunch=true), НЕ голым update_database (тот стартует сервер в RUN).

### delete_infobase
- Purpose: убрать привязку FILE-инфобазы ИЛИ удалить standalone-server приложение (обратное create_infobase).
- Params: projectName (req); applicationId ЛИБО infobaseName (одно из); deleteRegistration (true — также дерегистрация из EDT Infobases / чистка infobases.yaml); confirm (false=превью).
- Returns: JSON — action(preview/deleted), applicationKind, message.
- Gotchas: confirm-gated. Файлы инфобазы на диске НЕ удаляются (чисти каталог вручную). Автодетект kind по приложению.

### create_launch_config
- Purpose: создать runtime-client конфиг запуска (thin/thick/web). Один конфиг = и run, и debug (режим выбирается при запуске).
- Params: projectName (req, V8ConfigurationNature); clientType (thin default/thick/web); name (опц., default `<Project> Thin|Thick|Web Client`); applicationId (опц., из get_applications; иначе дефолтное приложение).
- Returns: JSON — action='created', name, applicationId, type, message.
- Gotchas: проект — конфигурация (extension/externalObjects отклоняются). Нет приложений → отказ (создай инфобазу). Конфиги в workspace `.metadata` (нет в git, не экспортируются). Очистка — delete_launch_config.

### delete_launch_config
- Purpose: удалить конфиг запуска по имени.
- Params: name (req, точное, case-sensitive); confirm (false=превью).
- Returns: JSON — action(preview/deleted), name, project, type, message.
- Gotchas: confirm-gated. Не удаляет работающий конфиг — сначала terminate_launch. delete_project НЕ удаляет конфиги.

### list_configurations
- Purpose: конфиги запуска (runtime client + Attach + др.) + running-состояние — discovery перед debug_launch/run_yaxunit_tests/update_database.
- Params: type (`attach`/`client`/`all` default); projectName (опц.).
- Returns: JSON — configurations[]{name (→launchConfigurationName), type, attach, applicationId, project, running(+mode/suspended)}; count.
- Gotchas: Attach-сессию стартует только launchConfigurationName-режим debug_launch. Имя `name` используй дословно.

### delete_project
- Purpose: убрать проект из воркспейса, опц. с удалением файлов с диска.
- Params: projectName (req); deleteContent (false=только дерегистрация; true=удалить файлы, необратимо); confirm (false=превью).
- Returns: JSON — action(preview/deleted), deleteContent, message.
- Gotchas: confirm-gated; deleteContent=true невосстановимо. Сначала terminate_launch занятых запусков. Не удаляет конфиги запуска (delete_launch_config).
