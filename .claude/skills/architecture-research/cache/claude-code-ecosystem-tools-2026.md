# Claude Code ecosystem — skills / plugins / subagents / MCP по SDLC-шагам (2026)

**Дата:** 2026-06-13
**Статус:** актуально
**Теги:** claude-code, plugins, skills, subagents, mcp, spec-driven-development, tdd, code-review, architecture

## Из интернета — экосистема и маркетплейсы

- Официальный встроенный каталог `claude-plugins-official`: 101 плагин (март 2026); 33 от Anthropic (12 LSP, 10 dev-workflow, setup, output-styles) + 68 partner (GitHub, Playwright, Supabase, Figma, Vercel, Linear, Sentry, Stripe, Firebase). Топ установок (01.06.2026): Frontend Design 829k, Superpowers 752k, Context7 349k, GitHub 262k, Playwright 248k, Security Guidance 176k, TypeScript LSP 177k.
- Awesome-листы: `hesreallyhim/awesome-claude-code` (36.8k★, канон), `affaan-m/everything-claude-code` (аггрегатор), `rohitg00/awesome-claude-code-toolkit` (135 agents/35 skills/176+ plugins/14 MCP), `supatest-ai/awesome-claude-code-sub-agents`, `ComposioHQ/awesome-claude-skills`, `Chat2AnyLLM/awesome-claude-plugins`, `punkpeye/awesome-mcp-servers`. Директории: claudemarketplaces.com, aitmpl.com.

## Шаг 1 — Планирование архитектуры (spec-driven + architecture agents)

- **GitHub Spec Kit** (github/spec-kit, ~80k★) — лидер SDD: spec→plan→tasks, human-review между шагами.
- **BMAD-METHOD** (~37k★) — агентный SDD c ролями PM/architect/dev; ~31.7k токенов/прогон.
- **OpenSpec** — лёгкий SDD (delta-specs, approval gate); дешевле BMAD.
- **Superpowers** (obra/superpowers, ~41k★) — SDLC skill-library: brainstorming→implementation planning→subagent execution→TDD→review.
- **Grill Me** (mattpocock/skills) — допрашивает план до общего понимания.
- **Skill Creator** (anthropics/skills) — интерактивный Q&A-генератор скиллов.
- Subagents (supatest-ai): **Design Patterns Expert**, **Clean Architecture Expert**, **Microservices Architect**, **Multi-Agent Systems Architect**, **AWS Cloud Architect**.
- Plugins (official): **Feature Dev** (guided exploration/design), **CLAUDE.md Management** (persistent memory).
- **Figma MCP** generate_diagram (апр 2026) — архитектурные диаграммы/ERD.
- Прочие SDD: AWS Kiro, Tessl, Google Antigravity (по обзору BCMS/Reenbit 2026).

## Шаг 2 — Дизайн реализации (design / API / infra)

- Subagents: **RAG Architecture Expert**, **Terraform Infrastructure Expert**, **Project Setup Wizard**, **Docker Specialist**, **Kubernetes Expert**.
- Skills (vercel-labs/agent-skills): **Web Design Guidelines** (100+ a11y/UX правил), **React Best Practices** (57 perf-правил), **Composition Patterns** (compound components/context).
- **Frontend Design** (official skill/plugin) — production-grade UI.
- **Figma** (official plugin + MCP) — design-to-code, design tokens.
- **Andrej Karpathy's Guidelines** (forrestchang) — think-before-coding, simplicity-first, surgical changes.
- **skills-for-architects** (AlpacaLabsLLC) — коллекция архитектурных скиллов.
- **Terraform MCP** (HashiCorp) — IaC в AI-workflow.

## Шаг 3 — Кодирование / выполнение

- LSP-плагины (official): **TypeScript LSP**, **Pyright LSP** (Python), **Go LSP**, **Rust Analyzer LSP**.
- **GitHub** (plugin/MCP) — repo/PR контекст.
- **Context7 MCP** (Upstash) — актуальная version-specific документация в запросе (анти-галлюцинация API).
- **E2B MCP** — изолированный cloud-sandbox для исполнения Python/JS (+ верификация «код запускается»).
- **Firecrawl MCP/skill** — web scraping/search/research (13+ tools).
- **code-simplifier** (anthropics/claude-plugins-official) — readability-cleanup без смены логики.
- Subagents: **Python Expert**, **Django Expert**, **React Architect**, **JS/TS Expert**, **Spring Boot Expert**.
- **Commit Commands** (official) — структурные коммиты.
- Token/context skills: **Caveman** (−65% токенов), **Context Mode** (восстановление сессии), **Handoff** (компрессия сессии).
- Subagent-driven execution (Superpowers) — свежий subagent-контекст на задачу (против context-drift).

## Шаг 4 — Тестирование / верификация

- **tdd-guard** — автоматический TDD-enforcement (блок без failing-теста).
- **imbue** (athola/claude-night-market) — TDD-enforcement, proof-of-work, scope-guarding.
- **Code Review** (official, 347k installs) — `/code-review` на PR, скоринг, авто-фидбек в GitHub.
- **PR Review Toolkit** (official) — multi-dimensional PR-review (comments/tests/errors/quality).
- **Playwright** (plugin + MCP, Microsoft) — браузер/E2E, визуальная верификация.
- **Webapp Testing** (anthropics/skills) — Playwright-тесты локальных приложений.
- Subagents: **Code Review Master**, **Test Automation Specialist** (TDD/BDD/property-based), **Test Strategy Architect**, **Performance Testing Expert**, **Security Audit Expert**.
- **Security Guidance** (official) + **Trail of Bits Security Skills** (CodeQL/Semgrep).
- **Sentry MCP** — production error-context (пост-деплой верификация).

## Ключевые источники

- Composio — Best Claude Code Plugins 2026: https://composio.dev/content/top-claude-code-plugins
- Firecrawl — Best Claude Code Skills 2026: https://www.firecrawl.dev/blog/best-claude-code-skills
- Firecrawl — 10 Best MCP Servers 2026: https://www.firecrawl.dev/blog/best-mcp-servers-for-developers
- supatest-ai/awesome-claude-code-sub-agents: https://github.com/supatest-ai/awesome-claude-code-sub-agents
- rohitg00/awesome-claude-code-toolkit: https://github.com/rohitg00/awesome-claude-code-toolkit
- athola/claude-night-market (TDD/spec-driven/review): https://github.com/athola/claude-night-market
- hesreallyhim/awesome-claude-code: https://github.com/hesreallyhim/awesome-claude-code
- BMAD vs Spec Kit vs OpenSpec (2026): https://medium.com/@reenbit/bmad-vs-spec-kit-vs-openspec-choosing-your-spec-driven-ai-framework-in-2026-a6996b3ebb8d
- SDD Definitive 2026 Guide (BCMS): https://thebcms.com/blog/spec-driven-development
- scriptbyai — Ultimate Claude Code Resource List 2026: https://www.scriptbyai.com/claude-code-resource-list/
