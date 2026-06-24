"""Unit: Contextual Retrieval на free-LLM (ADR-040 Фаза 5) — детерминированный guard.

Проверяет промоут context_generator в Category 1 → cheap-LLM (free rotation) включён по умолчанию,
без env-оверрайда и без платного Anthropic-ключа.

NB: робастность ContextGenerator к отсутствию ключа (self._llm=None, без ValidationError) проверена
LIVE (см. ADR-040 Фаза 5) — pytest-юнит на неё не делаем: импорт ContextGenerator тянет цепочку
parent_child → langchain_text_splitters → sentence_transformers, чей импорт внутри pytest-процесса
даёт нативный segfault (известная torch+pytest коллизия порядка импорта; standalone-импорт OK).
"""

import pytest

pytestmark = pytest.mark.unit


def test_context_generator_cheap_enabled_by_default(monkeypatch):
    # Cat-1 промоут: cheap-LLM (free rotation) для context_generator включён БЕЗ env-оверрайда
    monkeypatch.delenv("LLM_ROTATION_COMPONENTS", raising=False)
    monkeypatch.setenv("LLM_ROTATION_ENABLED", "true")
    from src.shared.llm_rotation import adapter

    adapter._enabled_components = None  # сброс кеша модуля
    try:
        assert adapter.COMPONENT_REGISTRY["context_generator"]["category"] == 1
        assert adapter.is_cheap_llm_enabled("context_generator") is True
    finally:
        adapter._enabled_components = None  # не протекать в другие тесты
