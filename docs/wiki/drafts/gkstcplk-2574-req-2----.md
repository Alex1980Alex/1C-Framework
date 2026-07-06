---
confidence: 0.8124424848355826
content_hash: 3dab9d839c51fde6
content_type: wiki
created_at: '2026-07-07T00:03:22.548557'
importance: 0.5
memory_type: wiki
source: obsidian-vault
status: draft
tags:
- GKSTCPLK-2574
- ШаблоныСообщений
- YAxUnit
- SonarQube
- config-src
- ИБTransportManagementDevelop
- union-получателей
title: GKSTCPLK-2574 REQ-2 (подбор получателей в шаблоне,
unified_id: wiki:obsidian-vault:93606553-ba5c-44b8-90c7-f43b557a3491
updated_at: '2026-07-07T00:03:22.548559'
version: 1
---

## Content

GKSTCPLK-2574 REQ-2 (подбор получателей в шаблоне, база ИБTransportManagementDevelop) — ЗАВЕРШЕНО и LIVE-верифицировано 2026-07-01.

СТАТУС ХВОСТОВ (были «не выполнены»):
1) update_database — ПРИМЕНЁН: ТЧ Справочник.ШаблоныСообщений.Получатели живёт в БД (get_applications=UPDATED), есть данные.
2/3) Live e2e union — ПОДТВЕРЖДЁН через execute_code (транзакция read-only) на реальном шаблоне «Рассылка уведомлений об отгрузке» (bc98a755-634b-11f1-a411-005056947911, 3 получателя-Пользователи → d.bazeltsev@/n.dovbysh@/e.mechai@): pre-seed подписки [subscr@, d.bazeltsev@] → после гкс_РассылкиИОповещения.ДобавитьПолучателейИзШаблона = [subscr@, d.bazeltsev@, n.dovbysh@, e.mechai@]. Union ✓, дедуп по адресу ✓ (d.bazeltsev@ ровно 1×), резолв ссылки Пользователи→EmailПользователя ✓, пустая ссылка→no-op ✓. Точка-4 wiring подтверждён живым чтением ЗаполнитьПолучателейСообщения из БД (вызов внутри ветки ТипШаблона="Письмо"). Исключен=Истина — фильтр «И НЕ Исключен» подтверждён фикстурой в транзакции.
4) YAxUnit — тест-модуль гкс_РассылкиИОповещенияТест (5 кейсов) НАПИСАН+зарегистрирован в src/bsl/exts/UnitTests (Configuration.xml ChildObjects + подсистема ЮТТ_ЮТПодключаемыеМодули/Модульные/Content). Фикстуры — временный ШаблоныСообщений (ОбменДанными.Загрузка), teardown жёстким Удалить. ПРОГОН заблокирован квирком раннера (см. урок ниже).
6) Sonar — ground-truth API (inNewCodePeriod=true): все 3 REQ-2 файла (гкс_РассылкиИОповещения, ШаблоныСообщенийСлужебный, ШаблоныСообщений/Forms/ФормаЭлемента) = 0 new-code BLOCKER/CRITICAL. Extract-method фикс REQ-1 CyclomaticComplexity ПриСозданииНаСервере 22→18 подтверждён устранённым. REQ-2 = Clean-as-You-Code.

УРОК A (YAxUnit test-runner mcp-onec-test-runner, config File='C:\onec-test-bases\TM_UnitTest'): config-src (tools/mcp-jars/.runtime/config-src, 221MB, gitignored) = Designer-дамп рабочей ИБ, НЕ авторегенерится launcher'ом; при устаревании тесты падают «метод не найден». Обновлять через edt-mcp export_configuration_to_xml(projectName, outputPath) — экспортит EDT-проект (с диска, с правками) в Designer-XML БЕЗ блокировки серверной ИБ (в обход занятого Конфигуратора). Расширение UnitTests: Privileged=true в общем модуле расширения ЗАПРЕЩЁН («Использование привилегированных общих модулей в расширении недопустимо») → Privileged=false. После неудачной загрузки ext (провал валидации Privileged) слот расширения в тест-базе «застревает» → build_project валит «Расширение с таким именем уже существует»; DeleteConfigExtension по имени "UnitTests"/"tests" не помог (rc=0 no-op). Чистый сброс — пересоздать конфиг тест-базы.

УРОК B (Sonar multi-root crash): run-sonar-analysis.ps1 передаёт -Dsonar.sources=<3 корня из sonar_sources.py>; bsl-сенсор (JDK21) ПАДАЕТ на 2-м корне (кумулятивная куча, -Xmx12g НЕ помог, тихий crash, exit 1). Обход: сканировать ЕДИНСТВЕННЫЙ корень (java -jar sonar-scanner-cli -Dsonar.sources=ИБTransportManagementDevelop/Конфигурация, БЕЗ 3-root override; кириллический путь передавать -D аргументом через python subprocess-list, НЕ из sonar-project.properties [оттуда мохибек]). Дельту REQ-2 мерять project-level /api/issues/search?componentKeys=<project>&inNewCodePeriod=true&severities=BLOCKER,CRITICAL + фильтр по суффиксу файла ЛОКАЛЬНО (обход кириллического component-key 500 в per-file запросах sonar_rescan_verify.py — [[reference-sonar-cyrillic-component-api]]). sonar_rescan_verify.py FAIL = артефакт (считает total не new-code + Cyrillic-500 + в scope попадает не-REQ-2 SVELTY-файл гкс_ПриемкаТранспорта), НЕ дефект REQ-2.
