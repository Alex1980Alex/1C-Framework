---
name: fix-sonar-task
description: Обязательный паттерн обработки дефектов SonarQube ЧЕРЕЗ 1С-пайплайн. ИСПОЛЬЗУЙ для /fix-sonar-task. Оркестратор pull→триаж→(per-cluster)/analyze-1c-task→/implement-1c-task→/run-1c-tests→re-scan. Делегирует sonar_issues_pull.py + analyze-1c-task-v2 + implement-1c-task + run-1c-tests, сам их НЕ дублирует. Хард-правило: Sonar-issue НИКОГДА не фиксить ad-hoc вне пайплайна.
version: 1.0.0
updated: 2026-06-21
commands:
  - /fix-sonar-task
---

# /fix-sonar-task — Sonar-remediation через пайплайн (паттерн, ADR-033)

> **Паттерн (обязательный):** дефекты SonarQube обрабатываются **только** через 1С-пайплайн
> Планирование→Дизайн→Кодирование→Тестирование. Ad-hoc правка Sonar-issue **запрещена** — каждый реальный
> баг проходит `/analyze-1c-task` (ANALYSIS-REPORT с корнем и intended behavior) → approve →
> `/implement-1c-task` (EDT-MCP + verify) → `/run-1c-tests` + re-scan. Это **оркестратор** существующих
> методик; он их не дублирует.

## Зачем паттерн
Sonar даёт десятки тысяч issues; среди BLOCKER/CRITICAL есть **реальные баги** (битые вызовы, запросы к
несуществующим метаданным), **ложные** (динамический `ОбщегоНазначения.ОбщийМодуль(строка)`, объекты из
расширений, плейсхолдеры шаблонов) и **косметика/БСП**. Реальный баг — это доменное решение (какой
метод/метаданное целевое), а не механическая замена → его место в пайплайне с анализом, а не в ad-hoc-правке.

## Вход (`$ARGUMENTS`)
Фильтр выгрузки: `--severities BLOCKER,CRITICAL` (дефолт), `--types BUG,VULNERABILITY`, `--path-contains <подстрока>`. Пусто → BLOCKER+CRITICAL.

## Оркестрация

### Шаг 1 — Pull + триаж (этап Планирование)
1. `scripts/sonar_issues_pull.py <фильтр> --max 5000` → worklist (MD+JSON+**SARIF 2.1.0**, R4) в `data/reports/sonar/`. Каждый issue несёт **`remediation_class`** (R5): `deterministic` (механический фикс) / `judgment` (домен).
2. **Scope-гейт (ADR-033):** оставить **кастом** (`/гкс_`, `configuration/`); **БСП не трогаем** (~90% issues — чужой код, правки сорвут обновление типовой).
3. **Триаж чтением кода** (НЕ авто-фикс): по каждому правиле/файлу определить:
   - **real** — битый вызов/запрос (метод/метаданное реально отсутствует) → в пайплайн;
   - **FP** — динамический модуль (`ОбщегоНазначения.ОбщийМодуль(строка)`), объект из расширения (чужой префикс), плейсхолдер шаблона (`ИмяПланаОбмена`) → пометить, НЕ фиксить (при необходимости исключить из скана / добавить расширение в скоуп);
   - **deterministic** (R5-класс: LineLength/MissingSpace/формат) → **детерминированный трансформер** (cc-1c-skills batch / ruff-подобный), НЕ тяжёлый анализ-пайплайн (split детерминизм/judgment, ADR-034 R5).
   Инструменты триажа: `scan_metadata_index` (объект существует?), `bsl_list_methods` (метод существует?), Read кода. После `/mcp reconnect` — `bsl-code-search`/`bsl_impact_analysis`/`edt_find_references`.

### Шаг 2 — Кластеризация
Сгруппировать **real**-баги в задачи-кластеры (по модулю/механизму). Один кластер = одна pipeline-задача.

### Шаг 3 — Per-cluster pipeline (ОБЯЗАТЕЛЬНО, child-workflow R1 ADR-034)
**Кластеры — СТРОГО ПОСЛЕДОВАТЕЛЬНО: один кластер = один полный пайплайн-цикл (child) со СВОИМ состоянием; «один CURRENT за раз».** Не запускать следующий, пока текущий не закрыт+проверен — иначе указатель `CURRENT` перетрётся, а сессионный `onec-task-completion-stop` пропустит кластер без своего capture (натяжения T1/T2).

Для КАЖДОГО кластера (по очереди):
1. **init child-pipeline:** `pipeline_state.py init sonar-<rule>-<file> --title "Sonar: <кластер>"` — свой slug + состояние (переезжает в папку задачи); НЕ переиспользовать чужой `CURRENT`.
2. **`/analyze-1c-task`** (`analyze-1c-task-v2`) → **ANALYSIS-REPORT.md**: корень (рефакторинг/мёртвый/extension/FP), точки, **доменный вопрос** (какой метод/метаданное целевое).
3. **approve** дизайна (реальность бага + intended behavior; FP отсекается здесь).
4. **`/implement-1c-task`** → правка BSL/XML через EDT-MCP + `get_project_errors` verify (BSL пишет Opus).
5. **`/run-1c-tests`** (если есть BDD) + live BP-trace (1c-debug-hmr).
6. **per-cluster completion (R2):** recall+capture+research **для ЭТОГО кластера** (не полагаться на сессионный gate) → `pipeline_state.py done <slug> 4`. Кластер **идемпотентен** (повторный прогон безопасен — повторная правка того же бага не создаёт дубль).
7. → только теперь следующий кластер.

### Шаг 4 — Re-scan + verify (этап Тестирование, evaluator-optimizer R7 ADR-034)
После фикса — **петля evaluator-optimizer**:
1. `scripts/run-sonar-analysis.ps1` (профиль «1C BSL Way» 180/180) → `sonar_issues_pull.py` по затронутым файлам → дельта (или `python scripts/sonar_rescan_verify.py` — авто-дельта по git-изменённым `.bsl` + запись state-контракта для хард-гейта ADR-037).
2. **Адверсариальный `code-verify`**: фикс не внёс новых issues и не сломал смежное.
3. **Критерий приёмки:** BLOCKER/CRITICAL по затронутым файлам = 0 **И** нет новых `new_violations` (`sonar_quality_gate_check.py`).
4. **Не сошлось → вернуться к Шагу 3.4 (implement)** для кластера (итеративное уточнение фикса), затем повторить оценку. Зафиксировать дельту.

## Хард-правила
- **НИКОГДА** не фиксить Sonar-issue ad-hoc вне пайплайна (это и есть паттерн).
- Каждый **real**-баг = pipeline-задача с ANALYSIS-REPORT (доменное решение зафиксировано).
- **FP / extension / placeholder / БСП / cosmetic** → НЕ код-правка: документировать, при необходимости — исключить из скана (`sonar_sources.py`) или добавить расширение в скоуп.
- Жёсткий QG-блокер (R6, ADR-034) реализован: `sonar_quality_gate_check.py` (Clean-as-You-Code, только новый код), **opt-in** `SONAR_QG_HARD=1` (по умолчанию soft/warn).
- **Хард-гейт изменённого/добавленного кода (ADR-037, default-ON):** после фикса прогнать `python scripts/sonar_rescan_verify.py` — Stop-гейт `onec-task-completion-stop` блокирует завершение 1С-задачи, если изменённый/новый `.bsl` под `/src/` не прошёл Sonar с чистой дельтой (0 BLOCKER/CRITICAL на затронутых файлах). Автоматизирует критерий приёмки Шага 4 для своих правок. Sonar-down → skip; opt-out `ONEC_SONAR_GATE_DISABLE=1`.

## Связанные
- Скрипты: `scripts/sonar_issues_pull.py`, `scripts/run-sonar-analysis.ps1`, `scripts/sonar_setup_quality_profile.py` (профиль 180/180).
- Методики (делегирование, НЕ дублировать): `analyze-1c-task-v2`, `implement-1c-task`, `run-1c-tests`, `code-verify`.
- Решения: ADR-033 (remediation), гл. 43.7 (анализ всей конфигурации).
