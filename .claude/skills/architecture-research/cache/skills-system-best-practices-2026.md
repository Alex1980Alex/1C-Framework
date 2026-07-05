# Skills-системы у лидеров — контракт SKILL.md, роутинг, lifecycle, evals (июль 2026)

**Дата:** 2026-07-05
**Статус:** актуально
**Теги:** [claude-code-skills, skill-md, frontmatter, progressive-disclosure, skill-evals, pass-at-k, skill-lint, master-router, lifecycle, agentskills-standard]

> Кеш = объективные факты (ADR-002). Сравнение с нашей системой — вне кеша.
> Дополняет `skill-library-lifecycle-testing-2026.md` (Voyager/lifecycle) и `claude-code-ecosystem-tools-2026.md` (каталоги/SDLC).

## 1. Официальный контракт SKILL.md (code.claude.com/docs/en/skills, fetched 2026-07-05)

- **Commands слиты со skills**: `.claude/commands/deploy.md` ≡ `.claude/skills/deploy/SKILL.md` — оба дают `/deploy`; skills = superset (supporting files, invocation control, авто-загрузка).
- Стандарт — **Agent Skills (agentskills.io)**, открытый, кросс-агентный; Claude Code расширяет его invocation control / subagent execution / dynamic context injection.
- **Frontmatter-поля (все опциональны, рекомендован только `description`)**: `name` (display only, команда — от имени директории), `description` (+`when_to_use` — вместе усечены до **1536 символов** в листинге), `argument-hint`, `arguments` (именованные позиционные → `$name`), `disable-model-invocation` (только юзер; описание НЕ в контексте), `user-invocable: false` (только модель; скрыт из `/`-меню), `allowed-tools` (pre-approve, НЕ ограничение), `disallowed-tools` (изъятие из пула до следующего сообщения), `model`, `effort`, `context: fork` + `agent` (Explore/Plan/custom; Explore/Plan не грузят CLAUDE.md), `hooks` (скоупленные на lifecycle скилла), `paths` (glob-активация только на подходящих файлах), `shell` (bash|powershell для `!`-инъекций).
- **Подстановки**: `$ARGUMENTS`, `$ARGUMENTS[N]`/`$N`, `$name`, `${CLAUDE_SESSION_ID}`, `${CLAUDE_EFFORT}`, `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PROJECT_DIR}` (v2.1.196+, работает и в `allowed-tools`).
- **Dynamic context injection**: `` !`cmd` `` и ` ```! ` блоки — команда выполняется ДО показа скилла модели, output инлайнится (preprocessing); отключаемо `disableSkillShellExecution` (managed policy).
- **Lifecycle контента**: приглашённый скилл остаётся в контексте всю сессию, файл НЕ перечитывается; при авто-компакте re-attach: первые **5000 токенов** на скилл, общий бюджет **25 000 токенов**, приоритет — последние приглашённые.
- **Бюджет листинга описаний**: 1% контекст-окна (настраивается `skillListingBudgetFraction` / `SLASH_COMMAND_TOOL_CHAR_BUDGET`); при переполнении первыми теряют описания реже используемые скиллы; `/doctor` показывает, кого урезало; `skillOverrides` в settings: `on|name-only|user-invocable-only|off` (без правки чужого SKILL.md).
- **Скоупы**: enterprise > personal > project (> bundled) при коллизии имён; nested `.claude/skills/` в монорепо → квалифицированное имя `apps/web:deploy`; symlink-директории поддерживаются; skill-папка с `.claude-plugin/plugin.json` = полноценный плагин (hooks/agents/MCP).
- **Live change detection**: правки SKILL.md подхватываются в текущей сессии без рестарта (только текст; hooks/.mcp.json — `/reload-plugins`).
- **Стекинг**: `/skillA /skillB args` (v2.1.199+) — до 6 скиллов одним сообщением, общий `$ARGUMENTS`.
- **Permission-контроль**: `Skill(name)` / `Skill(name *)` allow/deny-правила; deny `Skill` = отключить все.
- Bundled skills: `/code-review`, `/debug`, `/loop`, `/batch`, `/run`+`/verify`+`/run-skill-generator` (записывает launch-рецепт проекта в `.claude/skills/run-<name>/`).

## 2. Авторинг (platform.claude.com best-practices, fetched 2026-07-05)

- **Валидация полей**: `name` ≤64 симв., lowercase/цифры/дефисы, без слов "anthropic"/"claude"; `description` ≤1024 симв., без XML-тегов, **третье лицо** («Processes…», не «I can…" — ломает discovery).
- Описание = «что делает» + «когда использовать» с key terms/триггерами; единственный сигнал выбора из 100+ скиллов.
- **Naming**: рекомендован gerund (`processing-pdfs`); допустимы noun phrases; запрещены vague (`helper`, `utils`) и generic (`data`, `files`); консистентный паттерн внутри библиотеки.
- **Размер**: SKILL.md body < **500 строк**; сверх — выносить в отдельные файлы. «Claude уже умный» — каждый параграф должен оправдать токен-стоимость.
- **Progressive disclosure — 3 паттерна**: (1) high-level guide + ссылки на FORMS.md/REFERENCE.md/EXAMPLES.md; (2) domain-split `reference/{finance,sales,product}.md` — грузится только нужный домен, + grep-подсказки; (3) conditional details (базовое инлайн, advanced по ссылке).
- **Ссылки строго 1 уровень глубины от SKILL.md** (вложенные ссылки → Claude превьюит `head -100` и читает неполно); reference-файлы >100 строк — с TOC сверху.
- **Degrees of freedom**: high (эвристики текстом) / medium (шаблон-псевдокод) / low (точный скрипт без параметров) — по хрупкости операции («узкий мост vs открытое поле»).
- **Workflow-паттерны**: чеклист, который модель копирует в ответ и отмечает; feedback loop «валидатор → фикс → повтор»; plan-validate-execute (промежуточный `changes.json` + verbose-валидатор) для batch/деструктивных операций.
- **Скрипты**: solve-don't-punt (обрабатывать ошибки в скрипте, не сваливать на модель); без voodoo-констант; явно различать «Run X» (execute) vs «See X» (read as reference); MCP-инструменты — полные имена `Server:tool`.
- **Анти-паттерны**: Windows-пути (только `/`); много альтернатив вместо дефолта с escape-hatch; time-sensitive контент (вместо этого `<details>`-секция «Old patterns»); смешанная терминология.
- **Eval-first**: создавать evals ДО написания документации (gap→baseline→минимальные инструкции→итерация); тестировать на всех целевых моделях (Haiku/Sonnet/Opus); чеклист публикации ≥3 evals.
- Итеративный цикл «Claude A (автор) / Claude B (свежий исполнитель)»: наблюдать реальные пути навигации (пропущенные ссылки, перечитываемые файлы, игнорируемые бандлы) и править структуру по наблюдению, не по предположению.

## 3. Evals для скиллов — стандартизованный конвейер (agentskills.io/skill-creation/evaluating-skills + skill-creator plugin)

- Формат: `evals/evals.json` в директории скилла — `{id, prompt, expected_output, files[], assertions[]}`; workspace `skill-workspace/iteration-N/eval-X/{with_skill,without_skill}/{outputs,timing.json,grading.json}` + `benchmark.json`.
- **Baseline-сравнение обязательно**: каждый кейс дважды — со скиллом и без (или со старой версией-снапшотом); свежий контекст на прогон (subagent).
- Assertions: verifiable/countable («axes labeled», «≥3 recommendations»), не vague («output is good») и не brittle (точная фраза); mechanical-проверки — скриптом, не LLM-judge; grading = PASS/FAIL **с evidence-цитатой**.
- `benchmark.json`: pass_rate/time/tokens mean±stddev для обеих конфигураций + **delta** (что скилл покупает vs что стоит).
- Анализ паттернов: assertions «всегда PASS в обеих» — выкидывать (инфлируют pass rate); «всегда FAIL в обеих» — чинить кейс; высокий stddev = двусмысленные инструкции.
- **Blind A/B** двух версий скилла LLM-судьёй без раскрытия версий.
- **Description tuning**: генерация should-trigger / should-not-trigger промптов, замер hit rate, авто-предложение правок описания (skill-creator plugin, `/plugin install skill-creator@claude-plugins-official`).
- Правила итерации: generalize from feedback (не narrow-патчи под кейсы), keep lean (plateau при добавлении правил = over-constrained, пробовать УДАЛЯТЬ), explain why (reasoning-инструкции надёжнее ALWAYS/NEVER), bundle repeated work (повторяющийся helper-код → `scripts/`).

## 4. Независимый eval/verify-тулинг (2026)

- **Caliper** (github.com/edonadei/caliper) — local-first **pass@k** для скиллов (Claude Code/Codex/Pi/Hermes): `.eval.yaml` с `expect:` (LLM-judge по транскрипту вкл. tool-calls) + `assert:` (детерминированный Python); outcome-типы pass/task_fail/**cheat**/infra_error/timeout/judge_error; обязательный baseline-delta «скилл добавляет ценность, а не базовая модель справилась сама»; ставится как два скилла `evaluate-skill`/`grill-skill` через `npx skills add`.
- **SkillSpec** (skillspec.sh) — контракт `skill.spec.yml` рядом со SKILL.md (routes, phase sequencing, tool boundaries, required checks, completion proof); «Doctor» меряет token load / buried instructions / name collisions / missing proof; loop assess→import→execute→align, execution-трейсы фингерпринтятся против спеки (детект drift). Данные: ~100 токенов/скилл — «standing bill» листинга; медианное тело скилла ~1414 токенов; **46% опубликованных скиллов имеют коллизии имён**.
- **skill-framework** (karsonenns) — «Terraform для скиллов»: **17 lint-правил** (naming, dead links, token budgets, hardcoded credentials, undeclared secrets, spec limits), secrets через провайдеров без вшивания значений; `sf deploy` = один source tree → компиляция в Claude Code/Codex/Gemini/Cursor с plan-диффом и lockfile; таксономия 4 оси: domain (nouns) / outcomes (verbs) / memory type (knowledge|perception|procedure|motor|judgment) / duration (session|temporary|reinforced|permanent); shared knowledge в `references/` по ссылке, не копией.
- **NonBytes/skills-validation** — офлайн desktop (Tauri/Rust): parse/lint/validate/simulate/dry-run SKILL.md.

## 5. Роутинг / дискавери — паттерны лидеров

- **Master-router** (gamedev-skills, 66 скиллов): один router-скилл детектит контекст (файлы проекта, напр. `project.godot`) + keywords запроса → грузит только нужные скиллы в приоритетном порядке (engine basics → discipline → genre); **пользователь никогда не называет скиллы** — роутер выбирает невидимо. Скиллы version-pinned к релизу движка (Godot 4.x, Unity 6 LTS…) против API-дрейфа.
- Официальный путь — description-driven: третье лицо, key terms, `when_to_use`, `paths`-глобы для файлово-скоупленной активации; troubleshooting «не триггерится» = усилить keywords / «триггерится лишнее» = сузить описание или `disable-model-invocation`.
- Token-роутинг как отдельный скилл: vagkaratzas/skills `token-saviour` (~-70% токенов на tool selection, HN 2026-06).
- Anti-pattern из SkillSpec-данных: рост библиотеки → листинг-налог + коллизии имён → неверный выбор из усечённых описаний.

## 6. Lifecycle / композиция (Superpowers v6.1.1, июль 2026)

- obra/superpowers жив (v6.1.1 2026-07-02, 628 коммитов): ~14 core-скиллов в 4 категориях (testing / debugging / collaboration / meta), включая meta-скиллы **writing-skills** и **using-superpowers**.
- Композиция = последовательный SDLC-чейн: brainstorming → git-worktrees → writing-plans → subagent-driven-development|executing-plans → TDD (RED-GREEN-REFACTOR) → requesting/receiving-code-review (2 стадии: spec compliance → code quality) → finishing-a-development-branch; «агент проверяет релевантные скиллы перед любой задачей».
- Тестирование скиллов — собственный **drill eval harness** (superpowers-evals), тесты в `evals/` + npm test для plugin-инфры.

## 7. Дистрибуция / экосистема (2026-07)

- **vercel-labs/skills CLI** (25.1k★, v1.5.14 06/2026, 382 dependents): `npx skills add|find|use|list|update|remove`; discovery — корень/`skills/`/`skills/.curated/`/`skills/.experimental/`/`.claude/skills/` до 2 уровней + `.claude-plugin/marketplace.json`; scopes project (`./<agent>/skills/`, в VCS) vs global; 70+ агентов с автодетектом; флаг `internal: true` прячет WIP-скиллы (кроме `INSTALL_INTERNAL_SKILLS=1`). Курация конвенцией директорий `.curated`/`.experimental` — стадии зрелости прямо в дереве.
- **anthropics/skills** (158k★): `skills/` по категориям + `spec/` (спецификация стандарта) + `template/`; frontmatter-минимум name+description; document skills (docx/pdf/pptx/xlsx) — source-available референсы, питающие нативные способности Claude.
- Крупнейшие библиотеки на скане 2026-07: sickn33/antigravity-awesome-skills (1800+ скиллов, installer CLI, bundles), K-Dense-AI/scientific-agent-skills (140 скиллов, «160k+ scientists»), VoltAgent/awesome-agent-skills (1000+), TerminalSkills/skills, доменные пакеты (alpaca-skills, sports-skills, marketingskills, academic-research-skills) — тренд: вертикальные skill-packs под открытый стандарт.
- OthmanAdi/planning-with-files — file-based planning + «deterministic completion gate» + multi-agent shared state on disk, распространяется как SKILL.md на 60+ агентов.

## Чем лидеры отличаются от типичной самодельной skills-системы (нейтрально)

1. **Evals как first-class артефакт скилла** (`evals/evals.json` в директории скилла) + обязательный baseline «без скилла» и токен/время-delta — а не только ручная проверка «сработал».
2. **Измеряют оба слоя раздельно**: activation (should/not-should-trigger hit rate, description tuning) и output quality (assertions+judge) — и есть outcome-класс «cheat».
3. **Машинный контракт рядом с прозой** (skill.spec.yml: phases, tool boundaries, completion proof) + drift-детект по execution-трейсам.
4. **Линт и token-бюджеты в CI** (17 правил, dead links, secrets, spec limits) + «Doctor»-аудит листинг-налога и коллизий имён.
5. **Один source tree → компиляция во все runtime'ы** с lockfile и plan-диффом (вместо копий на агента).
6. **Роутинг вынесен в meta-скилл** (master router, детект по файлам проекта + невидимый выбор), version-pinning скиллов к версии инструмента.
7. **Стадии зрелости конвенцией каталога** (`.curated` / `.experimental` / `internal:`-флаг).
8. **Оптимизация в обе стороны**: plateau → УДАЛЯТЬ инструкции (over-constrained), а не добавлять; повторяющийся сгенерированный код → bundled script.

## Ключевые источники
- Skills в Claude Code (полный контракт): https://code.claude.com/docs/en/skills
- Authoring best practices: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Evals-конвейер: https://agentskills.io/skill-creation/evaluating-skills · skill-creator: https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator
- https://github.com/anthropics/skills · https://github.com/obra/superpowers · https://github.com/vercel-labs/skills
- https://github.com/edonadei/caliper · https://skillspec.sh · https://github.com/karsonenns/skill-framework · https://github.com/NonBytes/skills-validation
- https://github.com/gamedev-skills/awesome-gamedev-agent-skills · https://github.com/sickn33/antigravity-awesome-skills · https://github.com/OthmanAdi/planning-with-files
