"""
SonarQube Rules Manager

Phase 45: Миграция из 1C-Enterprise_Framework
"""

from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class BSLRule:
    """Правило анализа BSL кода"""
    key: str
    name: str
    severity: str
    description: str
    tags: List[str]


class RulesManager:
    """Менеджер правил SonarQube для BSL"""

    # Стандартные правила 1С:Предприятие
    DEFAULT_RULES = [
        BSLRule(
            key="bsl:naming-convention",
            name="Соглашения об именовании",
            severity="MAJOR",
            description="Проверка соответствия имен стандартам 1С",
            tags=["convention", "naming"]
        ),
        BSLRule(
            key="bsl:complexity",
            name="Сложность метода",
            severity="MAJOR",
            description="Метод не должен быть слишком сложным",
            tags=["complexity", "maintainability"]
        ),
        BSLRule(
            key="bsl:duplicate-code",
            name="Дублирование кода",
            severity="MINOR",
            description="Обнаружено дублирование кода",
            tags=["duplication", "maintainability"]
        ),
        BSLRule(
            key="bsl:missing-comment",
            name="Отсутствует комментарий",
            severity="INFO",
            description="Метод должен иметь описание",
            tags=["documentation"]
        ),
        BSLRule(
            key="bsl:long-method",
            name="Слишком длинный метод",
            severity="MAJOR",
            description="Метод превышает допустимую длину",
            tags=["maintainability", "readability"]
        ),
    ]

    def __init__(self, config=None):
        self.config = config
        self._rules: Dict[str, BSLRule] = {
            r.key: r for r in self.DEFAULT_RULES
        }

    def get_rule(self, key: str) -> BSLRule:
        """Получение правила по ключу"""
        return self._rules.get(key)

    def get_all_rules(self) -> List[BSLRule]:
        """Получение всех правил"""
        return list(self._rules.values())

    def get_rules_by_tag(self, tag: str) -> List[BSLRule]:
        """Получение правил по тегу"""
        return [r for r in self._rules.values() if tag in r.tags]
