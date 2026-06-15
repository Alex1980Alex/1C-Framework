# /run-1c-task — Кодирование (этап 3)

Реализовано 4 файла (каждый обратим независимо):

1. **`pipeline_1c_bridge.py`** — +`resolve_task_input(arg) -> {kind, slug, folder}`: детект входа
   (существующая папка ТЗ > JIRA-код > описание). Чистая функция (os.path + derive_slug) → collision-immune.
2. **`.claude/commands/run-1c-task.md`** — slash-команда: делегирует skill `run-1c-task`, передаёт `$ARGUMENTS`,
   ссылается на гейтованный поток как альтернативу.
3. **`.claude/skills/run-1c-task/SKILL.md`** — оркестратор 4 этапов: resolve вход → analyze-1c-task-v2 →
   **авто-approve** (`pipeline_state approve`, без паузы) → implement-1c-task → va-bdd-testing → W-отчёт.
   Хард-правило «AUTO ≠ игнор блокеров». Методики 1С не дублируются и не меняются.
4. **`tests/unit/test_pipeline_1c_bridge.py`** — +4 теста `resolve_task_input` (jira / chat / folder через tmp_path /
   несуществующий-путь-с-JIRA).

**Механизм AUTO:** оркестратор после анализа сам ставит `approve` (отличие от гейтованного потока — нет паузы
на человека). Гейт F-2 (UPS на /implement-1c-task) в skill-делегированном потоке не участвует → approve = консистентность
state. Гейтованный поток (`/analyze-1c-task` + `/implement-1c-task`) не затронут.
