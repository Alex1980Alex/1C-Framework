"""
Pytest fixtures for Development Pipeline tests.
"""

import pytest
from datetime import datetime

from constants import AgentRole, ArtifactType, VerificationStatus
from models import Artifact, ArtifactMetadata


@pytest.fixture
def sample_context_artifact():
    """Sample context.md artifact for PM-SPEC testing."""
    content = """# Контекст проекта

## Описание проекта
Разработка модуля управления складом для 1С:ERP.

## Структура
### Общие модули
- СкладскойУчет
- Товарооборот

### Справочники
- Номенклатура
- Склады

### Документы
- ПоступлениеТоваров
- ПеремещениеТоваров

## Цели
- Автоматизация приёмки товаров
- Интеграция с ТСД

## Текущее состояние
Модуль в разработке, требуется добавить новую функциональность.

## Анализ кодовой базы
Проанализированы следующие модули:
- СкладскойУчет.bsl (500 строк)
- ПриемкаТоваров.bsl (300 строк)

## Ключевые файлы
- src/CommonModules/СкладскойУчет.bsl
- src/Documents/ПоступлениеТоваров.xml

## Паттерны
Используется паттерн "Менеджер временных таблиц"

## Релевантные модули
- СкладскойУчет
- Товарооборот
- Номенклатура

## Зависимости
- Справочник.Номенклатура
- Документ.ПоступлениеТоваров
"""
    return Artifact(
        name="context.md",
        content=content,
        metadata=ArtifactMetadata(
            artifact_type=ArtifactType.CONTEXT,
            producer=AgentRole.PM_SPEC,
            tags={"project_id": "test-project", "task_id": "test-task"},
            version=1,
        ),
    )


@pytest.fixture
def sample_spec_artifact():
    """Sample spec.md artifact for PM-SPEC testing."""
    content = """# Спецификация

## Цель
Создание модуля автоматизации приёмки товаров.

## Требования

### Функциональные требования
- FR-001: Создание документа приёмки
- FR-002: Сканирование штрих-кодов
- FR-003: Печать этикеток

### Нефункциональные требования
- NFR-001: Время отклика < 2 сек
- NFR-002: Поддержка 10 одновременных пользователей

## Критерии приёмки
- Все функциональные требования реализованы
- Тесты пройдены

## Вне скоупа
- Мобильная версия (отложено на Phase 2)

## Контекст
См. context.md для детальной информации о проекте.
"""
    return Artifact(
        name="spec.md",
        content=content,
        metadata=ArtifactMetadata(
            artifact_type=ArtifactType.SPEC,
            producer=AgentRole.PM_SPEC,
            tags={"project_id": "test-project", "task_id": "test-task"},
            version=1,
        ),
    )


@pytest.fixture
def sample_design_artifact():
    """Sample design.md artifact for ARCHITECT testing."""
    content = """# Техническое решение

## Архитектурные решения

### Подход к реализации
Используем существующий паттерн обработки документов.

### Структура модулей
- Общий модуль: ПриемкаТоваровClient
- Обработка: МенеджерОбработки
- Формы: Управляемая форма

## План изменений

### Шаг 1: Создание модуля
Создать общий модуль для обработки приёмки.

### Шаг 2: Интеграция
Интегрировать с существующими справочниками.

## Риски
- Риск 1: Несовместимость с устаревшими данными
- Риск 2: Производительность при большом объёме

## BSL компоненты
- Создать процедуру ОбработатьПриемку
- Создать функцию ПолучитьДанныеТовара
"""
    return Artifact(
        name="design.md",
        content=content,
        metadata=ArtifactMetadata(
            artifact_type=ArtifactType.DESIGN,
            producer=AgentRole.ARCHITECT,
            tags={"project_id": "test-project", "task_id": "test-task"},
            version=1,
        ),
    )


@pytest.fixture
def sample_result_artifact():
    """Sample result.md artifact for IMPLEMENTER testing."""
    content = """# Результат реализации

## Выполненные шаги

### Шаг 1: Создание модуля
Создан общий модуль ПриемкаТоваров с необходимыми функциями.

### Шаг 2: Реализация процедур
Добавлены процедуры ОбработатьПриемку и ПолучитьДанныеТовара.

## Созданные файлы

### CommonModules/ПриемкаТоваров/Ext/Module.bsl
- Добавлена процедура ОбработатьПриемку
- Добавлена функция ПолучитьДанныеТовара

## Код реализации

```bsl
Процедура ОбработатьПриемку(Документ) Экспорт
    // Реализация обработки
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Документ.ПоступлениеТоваров";
КонецПроцедуры
```

## Выполненные требования
- FR-001: ✅ Реализовано
- FR-002: ✅ Реализовано

## Тестирование
Проведено unit-тестирование, все тесты пройдены.
"""
    return Artifact(
        name="result.md",
        content=content,
        metadata=ArtifactMetadata(
            artifact_type=ArtifactType.RESULT,
            producer=AgentRole.IMPLEMENTER,
            tags={"project_id": "test-project", "task_id": "test-task"},
            version=1,
        ),
    )


@pytest.fixture
def incomplete_context_artifact():
    """Incomplete context.md for testing REVISION_NEEDED."""
    content = """# Контекст

## Описание
Краткое описание без деталей.
"""
    return Artifact(
        name="incomplete_context.md",
        content=content,
        metadata=ArtifactMetadata(
            artifact_type=ArtifactType.CONTEXT,
            producer=AgentRole.PM_SPEC,
            tags={"project_id": "test-project", "task_id": "test-task"},
            version=1,
        ),
    )


@pytest.fixture
def incomplete_spec_artifact():
    """Incomplete spec.md for testing REVISION_NEEDED."""
    content = """# Спецификация

Некоторый текст без структуры и требований.
"""
    return Artifact(
        name="incomplete_spec.md",
        content=content,
        metadata=ArtifactMetadata(
            artifact_type=ArtifactType.SPEC,
            producer=AgentRole.PM_SPEC,
            tags={"project_id": "test-project", "task_id": "test-task"},
            version=1,
        ),
    )


@pytest.fixture
def incomplete_design_artifact():
    """Incomplete design.md for testing REVISION_NEEDED."""
    content = """# Дизайн

Просто текст без архитектурных решений и плана.
"""
    return Artifact(
        name="incomplete_design.md",
        content=content,
        metadata=ArtifactMetadata(
            artifact_type=ArtifactType.DESIGN,
            producer=AgentRole.ARCHITECT,
            tags={"project_id": "test-project", "task_id": "test-task"},
            version=1,
        ),
    )
