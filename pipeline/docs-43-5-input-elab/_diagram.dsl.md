T|§0 ВХОД  ·  сообщение в чате → «это 1С-задача?»
>|Пользователь пишет в ЧАТ. Три формы входа:
>|  • свободный текст («Доработать проведение…»)  — НИ слэша, НИ пути   ← основной случай
>|  • /слэш-команда  (/analyze-1c-task …)         — early-return, ведёт preflight команды
>|  • путь к папке ТЗ  (configuration/<JIRA>/…)   — аргумент /run-1c-task
C|
V|событие UserPromptSubmit
T|ПЕРЕХВАТ  ·  onec-task-input.py  (advisory · 5s · НЕ блокирует)
>|1) слэш-команда?  → return None  (дальше ведёт preflight самой команды)
>|2) иначе → route_1c_task(prompt):
>|     ├─ classify_1c_task()   «ЭТО 1С?» → {is_1c, jira, ttype}
>|     │     definitive (гкс_ / configuration)  ∨  (термин ∨ CamelCase) ∧ глагол
>|     ├─ confident_1c?    jira  ∨  сильный маркер (гкс_ / объект.точка / CamelCase)
>|     └─ estimate_effort()   СЛОЖНОСТЬ → баллы (modify/heavy_obj/cross/multi+тип+папка)
>|           банды:   ≤2 simple    ·    3–5 medium    ·    ≥6 complex
C|
V|flow ∈ {none, ask_1c, auto, ask_flow, gated}
T|РЕЖИМ (flow)  ·  рекомендация хука; решение — за пользователем
>|none      → молчит (не 1С)
>|ask_1c    → подтверди «это 1С? новая / доработка?»   +   V.6 (папка ТЗ)
>|auto      → /run-1c-task            (простая: analyze → approve → implement → test)
>|ask_flow  → СПРОСИ: AUTO или гейт?  (средняя)
>|gated     → /analyze → ревью ANALYSIS-REPORT → /implement   (сложная)
C|
V|РЕШЕНИЕ ПОЛЬЗОВАТЕЛЯ  →  старт потока
T|§0.9 ЗАВЕДЕНИЕ СОСТОЯНИЯ
>|preflight-хук → ensure_pipeline_1c() → pipeline/<slug>/.pipeline-state.json
>|slug = JIRA-код (стабилен analyze↔implement)  ·  title = "1С-задача (<cmd>): <slug>"
C|
V|
T|§1–§4  4-ЭТАПНАЯ ПАРАДИГМА  (G4 — единственный hard-гейт: дизайн approved → код)
>|Этап 1  Планирование   → analyze Ф1-2 → ANALYSIS-REPORT           (этапы 1,2 done)
>|Этап 2  Дизайн         → analyze Ф3-5 (+2.5) → approve G4         (этап 2 approved)
>|Этап 3  Кодирование    → implement Э0-8 → IMPLEMENTATION-PROGRESS  (этап 3 done)
>|Этап 4  Тестирование   → va-bdd S1-4a-4 → .run-state.json          (все passed → 4 done)
>|AUTO  /run-1c-task: analyze → авто-approve (--by auto) → implement → test  (один проход)
B|
A|        §5 СКВОЗНЫЕ СИСТЕМЫ (поперёк ВСЕХ этапов):  Память · Внешний анализ · Скиллы · TOOL-PLAN
V|событие Stop
T|§6 ЗАВЕРШЕНИЕ  ·  два Stop-гейта по порядку
>|1) pipeline-protocol-stop    — пайплайн использован? (правки без пайплайна → блок)
>|2) onec-task-completion-stop — RECALL ∧ CAPTURE ∧ RESEARCH закрыты?  (SKILL — info)
C|
V|
A|                            ✓  ЗАДАЧА ЗАВЕРШЕНА КОРРЕКТНО
