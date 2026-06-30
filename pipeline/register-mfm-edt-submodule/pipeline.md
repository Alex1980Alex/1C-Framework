# Пайплайн: оформить EDT-воркспейс `MFM/` как submodule (по аналогии с соседями)

## Что + затем
Пользователь добавил EDT-проект в `C:\1С-Framework\MFM`. Оформить его как прочие
EDT-воркспейсы (`ИБTransportManagementDevelop/`, `TransportManagementDevelop_SVETLY/`):
внутренняя `Конфигурация` — приватный git-submodule, внешняя папка — в `SKIP_PATTERNS`.
**Заменяет** прошлый подход (`pipeline/gitignore-mfm-edt-workspace` — gitignore `MFM/`),
который был отменён по указанию пользователя.

## Эталонный паттерн (изучен по соседям)
- `<ws>/.gitignore` (tracked) игнорит `/.metadata/` — у MFM уже есть, идентичный.
- `<ws>/Конфигурация` — submodule, remote `github.com/Alex1980Alex/<Name>-Configuration.git`
  (private), branch `master`; свой EDT-`.gitignore` (bin/build/*.cf/*.epf… + явный tr  ack src).
- внешняя папка `<ws>/` — в `SKIP_PATTERNS` `docs-change-enforcer.py`.

## Этапы
1. **Планирование** — определён паттерн submodule (а не gitignore); имя remote
   `UpravlenieMaterialnymiPotokami-Configuration` (выбор пользователя), private.
2. **Дизайн** — шаги: внутр. `.gitignore` (копия соседа) → init/commit `MFM/Конфигурация`
   → `gh repo create --private` + push → `git submodule add` → `SKIP_PATTERNS += MFM/`
   → CLAUDE.md → откат корневого `.gitignore`.
3. **Кодирование** —
   - `MFM/Конфигурация/.gitignore` создан (идентичен соседу).
   - inner repo: init -b master, commit `fca69f5` (9463 файла), push на новый private remote.
   - `git submodule add <url> MFM/Конфигурация` + `branch = master` в `.gitmodules`.
   - `docs-change-enforcer.py` `SKIP_PATTERNS += "MFM/"`; CLAUDE.md синхронизирован.
   - корневой `.gitignore`: строка `MFM/` удалена (откат прошлого подхода).
4. **Тестирование** — `git submodule status` показывает `MFM/Конфигурация`;
   `git status` чист; remote доступен (`gh repo view`); `.gitmodules` совпадает с соседями.

## Критерий готово
`MFM` оформлен идентично `TransportManagementDevelop_SVETLY` (submodule + SKIP_PATTERNS),
парент-коммит зелёный, EDT-сессии больше не триггерят ложные гейты.
