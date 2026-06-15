# Remediate 292 dependabot alerts

Задача: «исправь все» (292 dependabot-алерта в публичном репо, max-effort).
Slug: `remediate-dependabot-deps`

## 1. Планирование (исследование)

`gh api dependabot/alerts` → 292 open (7 crit / 129 high / 134 mod / 22 low).
Анализ (python over dump): **291/292 fixable**; 48 уникальных пакетов (axios×66,
hono×42, claude-code×16, handlebars×14[2 crit]). **ВСЕ в vendored dev/MCP-инструментах**
(`tools/`, `infra/`) — core-фреймворк (`pyproject.toml`/корневой `uv.lock`) чист.
Поверхность: 7 npm-lockfile + 2 uv.lock.

## 2. Дизайн

Безопасная единообразная стратегия: `npm audit fix --package-lock-only` (только
lockfile, без install/скриптов → нулевой runtime-риск, откатываемо) + `uv lock
--upgrade`. `--force` отвергнут как дефолт (пилот: шаффлит, high 11→12, тащит
мажоры). Точечный добив: tandem-bump конфликтующих peer-deps; overrides только
для same-major патчей. Multi-major / ESM-only / fix=False — не форсить (поломка >
польза при low severity).

## 3. Реализация

- npm non-force по 6 инструментам (calibrated пилотом на task-master).
- mcp-reasoner: tandem-bump `@typescript-eslint/*` (devDeps) → снял остаток.
- uv lock --upgrade: serena + ast-grep-mcp.
- 3 коммита: `71a344e14` (основной), `176c97fc8` (mcp-reasoner), pushed.

## 4. Тестирование (верификация)

Local `npm audit` before→after:
- bsl-debugger 7→**0**, bsl-code-search 1→**0**, mcp-reasoner 13→**0**
- tools 13→1low, auto-documenter 13→1low (`diff`, major+ESM → сознательно оставлен)
- task-master 95→52 (crit 5→1; глубокий транзитив vendored task-master-ai@0.26.0)
- pip verified: GitPython 3.1.50, Pygments 2.20.0, starlette 1.3.1 (≥патч)
- lockfile coherence: `npm install --package-lock-only --dry-run` exit 0.

Итог: критичные и большинство high выбиты безопасно; 5/6 npm-инструментов на 0/1-low;
pip чист. Существенный остаток только task-master (dev-scope) — требует ре-вендоринга
или dismiss (решение пользователя). Dependabot отразит снижение асинхронно (ре-скан).

Follow-up (решение пользователя): re-vendor task-master-ai latest / dismiss dev-scope /
accept. + 2 `diff` low + task-master residual.
