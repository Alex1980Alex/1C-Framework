# Provider Configuration Guide

Руководство по настройке AI провайдеров для Auto-Documenter.

## Обзор провайдеров

Auto-Documenter поддерживает несколько AI провайдеров с автоматическим переключением между ними.

| Провайдер | Бесплатный лимит | Модель по умолчанию | Качество |
|-----------|------------------|---------------------|----------|
| **Gemini** | 1,500 req/day | `gemini-2.5-pro-latest` | ★★★★★ |
| **Groq** | 500k tokens/day | `llama-3.3-70b-versatile` | ★★★★☆ |
| **Ollama** | Неограничено | `qwen2.5-coder:7b` | ★★★☆☆ |
| **OpenRouter** | Платный | `anthropic/claude-3.5-sonnet` | ★★★★★ |
| **Grok** | Платный | `grok-beta` | ★★★★☆ |

## Быстрая настройка

### Минимальная конфигурация (бесплатная)

```bash
# В run-autodoc.bat или .env файле
set ENABLE_ROTATION=true
set PRIMARY_PROVIDER=gemini
set GEMINI_API_KEY=your-gemini-api-key
```

### Расширенная конфигурация (рекомендуется)

```bash
# Основные настройки
set ENABLE_ROTATION=true
set PRIMARY_PROVIDER=gemini
set ENABLE_AUTO_ROTATION=true

# API ключи
set GEMINI_API_KEY=your-gemini-api-key
set GROQ_API_KEY=your-groq-api-key

# Опционально: custom модели
set GEMINI_MODEL=gemini-2.5-flash-lite
set GROQ_MODEL=llama-3.3-70b-versatile
set OLLAMA_MODEL=qwen2.5-coder:7b
```

## Получение API ключей

### Google Gemini (рекомендуется)

1. Перейдите на [Google AI Studio](https://ai.google.dev/)
2. Создайте проект или используйте существующий
3. Перейдите в "API Keys" → "Create API Key"
4. Скопируйте ключ и сохраните в переменную `GEMINI_API_KEY`

**Лимиты бесплатного тарифа:**
- 1,500 запросов в день
- 60 запросов в минуту
- 2 миллиона токенов в день

### Groq

1. Зарегистрируйтесь на [Groq Console](https://console.groq.com/)
2. Перейдите в "API Keys" → "Create API Key"
3. Сохраните ключ в `GROQ_API_KEY`

**Лимиты бесплатного тарифа:**
- 500,000 токенов в день
- 30 запросов в минуту

### Ollama (локальный)

1. Установите Ollama: https://ollama.ai/download
2. Запустите сервис: `ollama serve`
3. Загрузите модель: `ollama pull qwen2.5-coder:7b`

**Преимущества:**
- Неограниченное использование
- Работает без интернета
- Данные остаются локально

**Требования:**
- 8+ GB RAM для 7B модели
- 16+ GB RAM для 14B модели

### OpenRouter (платный)

1. Зарегистрируйтесь на [OpenRouter](https://openrouter.ai/)
2. Пополните баланс (минимум $5)
3. Создайте API ключ
4. Сохраните в `OPENROUTER_API_KEY`

### Grok (платный)

1. Получите доступ через X Premium
2. Создайте API ключ в настройках
3. Сохраните в `GROK_API_KEY`

## Rotation Strategy

### Автоматическое переключение

Auto-Documenter автоматически переключается между провайдерами при ошибках:

```
gemini → groq → ollama → (error)
```

**Настройка порога ошибок:**

```javascript
// По умолчанию: 3 ошибки до переключения
const config = {
  maxErrorsBeforeFallback: 3,
  enableAutoRotation: true
};
```

### Приоритет провайдеров

Порядок fallback:
1. **PRIMARY_PROVIDER** (по умолчанию: gemini)
2. **Groq** - быстрый, большой бесплатный лимит
3. **Ollama** - локальный, всегда доступен

### Отключение rotation

```bash
# Использовать только один провайдер
set ENABLE_ROTATION=false
set OPENROUTER_API_KEY=your-key
```

## Выбор модели

### Gemini модели

| Модель | Скорость | Качество | Рекомендация |
|--------|----------|----------|--------------|
| `gemini-2.5-pro-latest` | Средняя | Отличное | Документация |
| `gemini-2.5-flash-lite` | Высокая | Хорошее | Быстрая генерация |
| `gemini-1.5-pro` | Медленная | Отличное | Сложный код |

### Groq модели

| Модель | Контекст | Качество |
|--------|----------|----------|
| `llama-3.3-70b-versatile` | 128K | Отличное |
| `mixtral-8x7b-32768` | 32K | Хорошее |
| `llama-guard-3-8b` | 8K | Безопасность |

### Ollama модели

| Модель | Размер | RAM | Качество |
|--------|--------|-----|----------|
| `qwen2.5-coder:7b` | 4.4GB | 8GB | Хорошее |
| `qwen2.5-coder:14b` | 8.9GB | 16GB | Отличное |
| `codellama:7b` | 3.8GB | 8GB | Среднее |
| `deepseek-coder:6.7b` | 3.8GB | 8GB | Хорошее |

## Мониторинг использования

### Проверка статуса

```typescript
// В коде
const client = new OpenRouterClient();
client.printUsageStats();
```

### Пример вывода

```
📊 Provider Usage Statistics:

👉 GEMINI:
   Requests: 150
   Tokens: 450,000
   Errors: 0
   Last Used: 11/26/2025, 10:30:00 AM

   GROQ:
   Requests: 0
   Tokens: 0
   Errors: 0
   Last Used: 11/26/2025, 9:00:00 AM
```

### Предупреждения о лимитах

Auto-Documenter автоматически предупреждает при приближении к лимитам:

```
⚠️ Approaching Gemini daily limit (1450/1500 requests)
⚠️ Approaching Groq daily limit (480,000/500,000 tokens)
```

## Стоимость

### Бесплатные провайдеры

| Провайдер | Ежемесячная стоимость |
|-----------|----------------------|
| Gemini Free | $0 |
| Groq Free | $0 |
| Ollama | $0 (электричество) |

### Платные провайдеры (примерные цены)

| Провайдер | Input (per 1M tokens) | Output (per 1M tokens) |
|-----------|----------------------|------------------------|
| Gemini Pro | $0.075 | $0.30 |
| GPT-4 Turbo | $10.00 | $30.00 |
| Claude 3.5 | $3.00 | $15.00 |

### Расчёт стоимости

При среднем запросе в 2000 токенов и 1000 токенов ответа:

- **Gemini Free**: ~500 документов/день бесплатно
- **Groq Free**: ~165 документов/день бесплатно
- **При платном использовании**: ~$0.001 за документ

## Troubleshooting

### "OpenRouter API key is required"

**Решение:**
```bash
set ENABLE_ROTATION=true
set GEMINI_API_KEY=your-key
```

### "Provider GEMINI failed"

**Возможные причины:**
1. Неверный API ключ
2. Превышен дневной лимит
3. Временные проблемы сервиса

**Решение:** Система автоматически переключится на Groq/Ollama

### "All providers failed"

**Проверьте:**
1. Все API ключи корректны
2. Ollama запущен (`ollama serve`)
3. Интернет-соединение работает

### Медленная генерация

**Попробуйте:**
1. Использовать `gemini-2.5-flash-lite` вместо `pro`
2. Переключиться на локальный Ollama
3. Уменьшить размер анализируемых файлов

## Лучшие практики

1. **Всегда настраивайте резервные провайдеры**
   - Gemini + Groq + Ollama для максимальной надёжности

2. **Используйте локальный Ollama для чувствительного кода**
   - Данные не покидают вашу машину

3. **Мониторьте использование**
   - Регулярно проверяйте статистику
   - Планируйте под лимиты бесплатного тарифа

4. **Выбирайте правильную модель**
   - Быстрая: `gemini-2.5-flash-lite`
   - Качественная: `gemini-2.5-pro-latest`
   - Локальная: `qwen2.5-coder:7b`

## Пример полной конфигурации

### run-autodoc.bat

```batch
@echo off
:: Auto-Documenter MCP Server Configuration

:: Provider Rotation
set ENABLE_ROTATION=true
set PRIMARY_PROVIDER=gemini
set ENABLE_AUTO_ROTATION=true

:: API Keys
set GEMINI_API_KEY=AIzaSy...your-key
set GROQ_API_KEY=gsk_...your-key

:: Models (optional overrides)
set GEMINI_MODEL=gemini-2.5-flash-lite
set GROQ_MODEL=llama-3.3-70b-versatile
set OLLAMA_MODEL=qwen2.5-coder:7b

:: Cost limits (optional)
set DAILY_BUDGET=5.00
set MONTHLY_BUDGET=50.00

:: Start server
node build/index.js
```

## Связанная документация

- [CLI Usage Guide](../CLI-USAGE-GUIDE.md) - Использование CLI
- [BSL Development Guide](BSL_DEVELOPMENT_GUIDE.md) - Работа с 1C:Enterprise
- [Troubleshooting](../troubleshooting/README.md) - Решение проблем
