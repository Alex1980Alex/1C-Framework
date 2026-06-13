# skill-router-ground-truth.jsonl — схема и провенанс (roadmap 260613 Фаза A)

Эталон для `scripts/eval-skill-router.py`. Один JSON-объект на строку (JSONL, UTF-8).

## Поля

| Поле | Тип | Назначение |
|------|-----|------------|
| `prompt` | str | Входной промпт пользователя |
| `expected_skills` | list[str] | Ожидаемые скиллы (пусто = роутер должен молчать) |
| `expected_bundles` | list[str] | Ожидаемые бандлы роутера |
| `intent` | `action`\|`informational`\|`system` | Класс намерения |
| `source` | см. ниже | **Провенанс метки** (A4) |
| `split` | `train`\|`test`\|`quarantine` | Назначение в оценке (A6/A5) |

## Таксономия `source` (A3)

| source | Значение | Доверие метке |
|--------|----------|----------------|
| `spec` | Кейс спроектирован из определения/триггеров скилла | высокое (нет leakage) |
| `human` | Промпт написан человеком, метка проставлена вручную независимо | высокое |
| `transcript-human` | Промпт из живого транскрипта, метка проставлена **независимо** (человек смотрел определение скилла, НЕ вывод роутера) | высокое |
| `transcript-router` | Промпт из транскрипта, метка **выведена из session-активаций** (что роутер/человек-в-цикле активировал) | **LEAKAGE-кандидат** — метка коррелирует с поведением роутера |

## Политика `split` (A5/A6)

- **`train`** / **`test`** — только чистые от leakage кейсы (`source ∈ {spec, human, transcript-human}`).
  Split **заморожен** и **стратифицирован** по `intent` + домену (первый `expected_bundle`):
  внутри страты ~каждый 3-й → `test` (детерминированно по sha1(prompt)).
  Гейт (`scripts/skill_system_acceptance.py` критерий 3) меряет **pooled action_f1** на этом наборе.
- **`quarantine`** — `transcript-router` кейсы (leakage-кандидаты). **Остаются в файле**
  (ценные реальные промпты), но **исключены из train/test** и из метрик eval.
  Промоушен `quarantine → train/test` — **только** после независимой ре-верификации
  метки автором (смотреть определение скилла, НЕ вывод роутера); тогда `source`
  меняется на `transcript-human`. До тех пор они не влияют на честное число.

## Инварианты (проверяет `scripts/lint_skill_router_gt.py`, A8)

1. Каждый кейс несёт все 6 полей; `intent`/`source`/`split` из допустимых множеств.
2. `expected_skills ⊆ каталог` (скиллы из бандлов `skill-router-config.json`).
3. **0 leakage в гейте**: `source == transcript-router` ⇒ `split == quarantine` (никогда train/test).
4. `intent ∈ {informational, system}` ⇒ `expected_skills == []`.
5. Покрытие `test`: ≥1 action, ≥1 silence, ≥5 доменов (иначе предупреждение).

CI: blocking-job `skill-router-gt-lint` в `.github/workflows/ci.yml` (A9) — leakage/схема
краснят CI независимо от advisory `skill-router-eval`.

## Текущее состояние (миграция 2026-06-13)

73 `spec` (designed) + 22 `transcript-router` (карантин). Split: 48 train / 25 test
(20 action) / 22 quarantine. **A7 (рост test независимыми кейсами до ≥30 action)** —
follow-up: добирать `transcript-human`/`spec` кейсы, метить независимо.
