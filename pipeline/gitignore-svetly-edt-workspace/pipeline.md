# Пайплайн: gitignore-svetly-edt-workspace

**Задача:** корректно подключить локальный воркспейс `TransportManagementDevelop_SVETLY/`
к репозиторию (он ложно триггерил `docs-change-enforcer` как untracked «код без документации»).

## 1. Планирование (архитектура)
`TransportManagementDevelop_SVETLY/` — локальный воркспейс **1C:EDT**: `.metadata/` (служебное) +
`Конфигурация/` (исходники) + собственный `.gitignore`. Untracked в parent, **не** сабмодуль,
своей git-истории нет. Сиблинг `ИБTransportManagementDevelop/Конфигурация` подключён как **submodule**.
Стратегия отслеживания — решение пользователя.

## 2. Дизайн (реализация)
- **Интерим (сделано):** исключить весь воркспейс из parent по принципу «gitignore-first» —
  снять ложную UNMAPPED-блокировку немедленно, без потери данных на диске.
- **Целевое (выбрано пользователем):** отслеживать как сиблинг — `.metadata/` остаётся в ignore,
  `Конфигурация/` регистрируется как **submodule** (нужен remote; пушить submodule ДО parent —
  см. память `project_embedded_git_repos`).

## 3. Кодирование
- [x] Добавлен `/TransportManagementDevelop_SVETLY/` в корневой `.gitignore` (интерим-разблокировка).
- [ ] Пивот на submodule: сузить ignore до `.metadata/`, создать remote, `git init` + push
      `Конфигурация`, `git submodule add`, запись в `.gitmodules`.

## 4. Тестирование
- [x] Интерим проверен: `git check-ignore -v` → правило `.gitignore:25`; `git status` чист.
- [ ] Submodule: `git submodule status` видит `Конфигурацию`; parent ссылается на pinned-коммит;
      клон с `--recurse-submodules` восстанавливает дерево.
