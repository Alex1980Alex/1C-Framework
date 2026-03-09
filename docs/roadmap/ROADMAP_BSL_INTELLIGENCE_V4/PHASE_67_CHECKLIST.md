# Чеклист готовности: Фаза 67 — External Tools Integration

**Приоритет:** LOW | **Срок:** 2-4 дня | **Зависимости:** нет

## Предусловия
- [ ] Доступны репозитории: claude-hud, bsl-semantic-diff
- [ ] SonarQube установлен с поддержкой BSL плагина (sonar-bsl-plugin)
- [ ] 1C:EDT установлена для тестирования export/import
- [ ] Тестовые BSL проекты для валидации интеграций

## Артефакты (файлы/код)
- [ ] `tools/claude-hud/bsl_panel.js` — BSL панель для claude-hud (модуль, зависимости, объекты)
- [ ] `tools/bsl-semantic-diff/` — структурный diff BSL (уже частично существует)
- [ ] `config/sonar-bsl-rules.xml` — правила качества BSL для SonarQube
- [ ] `scripts/edt_export_import.py` — скрипты export/import для 1C:EDT
- [ ] Документация: `docs/external_tools.md`

## Метрики приёмки
- [ ] claude-hud BSL panel: время отклика <= 2s при загрузке проекта
- [ ] bsl-semantic-diff: точность >= 95% на тестовом наборе
- [ ] SonarQube BSL: покрытие >= 80% кодовой базы
- [ ] 1C:EDT export/import: Success Rate = 100% на тестовых проектах

## Интеграционные проверки
- [ ] claude-hud: отображение данных при открытии `.bsl` файла
- [ ] semantic-diff: отчёт между двумя коммитами генерируется корректно
- [ ] SonarQube: сканирование проекта показывает метрики BSL (дублирование, сложность)
- [ ] EDT export: формирует корректную файловую структуру
- [ ] EDT import: не нарушает целостность проекта (валидация проходит)
- [ ] Логирование всех внешних вызовов (INFO/DEBUG)

## Блокеры для следующих фаз
- [ ] Эта фаза завершающая — не блокирует другие фазы
- [ ] Однако отсутствие SonarQube блокирует Quality Gates в CI/CD
