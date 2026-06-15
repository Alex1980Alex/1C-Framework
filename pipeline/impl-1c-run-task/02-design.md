# /run-1c-task — Дизайн (этап 2)

## Решение
Новая команда-оркестратор **`/run-1c-task <вход>`** = AUTO-режим: analyze→approve(авто)→implement→test
без паузы. Гейтованный поток (`/analyze-1c-task` + `/implement-1c-task`) остаётся для случаев с ревью.

## Изменения (4 файла, каждое обратимо)

### 1. `pipeline_1c_bridge.py` — +`resolve_task_input(arg) -> dict`
Детект источника входа: путь к ТЗ-папке (существует + dir) → `folder`; иначе JIRA-код → `jira`;
иначе описание → `chat`. Возврат `{kind, slug, folder}`. Чистая функция (Path + derive_slug, без pipeline_state) → collision-immune тест.

### 2. `.claude/commands/run-1c-task.md` — команда
Делегирует скиллу `run-1c-task`, передаёт `$ARGUMENTS`. Краткая шапка + «см. SKILL».

### 3. `.claude/skills/run-1c-task/SKILL.md` — оркестрация (4 этапа)
Инструкция мне (Claude):
1. **Вход** — `resolve_task_input($ARGUMENTS)` → kind/slug/folder.
2. **Этап 1-2** — `pipeline_state init <slug>`; выполнить методику **analyze-1c-task-v2** (Фазы 1-5) → ANALYSIS-REPORT.md.
   Если kind=folder: собрать spec+скриншоты из ТЗ-папки (input-ingestion V.6). `done <slug> 1; done <slug> 2`.
3. **АВТО-APPROVE** — `pipeline_state approve <slug>` БЕЗ паузы на человека (это и есть отличие от гейтованного).
4. **Этап 3** — выполнить методику **implement-1c-task** (Этапы 0-3) → BSL/XML. `done <slug> 3`.
5. **Этап 4** — выполнить **/run-1c-tests** (va-bdd-testing) → зелёные. `done <slug> 4`.
6. **W** — `tool_usage_report.py --run-id <id> --task-dir <папка>`.
7. Отчёт: что сделано + вердикт тестов.
**Хард-правило:** AUTO ≠ игнор блокеров. Критическая ошибка/неоднозначность на любом этапе → ОСТАНОВИСЬ и спроси.

### 4. `tests/unit/test_pipeline_1c_bridge.py` — +тесты resolve_task_input (folder/jira/chat).

## Почему так (атрибуция)
- `[exp]` Skill-делегирование не триггерит UPS-гейт → approve в AUTO = консистентность state, методика не дублируется.
- `[own]` Одна команда с авто-детектом входа (folder/jira/chat) проще двух (выбор пользователя на AskUserQuestion).
- `[exp]` Авто-approve = осознанный обход ревью (пользователь выбрал /run-1c-task), но с хард-правилом «стоп на блокере».

## Обратимость
Удалить команду+скилл+helper-функцию+тесты. Гейтованный поток (B′) не затронут. Гейт F-2 не меняется.

## Риск и митигация
Риск: AUTO пропускает ревью → плохой ANALYSIS уйдёт в код. Митигация: хард-правило «стоп на критической
ошибке/неоднозначности» в скилле + методика analyze-1c-task-v2 (Фазы verify) не ослаблена.

**Статус: approved (оператор — само-одобрение, dogfooding).**
