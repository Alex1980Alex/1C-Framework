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
0. **Pre-audit** (~15 мин, read-only): scan `C:\1С-Framework` + `~/.claude*` → `data/reports/profile-rename-inventory.json`
1. **Backup** (~30 мин): `git commit --allow-empty`, copy `.claude*` + `.claude.json` + `Documents\WindowsPowerShell\` → `E:\backup\`, `reg export ProfileList`, `winget export`
2. **Create Admin2** (~5 мин): `New-LocalUser Admin2 + Add-LocalGroupMember Administrators`. Нужен чтобы переименовать активный профиль.
3. **Rename + registry** (~10 мин): logout → Admin2 → `Rename-Item "Tech. Boutique" "AlexPC"` → registry `ProfileImagePath` → (опц.) `Rename-LocalUser` → relogin AlexPC.
4. **Recreate venvs** (~10 мин): venv shebangs hardcoded → broken. Recreate `.venv` + `external/1c_mcp/venv`, `pip install -e .`
5. **Sed-replace** (~20 мин): `scripts/replace_user_profile_path.py --apply`. Patterns: `C:\Users\Tech. Boutique` (3 quote forms). Exclude vendor/cache/git.
6. **Reinstall apps** (~15 мин): `winget uninstall + install GitKraken.cli` (per-user package path). Обновить `.claude/settings.local.json`.
7. **Verification** (~15 мин): `claude mcp list` 23+, real MCP tool call, hook chain, 1С debug <2s, pre-commit pass.
8. **Cleanup** (~5 мин): `Remove-LocalUser Admin2`, clear debug logs, retain backup 30 дней.

## §18 Progress log
| Дата | Phase | Event | Ref |
|---|---|---|---|
| 2026-05-23 | — | Roadmap created | (this commit) |
