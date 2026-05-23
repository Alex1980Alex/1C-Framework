# 260523 ROADMAP — Windows профиль Tech. Boutique → AlexPC

**Дата:** 2026-05-23
**Статус:** proposed
**Owner:** Alex Terletskii

## Цель
Переименовать `C:\Users\Tech. Boutique` → `C:\Users\AlexPC`. Пробел+точка ломают bash-escape (~5% команд).

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
