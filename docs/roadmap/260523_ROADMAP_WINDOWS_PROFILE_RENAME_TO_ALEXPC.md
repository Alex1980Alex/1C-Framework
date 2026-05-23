# 260523 ROADMAP — Windows профиль Tech. Boutique → AlexPC

**Дата:** 2026-05-23
**Статус:** proposed
**Owner:** Alex Terletskii

## Цель
Переименовать `C:\Users\Tech. Boutique` → `C:\Users\AlexPC`. Пробел+точка ломают bash-escape (~5% команд).

## Scope
**In:** rename folder + registry, опц. account rename, обновление hardcoded путей в `C:\1С-Framework` и `~/.claude*`, recreate venvs, reinstall winget user-scope apps.
**Out:** имя ПК, диск, credentials, OS reinstall.

## Pre-flight inventory (по категориям)
- Claude Code: `~/.claude.json`, `~/.claude/projects/.../memory/*.md`, `~/.claude/plugins/`, `~/.claude/debug/`
- PowerShell: `Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`
- Apps user-scope: `~\AppData\Local\Microsoft\WinGet\Packages\GitKraken.cli_*`, `~\AppData\Local\GitKrakenCLI\`, `~\AppData\Roaming\obsidian\`
- Project: `.mcp.json`, `.claude/settings.local.json`, `.venv\` (recreate!), `external/1c_mcp/venv\` (recreate!), `.claude/skills/*/SKILL.md`, `docs/**/*.md`

## Phases (high-level)
0. Pre-audit (read-only inventory)
1. Backup (mandatory)
2. Create Admin2 account
3. Rename folder + registry SID
4. Recreate Python venvs
5. Sed-replace hardcoded paths
6. Reinstall user-scope apps
7. Verification
8. Cleanup

## §18 Progress log
| Дата | Phase | Event | Ref |
|---|---|---|---|
| 2026-05-23 | — | Roadmap created | (this commit) |
