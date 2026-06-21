# ADR-034: Эволюция слоистости pattern↔pipeline по best-practices 2026 (резолв T1-T5)

**Дата:** 2026-06-21 · **Статус:** accepted (R1-R8 реализованы; R3 — основа, миграция инкрементальна) · **Исследование:** [../cache/pattern-pipeline-orchestration-2026.md](../cache/pattern-pipeline-orchestration-2026.md)
**Связь:** уточняет ADR-017/018 (generic + mandatory pipeline), ADR-033 (Sonar remediation), PATTERN 2.14.

## Контекст
Архитектура: каталог-паттернов (ярус 1) → пайплайн 1С (ярус 2 = композиция ~9 паттернов) → оркестраторы `/run-1c-task`/`/fix-sonar-task` (ярус 3). Слоистость здоровая (ацикл 3→2→1), но 5 натяжений на стыке: **T1** батч vs одиночный CURRENT; **T2** сессионный Stop-gate vs per-cluster; **T3** два Stop-Gate на одном Stop; **T4** инстанс в каталоге паттернов; **T5** перегрузка «pipeline». Свип best-practices 2026 даёт проверенные решения (см. кеш).

## Решение (приоритизированный роадмап; [own] на базе [web])
- **R1 (T1+T2) ВЫСШИЙ — child-workflow модель.** `/fix-sonar-task` = родитель; каждый кластер = **полный пайплайн-цикл (child)** со СВОИМ состоянием в папке кластера + per-cluster completion-check; прогон **последовательный** (один CURRENT за раз). Источник: Temporal child-workflows + LangGraph subgraph.
- **R2 (T2) — idempotency + per-cluster capture.** Кластер идемпотентен (повторный прогон безопасен); recall/capture per-cluster, не опираясь на сессионный gate. Источник: Temporal idempotency.
- **R3 (T3) — gate-as-policy.** Гейты (approval/scope/completion) → **композируемый policy-слой** (OPA-стиль) с decision-logging вместо независимых конкурирующих Stop-хуков. Источник: OPA/conftest.
- **R4 (T4, лёгкий, ВЫСОКИЙ ROI) — SARIF как контракт находок.** `sonar_issues_pull` эмитит/потребляет **SARIF 2.1.0** → любой сканер (mypy/Semgrep/BSL-LS) кормит тот же пайплайн → паттерн обобщается «Findings-to-Pipeline». Источник: SARIF + Pixee.
- **R5 (эффективность) — split детерминизм vs суждение.** Косметика/механика (LineLength/MissingSpace/Export) → **детерминированный трансформер** (cc-1c-skills batch / recipe), НЕ тяжёлый анализ-пайплайн; только judgment-баги → пайплайн. Источник: OpenRewrite/Moderne + Pixee codemods.
- **R6 (CI-гейт) — Clean-as-You-Code.** Жёсткий QG-блокер только на **новый код** (`new_violations`), не на 64k легаси-БСП → снимает блокер из ADR-033. Источник: SonarQube CaYC.
- **R7 (эвалюатор) — evaluator-optimizer на фиксе.** После фикса — re-scan дельта + адверсариальный `code-verify` ДО merge. Источник: Anthropic evaluator-optimizer + наш code-verify.
- **R8 (T4/T5 чистота) — таксономия.** PATTERN 2.14 → обобщённый «Findings-to-Pipeline Remediation», `/fix-sonar-task` = реализация; глоссарий «pipeline» (1.10 / 2.13 / generic-4stage / 1С-43) в PATTERNS.md/43.1; имена этапов согласовать со словарём Anthropic.

**Очередность внедрения:** дёшево сначала — **R4 + R5 + R6 + R8** (SARIF-контракт, split детерминизма, CaYC-гейт, таксономия), затем **R1** (child-state), затем **R3** (policy-слой) + **R2/R7**.

**Реализовано 2026-06-21:** ✅ **R4** (`sonar_issues_pull.py --format sarif`, SARIF 2.1.0, live-verified) · ✅ **R5** (`remediation_class` deterministic/judgment в pull + триаже `/fix-sonar-task`) · ✅ **R8** (PATTERN 2.14 → «Findings-to-Pipeline Remediation» + глоссарий «pipeline» в PATTERNS.md) · ✅ **R6** (`scripts/sonar_quality_gate_check.py` — Clean-as-You-Code hard-gate на новый код; вписан в `run-sonar-analysis.ps1` + `ci-1c.yml`; **opt-in** `SONAR_QG_HARD=1`, по умолчанию soft; live: hard→exit 1, soft→exit 0) · ✅ **R1+R2** (child-workflow в `fix-sonar-task` SKILL Шаг 3: кластеры строго последовательно, свой pipeline-state на кластер, «один CURRENT за раз», per-cluster completion+идемпотентность) · ✅ **R7** (evaluator-optimizer в Шаг 4: re-scan дельта + адверсариальный `code-verify` + критерий BLOCKER=0 ∧ нет new_violations, не сошлось → назад к implement) · ✅ **R3** (`.claude/hooks/shared/gate_policy.py` — composable fail-closed `evaluate_gates` + `log_decision`; 4 unit-теста PASS) **+ миграция 3 живых гейтов** (`pipeline-gate`/`pipeline-protocol-stop`/`onec-task-completion-stop` логируют deny/allow через `gate_policy` → единый `data/gate-decisions.jsonl`; defensive import [graceful fallback], behavior-preserving, import-smoke резолвит реальный модуль). **Все R1-R8 реализованы.**

## Последствия
### Положительные
- T1-T5 закрыты проверенными отраслевыми паттернами; пайплайн масштабируется на батч без протечки слоёв; findings-слой обобщается на любой сканер (SARIF); снят блокер жёсткого QG (CaYC).
### Отрицательные / риски
- R1/R3 — нетривиальная переработка (child-state + policy-слой) → строго инкрементально.

## Альтернативы (отклонены)
- Внедрять Temporal/LangGraph как **движки** — избыточно (мы на hooks+Python+Claude Code); берём **паттерны**, не рантаймы.
- Оставить как есть — натяжения протекут на батч-сценариях (кластер без capture, дедлок гейтов).

## Связанные файлы
- Кеш: `cache/pattern-pipeline-orchestration-2026.md`
- ADR-017/018/033 · PATTERNS.md (2.14) · 43.1/43.7 · `scripts/sonar_issues_pull.py` · `.claude/skills/fix-sonar-task/`
