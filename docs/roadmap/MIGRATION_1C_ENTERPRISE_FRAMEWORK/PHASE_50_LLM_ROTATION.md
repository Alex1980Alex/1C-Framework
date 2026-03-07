# Фаза 50: LLM Rotation Service

**Tier:** 3 — Memory и AI-сервисы
**Статус:** DONE
**Зависимости:** Фаза 44 (Infrastructure)
**Оценка:** ~4 часа

---

## Цель

Перенести мульти-провайдер LLM сервис с автоматическим fallback между провайдерами.

---

## Компонент

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\shared\` |
| **Цель** | `D:\1С-Framework\src\shared\llm_rotation\` |
| **LOC** | ~2,000 |

---

## 5 LLM-провайдеров

| # | Провайдер | Модель | Приоритет | Стоимость |
|---|-----------|--------|-----------|----------|
| 1 | Mistral AI | mistral-small-latest | Primary | Free tier |
| 2 | OpenRouter | llama-3.3-70b | Fallback 1 | Pay-per-use |
| 3 | Gemini | gemini-2.0-flash | Fallback 2 | Free tier |
| 4 | Ollama Cloud | varies | Fallback 3 | Free |
| 5 | Ollama Local | varies | Fallback 4 | Free (local) |

**Ротация:** при ошибке/rate limit автоматическое переключение на следующий.

---

## Ключевые файлы

```
shared/
├── llm_rotation_service.py    # Core service (~800 LOC)
├── llm_rotation_mcp.py        # MCP wrapper
├── zai_proxy.py               # Z.AI proxy integration
└── README.md
```

---

## Интеграция с 1С-Framework

**Текущие LLM в 1С-Framework:**
- Claude Opus 4.6 — main LLM
- Claude Sonnet 4.5 — fast (grading, rewrite, vision)
- Z.AI proxy — для Sonnet

**Решение:** LLM Rotation как **дополнительный fallback-слой** для задач, не требующих Claude:
- BSL документация (auto-documenter уже использует Gemini/Groq)
- Embeddings (Ollama для nomic-embed-text)
- Lightweight analysis (code reasoning)

Claude остаётся primary для RAG/search/agents.

---

## Шаги

### 50.1 Перенести shared/

```bash
mkdir -p src/shared/llm_rotation
cp D:/1C-Enterprise_Framework/shared/llm_rotation_service.py src/shared/llm_rotation/service.py
cp D:/1C-Enterprise_Framework/shared/llm_rotation_mcp.py src/shared/llm_rotation/mcp.py
cp D:/1C-Enterprise_Framework/shared/zai_proxy.py src/shared/llm_rotation/zai_proxy.py
touch src/shared/llm_rotation/__init__.py
```

### 50.2 Адаптировать конфиг

```python
# src/shared/llm_rotation/config.py
from pydantic_settings import BaseSettings

class LLMRotationSettings(BaseSettings):
    primary_provider: str = "mistral"
    mistral_api_key: str = ""
    openrouter_api_key: str = ""
    gemini_api_key: str = ""
    ollama_url: str = "http://localhost:11434"
    zai_api_key: str = ""
    zai_base_url: str = "https://api.z.ai/api/anthropic"

    class Config:
        env_prefix = "LLM_ROTATION_"
        env_file = ".env"
```

### 50.3 Интегрировать Z.AI proxy

Z.AI уже настроен в 1С-Framework. Проверить что `zai_proxy.py` совместим.

### 50.4 Тест: fallback цепочка

```python
# tests/test_llm_rotation.py
async def test_fallback_chain():
    """При ошибке primary -> автопереключение на fallback."""
    service = LLMRotationService(settings)
    # Mock: Mistral returns error
    result = await service.generate("test prompt")
    assert result.provider in ["openrouter", "gemini", "ollama"]
```

### 50.5 MCP wrapper

Зарегистрировать `llm_rotate` tool для доступа из Claude Code.

---

## Чеклист завершения

- [x] `src/shared/llm_rotation/` содержит service, mcp, zai_proxy
- [x] Config через pydantic-settings (`.env`)
- [x] Fallback: Zhipu -> Gemini -> OpenRouter -> Mistral -> Ollama
- [x] Z.AI proxy интегрирован
- [x] Тест fallback цепочки проходит (33/33)
- [x] MCP tools (5 шт.) доступны в `.mcp.json`
- [x] Skill `llm-rotation/SKILL.md` создан
- [ ] Git commit: `feat: Phase 50 — LLM Rotation Service`
