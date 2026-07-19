# Подавление алертов по «известным проблемам» — best practices (2026-07-19)

**Источники (verified via WebSearch 2026-07-19):**
- [Prometheus Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) — silences / inhibition / mute_time_intervals.
- [pytest: Flaky tests / xfail](https://docs.pytest.org/en/stable/explanation/flaky.html) — expected-failure маркер.
- [TeamCity: muting build/test failures](https://www.jetbrains.com/help/teamcity/investigating-and-muting-build-failures.html) — quarantine known issue.

## Проблема
«Инструмент/тест сломан по ИЗВЕСТНОЙ (часто внешней/апстрим) причине. Не хочу бесконечный алерт/задачу, но не хочу ослепнуть, если сломается по-новому.»

## Каноничные паттерны

### 1. Alertmanager — silences vs inhibition
- **Silence** = временное подавление по matchers. **Best practice: не длиннее 24ч без явного обоснования**; всегда с expiry.
- **Inhibition** = подавить производные алерты, пока горит корневой (dependency-based).
- **Muting ≠ удаление:** silenced-алерты сохраняют **видимость и audit trail**. Открытый запрос (issue #2805): хотят уведомление, когда silenced-алерт **RESOLVED**.

### 2. pytest xfail / CI-quarantine (главный аналог)
- **`xfail`** = known-failure не красит билд. **`strict=True`:** если xfail-тест **неожиданно ПРОШЁЛ → xpass → билд КРАСНЕЕТ** (маркер устарел / проблема решена). ← критическая защита от «ослепнуть».
- ⚠ Quarantine/xfail **«опасен как ПОСТОЯННЫЙ»** — только временно, с ревью. Успех flaky-теста не доказывает починку (manual mute).

### 3. Синтез — «xfail для инструментов» (правильная форма suppression)
Наивный вечный allowlist — антипаттерн. Правильное подавление known-issue несёт 4 свойства:
1. **Reason + audit trail** — причина + ссылка (ADR/issue/W13), кто/когда. Тул остаётся ВИДЕН в отчёте с пометкой `known-issue`, но НЕ эскалируется в mandatory-задачу.
2. **Time-bounded / review-by** — дата ревью (аналог Alertmanager «≤24ч без обоснования»; для редких инфра-дефектов — недели, но НЕ «навсегда»). После expiry — снова алертит.
3. **Unexpected-recovery detection (xpass)** — если «known-broken» тул начал УСПЕШНО отрабатывать → surface «возможно решено, снять suppression» (не молчать).
4. **Inhibition-мысль** — подавлять по КОРНЮ (напр. ложный `infra_error` при exit 0 = класс), не по одному имени, если корень общий.

## Применение во фреймворке (tool-health, ADR-055)
`analyze_tool_health.py` / `tool-health-banner-on-start.py` не имеют suppression → broken-тул с внешним корнем (codepilot1c `qa_run`/`qa_generate`, W13: getThickClientInfo апстрим + `infra_error`-при-успехе) плодит mandatory-задачи каждые 72ч (метрика не самоочистится из-за ложных негативов). Нужен known-issues слой с 4 свойствами выше, а НЕ вечный mute.

## Связь
- [[reference-codepilot1c-qa-run-binary-path]], W13 (roadmap 260718), ADR-055 (если реализуем).
