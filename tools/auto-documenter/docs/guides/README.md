# User Guides

This directory contains practical guides for setting up and using the Auto-Documenter MCP server.

## Files

### FREE_TIER_SETUP.md (348 lines)
Comprehensive guide for configuring free AI providers:
- Step-by-step setup for Google Gemini
- Step-by-step setup for Groq
- Step-by-step setup for Ollama (local)
- Cost comparison tables
- Provider rotation strategy
- Expected daily capacity: ~1,533 modules for free

### SETUP_COMPLETE.md (121 lines)
Quick setup confirmation for basic Gemini integration:
- Gemini API key configuration
- Basic rotation setup
- Cost savings summary ($60-150/month → $0/month)
- Next steps after setup

### GROK_SETUP_COMPLETE.md (172 lines)
Documentation for xAI Grok integration:
- Grok API configuration
- Updated rotation strategy including Grok
- Grok features (advanced reasoning, real-time knowledge)
- When Grok is used in the rotation
- Cost analysis with Grok included
- Usage tracking information

### BSL_DEVELOPMENT_GUIDE.md ⭐ NEW
Complete guide for 1C:Enterprise (BSL) projects:
- BSL-specific features and module types
- Russian language and Cyrillic folder support
- Tree-sitter parsing capabilities
- Context-aware documentation generation
- Export detection and region support
- Usage examples with real BSL code
- Testing and troubleshooting BSL projects
- Best practices for 1C:Enterprise development

## Quick Start

1. **Choose your strategy:**
   - **Free-only (recommended):** Follow FREE_TIER_SETUP.md
   - **Quick start:** Follow SETUP_COMPLETE.md for basic Gemini setup
   - **Advanced:** Add Grok following GROK_SETUP_COMPLETE.md
   - **1C:Enterprise/BSL users:** Also read BSL_DEVELOPMENT_GUIDE.md

2. **Get API keys:**
   - Gemini: https://aistudio.google.com/apikey (free)
   - Groq: https://console.groq.com/ (free)
   - Grok: https://x.ai/ (paid)

3. **Configure environment:**
   - Edit `claude_desktop_config.json`
   - Add API keys to env section
   - Set `ENABLE_ROTATION=true`
   - Choose `PRIMARY_PROVIDER`

4. **Restart Claude Code**

## Cost Comparison

| Strategy | Cost | Daily Capacity |
|----------|------|----------------|
| **Free-only** (Gemini + Groq + Ollama) | $0/month | ~1,533 modules |
| **With Grok** (Gemini → Grok → Ollama) | ~$5-10/month | unlimited |
| **OpenRouter only** (old approach) | $60-150/month | unlimited |

## Related Documentation

- **Architecture:** [../architecture/](../architecture/) - System design
- **Troubleshooting:** [../troubleshooting/](../troubleshooting/) - Common issues
- **Development:** [../development/](../development/) - Technical details
