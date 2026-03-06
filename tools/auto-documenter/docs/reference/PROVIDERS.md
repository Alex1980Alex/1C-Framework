# Providers Reference

Detailed configuration guide for all supported AI providers.

## Provider Overview

| Provider | Cost | Speed | Quality | Best For |
|----------|------|-------|---------|----------|
| **Gemini** | Free | Fast | High | General use, free tier |
| **Groq** | Free | Fastest | Good | High volume, speed |
| **Ollama** | Free | Slow | Variable | Privacy, offline |
| **Grok** | Paid | Fast | High | X/Twitter context |
| **OpenRouter** | Paid | Variable | Best | Model selection |

---

## Gemini (Google)

### Configuration

```bash
# Environment variable
export GEMINI_API_KEY=your_api_key_here

# Or CLI
autodoc generate ./src --provider gemini --api-key your_key
```

### Models

| Model | Speed | Quality | Context | Notes |
|-------|-------|---------|---------|-------|
| `gemini-2.5-flash-latest` | Fast | High | 1M | **Default**, recommended |
| `gemini-2.5-pro-latest` | Slow | Highest | 1M | Complex tasks |
| `gemini-1.5-flash` | Fastest | Good | 1M | Simple tasks |

### Rate Limits (Free Tier)

- **Requests per day:** 1,500
- **Requests per minute:** 15
- **Tokens per minute:** 1,000,000

### Best Practices

1. Use flash models for documentation generation
2. Use pro models for complex code analysis
3. Batch requests to avoid rate limits

---

## Groq

### Configuration

```bash
export GROQ_API_KEY=your_api_key_here
```

### Models

| Model | Speed | Quality | Context | Notes |
|-------|-------|---------|---------|-------|
| `llama-3.3-70b-versatile` | Fast | High | 128K | **Default** |
| `llama-3.1-8b-instant` | Fastest | Good | 128K | Quick tasks |
| `mixtral-8x7b-32768` | Fast | Good | 32K | Balanced |

### Rate Limits (Free Tier)

- **Tokens per day:** 500,000
- **Requests per minute:** 30

### Best Practices

1. Excellent for high-volume processing
2. Use 8b model for simple documentation
3. Use 70b for code reviews

---

## Ollama (Local)

### Configuration

```bash
# No API key needed - runs locally
# Install Ollama first: https://ollama.ai

# Pull required model
ollama pull deepseek-r1:14b
```

### Models

| Model | Size | Speed | Quality | Notes |
|-------|------|-------|---------|-------|
| `deepseek-r1:14b` | 14B | Medium | High | **Default**, reasoning |
| `codellama:13b` | 13B | Fast | Good | Code focused |
| `qwen2.5-coder:14b` | 14B | Medium | High | Coding |
| `llama3.2:3b` | 3B | Fastest | Basic | Quick tests |

### System Requirements

| Model Size | RAM Required | GPU VRAM |
|------------|-------------|----------|
| 3B | 8GB | 4GB |
| 7-8B | 16GB | 8GB |
| 13-14B | 32GB | 16GB |
| 70B | 64GB+ | 48GB+ |

### Best Practices

1. Start with smaller models to test
2. Use GPU acceleration when available
3. Ideal for sensitive/private code

---

## Grok (xAI)

### Configuration

```bash
export XAI_API_KEY=your_api_key_here
```

### Models

| Model | Speed | Quality | Context | Notes |
|-------|-------|---------|---------|-------|
| `grok-2-1212` | Fast | High | 128K | **Default** |
| `grok-2-vision-1212` | Fast | High | 128K | With images |

### Pricing

- **Input:** $2.00 / 1M tokens
- **Output:** $10.00 / 1M tokens

### Best Practices

1. Good for code with social context
2. Strong reasoning capabilities
3. Consider cost for large projects

---

## OpenRouter

### Configuration

```bash
export OPENROUTER_API_KEY=your_api_key_here
```

### Models

Access to 100+ models through unified API:

| Model | Provider | Quality | Price |
|-------|----------|---------|-------|
| `anthropic/claude-3.5-sonnet` | Anthropic | Highest | $$$ |
| `openai/gpt-4o` | OpenAI | Highest | $$$ |
| `google/gemini-2.0-flash-exp` | Google | High | $ |
| `meta-llama/llama-3.3-70b-instruct` | Meta | High | $ |

### Best Practices

1. Use for accessing best models
2. Good for comparing providers
3. Pay-per-use, no subscriptions

---

## Provider Rotation

### How It Works

When `ENABLE_ROTATION=true`, the system automatically:

1. Tries the primary provider
2. On failure, rotates to next available provider
3. Continues until success or all providers exhausted

### Priority Order

```typescript
const ROTATION_ORDER = [
  'gemini',     // Try free Gemini first
  'groq',       // Then free Groq
  'ollama',     // Then local Ollama
  'grok',       // Then paid Grok
  'openrouter'  // Finally OpenRouter
];
```

### Configuration

```bash
# Set primary provider
export PRIMARY_PROVIDER=gemini

# Enable/disable rotation
export ENABLE_ROTATION=true
```

---

## Choosing a Provider

### For Free Tier Users

1. **Start with Gemini** - Best quality/free balance
2. **Add Groq** as backup - Fast, high limits
3. **Consider Ollama** - For privacy/offline

### For Production

1. **OpenRouter** - Access to best models
2. **Enable rotation** - For reliability
3. **Monitor costs** - Track token usage

### For Development

1. **Ollama** - Free, unlimited testing
2. **Gemini** - When online access needed
3. **Switch to production** provider when ready

---

## Environment Variables Summary

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google AI API key | For Gemini |
| `GROQ_API_KEY` | Groq API key | For Groq |
| `XAI_API_KEY` | xAI API key | For Grok |
| `OPENROUTER_API_KEY` | OpenRouter key | For OpenRouter |
| `PRIMARY_PROVIDER` | Default provider | Optional |
| `ENABLE_ROTATION` | Enable failover | Optional |

---

*Last updated: 2025-11-26*
