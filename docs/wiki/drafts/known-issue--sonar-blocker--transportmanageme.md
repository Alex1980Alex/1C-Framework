---
confidence: 0.8234927680908746
content_hash: 7e1fe3f7cb6de133
content_type: wiki
created_at: '2026-07-05T04:22:37.330641'
importance: 0.5
memory_type: wiki
source: obsidian-vault
tags:
- sonar
- blocker
- MissingCommonModuleMethod
- 1c
- гкс_ПриемкаНаПЛКСервер
- deferred
- fix-sonar-task
title: '[KNOWN-ISSUE · Sonar BLOCKER · ИБTransportManageme'
unified_id: wiki:obsidian-vault:219db8a4-0e75-450d-a8ca-297796b436f9
updated_at: '2026-07-05T04:22:37.330645'
version: 1
---

## Content

[KNOWN-ISSUE · Sonar BLOCKER · ИБTransportManagementDevelop] Реальный недостающий метод: вызов гкс_ПриемкаНаПЛКСервер.ОтразитьТранспортныйДокумент(РегистрацияНаПЛК, Объект.Ссылка) в форме Documents/гкс_ТранспортныйДокумент/Forms/ФормаДокумента/Module.bsl L77 — метода нет в общем модуле гкс_ПриемкаНаПЛКСервер. Корень доказан: не FP, не rename (git log -S: символа никогда не было в модуле), НЕ ОтразитьДвижения (тот generic-хелпер движений: 3 параметра ТаблицыДляДвижений/Движения/Отказ, другая семантика; вызов даёт 2 ссылки), среди 27 методов модуля кандидата под сигнатуру (Регистрация, ТранспортныйДокумент) нет; вызов единственный во всей конфигурации, внутри намеренной ветки (нашли РегистрациюНаПЛК → отразить). Статус: DEFERRED пользователем 2026-06-22 — ждёт доменного решения (A реализовать метод по спеке / B удалить вызов L76-78 / C другой метод). Анализ: pipeline/sonar-missing-otrazit-transportdoc/ANALYSIS-REPORT.md; pipeline на approve-гейте (этапы 1-2 done, 3 заблокирован). Связанный кластер Bug A: гкс_ИнтеграцияСРПВ L137/157/164 → отсутствующие методы гкс_ПодтверждениеДоставкиСообщений. Прогнано через паттерн /fix-sonar-task (GATE_ORCHESTRATOR_ENABLE активен).