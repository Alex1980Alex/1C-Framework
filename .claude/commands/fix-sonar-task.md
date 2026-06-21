---
description: Обязательный паттерн обработки Sonar-багов ЧЕРЕЗ 1С-пайплайн (pull→триаж→analyze→implement→test→re-scan). Sonar-issue НИКОГДА не фиксится ad-hoc — всегда через /analyze-1c-task → /implement-1c-task. Вход — фильтр (severities/types/path) или пусто (дефолт BLOCKER+CRITICAL кастом).
---

# /fix-sonar-task — Sonar-remediation через пайплайн (обязательный паттерн)

Обработать дефекты SonarQube **только через 1С-пайплайн**, используя **skill `fix-sonar-task`**.

## Вход:
$ARGUMENTS

(фильтр выгрузки: `--severities`, `--types BUG,VULNERABILITY`, `--path-contains`; пусто = BLOCKER+CRITICAL кастом)

---

## Инструкция

**Используй skill `fix-sonar-task`** — оркестратор remediation поверх существующих методик. Паттерн (ADR-033):
1. **Pull + триаж** — `scripts/sonar_issues_pull.py` → кастом (гкс_/configuration) vs БСП; чтением кода real / FP / cosmetic (НЕ авто-фиксить вслепую).
2. **Per-cluster ОБЯЗАТЕЛЬНО через пайплайн** — каждый реальный баг-кластер: `/analyze-1c-task` (ANALYSIS-REPORT, корень+домен) → approve → `/implement-1c-task` (EDT-MCP+verify) → `/run-1c-tests`.
3. **Re-scan + verify** — `run-sonar-analysis.ps1` → `sonar_issues_pull.py` по затронутым файлам → BLOCKER=0.

> **Хард-правило (паттерн):** Sonar-issue НИКОГДА не фиксить ad-hoc вне пайплайна. Каждый реальный баг = pipeline-задача с ANALYSIS-REPORT (intended behavior зафиксирован). FP (extension/placeholder) / БСП / cosmetic → НЕ код-правка (документировать / исключить из скана).

## Результат
- worklist (`data/reports/sonar/`) + триаж · ANALYSIS-REPORT на каждый кластер · правки через /implement + verify · re-scan delta (BLOCKER по файлам → 0).
