# 260613 — Skill System Verification Follow-up (методология измерения + precision роутера)

> Follow-up к [260612 Skill System Full Verification](260612_ROADMAP_SKILL_SYSTEM_FULL_VERIFICATION.md).
> Ревью реализации 260612 (2026-06-13, max-effort code review) подтвердило: P0–P3
> инженерно крепкие (mirror/prune, write-contract, uuid5-identity, score-floor,
> контракт лога surfacing — без ложных тревог), **но сертификация качества
> замкнута сама на себя**. Критерий 3 acceptance («router F1 ≥ 0.75») и цель S5
> («качество роутера доказано числом») держатся на in-sample числе, подогнанном
> под тот же ground-truth, по которому оно измеряется. Этот roadmap фиксирует
> findings F1–F8 и план их закрытия.
>
> Связанные правила: [[feedback-roadmap-progress-log-protocol]],
> [[project-roadmap-audit-pattern]], [[feedback-root-cause-over-symptom]].

## 1. Findings (ревью 2026-06-13)

| # | Sev | Finding | Якорь | Суть |
|---|-----|---------|-------|------|
| **F1** | 🔴 CRIT | Гейт F1≥0.75 in-sample / overfit + label leakage | [skill-router.py:269-384](../../.claude/hooks/skill-router.py#L269), [skill_system_acceptance.py:94](../../scripts/skill_system_acceptance.py#L94) | Layer A2 откалиброван по FN того же GT (комментарий: «GT-классы FN … закрываются детекторами»); 22 кейса GT размечены по выводу самого роутера; +0.18 F1 (0.5791→0.7595) измерен на тех же 95 кейсах, held-out нет; запас над порогом 0.0095. Критерий 3 нефальсифицируем. |
| **F2** | 🟠 HIGH | «CI-гейт качества» ничего не блокирует | [ci.yml:362](../../.github/workflows/ci.yml#L362) | `continue-on-error: true` → и `exit 1` при F1<0.75 ([ci.yml:420](../../.github/workflows/ci.yml#L420)), и честный fail при отсутствии GT ([ci.yml:389](../../.github/workflows/ci.yml#L389)) — лишь аннотации. §1/U6 называет это «гейт», энфорсмента нет. |
| **F3** | 🟠 HIGH | Подстрочный матч имени скилла +4 без границ слова | [skill-router.py:380-384](../../.claude/hooks/skill-router.py#L380) | `len(skill)>=6 and skill.lower() in prompt_lower → +4` при `min_score=1`. Однословные бандл-скиллы `deployment`/`autoresearch` срабатывают на случайный подстрочный хит → форс бандла → FP (тот класс, что дал «89 FP»). |
| **F4** | 🟡 MED | Критерий 1 «зеркало» не ловит content-drift | [skill_system_acceptance.py:78](../../scripts/skill_system_acceptance.py#L78), [skills_harvest.py:404](../../.claude/hooks/shared/skills_harvest.py#L404) | drift = `len(missing)` (точки нет вовсе); changed-скиллы (`content_hash` разошёлся, точка есть) сидят в `to_upsert` и в drift не входят. Протухшая по контенту библиотека рапортует drift=0 и PASS — противоречит «библиотека = зеркало живого каталога». |
| **F5** | 🟡 MED | Macro-F1 подбит бесплатными 1.0 | [eval-skill-router.py:81-93](../../scripts/eval-skill-router.py#L81), [196-202](../../scripts/eval-skill-router.py#L196) | 13/95 GT-кейсов (informational+system, `expected=[]`) дают f1=1.0 за молчание и усредняются в `skill_metrics`. ~14% заголовочного F1 — «кредит за тишину», а не точность роутинга; именно это число читает гейт. |
| **F6** | 🟡 MED | Критерий 7 (honest-failure) — хрупкий греп | [skill_system_acceptance.py:154](../../scripts/skill_system_acceptance.py#L154), [ci.yml:390](../../.github/workflows/ci.yml#L390) | Ищет `"ground-truth.jsonl missing"` — совпадает случайно (хвост имени файла), грепает текст сообщения, а не `exit 1`. Перефраз echo → молчаливый FAIL при живом поведении; удаление `exit 1` с сохранением echo → ложный green. |
| **F7** | ⚪ LOW | Phantom-guard не покрывает Level A.1 | [code-skill-enforcer.py:328-383](../../.claude/hooks/code-skill-enforcer.py#L328) | `_check_research_protocol` хардкодит `Skill('learning-loop')` без `_skill_exists`. Скилл сейчас существует, но заявление B2 «класс phantom-блокировки закрыт» имеет дыру. |
| **F8** | ⚪ LOW | Дефолтный путь health-отчёта расходится с каноном | [skill-health-analyzer.py:273](../../scripts/skill-health-analyzer.py#L273) vs [skill_system_acceptance.py:54](../../scripts/skill_system_acceptance.py#L54) | Скрипт по умолчанию пишет в `data/skill-health-report.md`, acceptance/каденс читают `data/reports/skills/…`. Работает лишь потому, что каденс передаёт `--output` явно ([memory_maintenance.py:96](../../scripts/memory_maintenance.py#L96)); любой иной вызов кладёт отчёт мимо → критерий 6 FAIL. |

## 2. Корневая проблема

Измерительный слой (S5 / eval-skill-router / acceptance критерий 3) выдаёт **нефальсифицируемый и систематически завышенный** сигнал: число меряется на той же выборке, под которую подгонялся роутер, и читается как доказательство обобщающего качества. Acceptance в итоге закрывает гарантию, которой нет. Доменные фичи A2 (CamelCase-кириллица, `гкс_`, `Srvr=`) сами по себе легитимны и в проде, вероятно, помогают — претензия к **способу измерения**, а не к фичам.

## 3. Тест-карта (что должна проверять честная приёмка)

| # | Цепочка | Критерий приёмки |
|---|---------|------------------|
| H1 | Held-out F1 | GT разбит train/test (или k-fold CV); A2-веса подбираются ТОЛЬКО на train; отчётный F1 — на test. В §18 — оба числа. |
| H2 | Анти-оверфит GT | новые GT-кейсы НЕ размечаются по выводу роутера (only human/spec-разметка); фиксировать происхождение каждого кейса. |
| H3 | Honest CI | либо джоба блокирующая (снять `continue-on-error`), либо слово «гейт» убрано из §1/U6/доков везде; критерий 7 проверяет факт `exit 1`, а не текст сообщения. |
| H4 | Precision A2 | word-boundary матч имени скилла; родовые однословные имена исключены/занижены; FP-замер до/после на test-сплите. |
| H5 | Зеркало по контенту | критерий 1 учитывает `to_upsert`/changed ИЛИ добавлен отдельный freshness-критерий (доля точек с `content_hash` == disk-hash). |
| H6 | Метрика без «тишины-кредита» | заголовочный F1 считается отдельно по action-кейсам (expected≠∅); silence-accuracy на informational/system — отдельная метрика, не в одном среднем с роутингом. |

## 4. Фазы

### P0 — Честная метрика (фундамент, блокирует переоценку S5)
| # | Задача | Критерий |
|---|--------|----------|
| P0.1 | **F1/F5/H1/H6**: train/test split (или k-fold) в `eval-skill-router.py`; отдельный `action_f1` (expected≠∅) и `silence_accuracy`; `--save-report` пишет оба + размер сплитов | held-out F1 числом в §18 (ожидаемо < 0.7595) |
| P0.2 | **F1/H2**: пометить происхождение каждого GT-кейса (`source: human|spec|transcript`); запретить разметку по выводу роутера; зафиксировать в `data/skill-router-ground-truth.jsonl` schema | leakage-кейсы помечены/изъяты |
| P0.3 | Acceptance: критерий 3 читает **held-out action_f1**, не in-sample `skill_metrics.f1`; до появления честного числа — критерий 3 = PENDING, не PASS | acceptance перестаёт маскировать |

### P1 — Precision роутера (F3/H4)
- Word-boundary в [skill-router.py:380-384](../../.claude/hooks/skill-router.py#L380) (`\bskill\b`, не `in`); исключить однословные родовые имена (`deployment`, `autoresearch`) или понизить их вес.
- FN/FP-разбор по `--save-fp` **на train-сплите**; A2-веса не трогать без проверки на test.
- Замер precision до/после на test (ожидается рост precision при ≤ малой просадке recall).

### P2 — Честный CI/guards (F2/F6/F7/H3)
| # | Задача | Критерий |
|---|--------|----------|
| P2.1 | Решить судьбу `continue-on-error` на `skill-router-eval`: либо снять (блокирующий гейт после P0/P1), либо вычистить слово «гейт» из §1/U6 и доков (честный advisory) | формулировка == реальность |
| P2.2 | Критерий 7 проверяет `exit 1`-ветку структурно (парс шага, не греп текста); добавить негативный тест: удаление `exit 1` → критерий FAIL | F6 закрыт |
| P2.3 | `_skill_exists('learning-loop')` в Level A.1 ([code-skill-enforcer.py](../../.claude/hooks/code-skill-enforcer.py)) перед блоком | F7 закрыт |

### P3 — Зеркало по контенту + мелочи (F4/F8/H5)
- Acceptance критерий 1: либо учитывать `to_upsert` (changed) в drift, либо добавить freshness-критерий (доля `content_hash`-совпадений). Решить осознанно (changed-churn vs зеркало).
- Дефолт `--output` в [skill-health-analyzer.py](../../scripts/skill-health-analyzer.py) выровнять на `data/reports/skills/skill-health-report.md`.

### P4 — Re-acceptance
После P0–P3 — переснять acceptance 260612 с честной метрикой; зафиксировать новый вердикт в §18 260612 (текущий «критерий 3 PASS честным числом» аннотировать как оспоренный этим follow-up).

## 5. Порядок и оценка

P0 (1d — split + переразметка GT может вскрыть, что held-out F1 заметно < 0.75 → роутер требует реальной работы, не косметики) → P1 (0.5d) → P2 (0.5d) → P3 (0.5d) → P4 (0.5d).
[[project-roadmap-audit-pattern]]: оценка P0 оптимистична — переразметка происхождения 95 кейсов и честный сплит могут вскрыть, что «дотяжка до 0.75» была иллюзией; закладывать +1d на реальную доводку роутера.

## 6. Риски

- **Held-out F1 < 0.75 (вероятно)** — тогда критерий 3 260612 ретроактивно не выполнен; это ожидаемый и желательный честный результат, не регрессия. Не «чинить» подгонкой под test.
- **Снятие `continue-on-error` краснит master** — сначала P0/P1 (реальное качество), потом блокирующий гейт; иначе CI-красный без рычага.
- **Переразметка GT субъективна** — фиксировать происхождение и критерий разметки (spec-driven), не «как решил роутер».
- **Word-boundary может уронить recall** на легитимных буквальных упоминаниях скиллов — мерить на test, не на глаз.

## §18 Progress Log

| Дата | Событие | Детали |
|------|---------|--------|
| 2026-06-13 | Follow-up создан | Max-effort code review реализации [260612](260612_ROADMAP_SKILL_SYSTEM_FULL_VERIFICATION.md): P0–P3 инженерно корректны (mirror reconcile-против-коллекции, snapshot-before-prune, uuid5-identity == батч-индексатор, write-contract `content_hash`+`record_ingest`, score-floor на сырой cosine до RRF, контракт `arms`/`gate` int-счётчиков на верхнем уровне лога). Findings F1–F8: **F1 CRIT** — гейт F1≥0.75 in-sample/overfit (Layer A2 подогнан под FN того же GT, 22 GT-кейса размечены по выводу роутера, +0.18 на той же выборке, запас 0.0095) + **F2/F3 HIGH** (CI `continue-on-error` → не гейт; подстрочный матч имени скилла +4 без границ слова → FP) + F4–F8. Корень: измерительный слой выдаёт нефальсифицируемый/завышенный сигнал, acceptance закрывает несуществующую гарантию. План P0 (честная held-out метрика + анти-leakage GT) → P1 (precision A2) → P2 (честный CI/guards) → P3 (зеркало по контенту) → P4 (re-acceptance). |
| 2026-06-13 | **P0–P3 реализованы; критерий 3 честно FAIL — желаемый исход** | **F3** (P1): подстрочный матч имени скилла → word-boundary `\b…\b` ([skill-router.py:380](../../.claude/hooks/skill-router.py#L380)); изоляция-прогон (pre/post) — 0 регрессий (33 пред-существующих env-падения `test_skill_routing.py` не связаны). **F1/F5** (P0): eval-skill-router считает `honest_metrics` — pooled `action_f1` (action-only, без silence-padding) + диагностический train/test split + `silence_accuracy`; acceptance критерий 3 переключён с in-sample `skill_metrics.f1` на pooled `action_f1`. **Живой прогон: legacy padded macro-F1=0.7595, но честный pooled action_f1=0.7361 (<0.75) → критерий 3 = FAIL.** Ключевой вывод реализации: train/test split тут НЕ held-out (роутер не обучается на GT в eval-time → A2-веса захардкожены оффлайн), мелкий test-сплит инвертировал (0.84 на 13 семплах > train 0.71) — гейт читает pooled, сплит оставлен диагностикой. **F2** (P2): CI `skill-router-eval` явно advisory, порог на честную метрику ([ci.yml](../../.github/workflows/ci.yml)). **F6** (P2): критерий 7 проверяет факт `exit 1`-ветки, не текст echo. **F7** (P2): `_skill_exists('learning-loop')` guard в Level A.1 enforcer'а. **F4** (P3): критерий `library_content_fresh` (changed=0, точки не устарели по контенту). **F8** (P3): дефолт `--output` health-analyzer на канон. Regress: [tests/unit/test_eval_skill_router_honest.py](../../tests/unit/test_eval_skill_router_honest.py) 7/7 PASS; ruff+compile clean. Acceptance day-1: `all_pass=false` (честно — критерий 3 FAIL). **Остаток: дотяжка precision/recall роутера до pooled action_f1≥0.75 (P1-follow-up, FN/FP-разбор на train без подгонки под GT) + автоматизация A2 re-tune на train-only (тогда test-сплит станет настоящим held-out).** |
| 2026-06-13 | **Остаток декомпозирован → [260613 Honest Eval](260613_ROADMAP_SKILL_ROUTER_HONEST_EVAL.md)** | 4 отложенных пункта раскрыты в фазы A (гигиена GT: провенанс/leakage/split/рост) → B (инфра честного held-out: A2-веса в конфиг, `--split`/`--cv`, train-only оптимизатор) → C (дотяжка FN/FP на train, одноразовый замер на held-out) → D (re-acceptance + решение по CI-гейту). Ключ: B предшествует C (held-out настоящий только при автоматизированном подборе на train-only). Граф зависимостей + критический путь + DoD — в новом roadmap. |
