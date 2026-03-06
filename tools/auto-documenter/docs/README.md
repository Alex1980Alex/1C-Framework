# Auto-Documenter Documentation

Welcome to the Auto-Documenter MCP server documentation. This directory contains organized documentation for all aspects of the system.

## 📁 Directory Structure

### [features/](features/)
Feature-specific documentation:
- **[Form.xml Validation](features/FORM_XML_VALIDATION.md)** - 1C:Enterprise form validation system
- BSL analyzer architecture
- Metadata integration

**Start here if:** You want to understand specific features in depth.

### [architecture/](architecture/)
System architecture and design documentation:
- Provider Rotation system design
- Original project plan and diagrams
- Integration points
- Core concepts and patterns

**Start here if:** You want to understand how the system works internally.

### [guides/](guides/)
Practical guides for setup and usage:
- Free tier setup (Gemini, Groq, Ollama)
- Quick start guides
- Grok integration
- Cost optimization strategies

**Start here if:** You want to set up and start using Auto-Documenter.

### [reference/](reference/)
API reference and configuration options:
- Tool parameters and usage
- Provider configuration reference
- Environment variables
- Model selection

**Status:** Planned (not yet implemented)

### [troubleshooting/](troubleshooting/)
Common problems and solutions:
- Running and debugging the server
- Provider errors
- Configuration issues
- Windows-specific problems

**Start here if:** You're experiencing problems.

### [development/](development/)
Technical documentation for contributors:
- Code review and quality analysis
- Known issues and bugs
- Improvement roadmap
- Development setup

**Start here if:** You want to contribute to the codebase.

## 🚀 Quick Navigation

**New users:**
1. [Setup Guide](guides/FREE_TIER_SETUP.md) - Free tier configuration
2. [Troubleshooting](troubleshooting/README-RUN.md) - Common issues

**Understanding the system:**
1. [Architecture](architecture/ROTATION_IMPLEMENTATION.md) - Provider Rotation
2. [Original Plan](architecture/project-plan.md) - System design

**Developers:**
1. [Code Review](development/code-review.md) - Technical analysis
2. [Architecture](architecture/) - System internals

## 💰 Cost Overview

| Configuration | Monthly Cost | Daily Capacity |
|---------------|--------------|----------------|
| Free-only (Gemini + Groq + Ollama) | **$0** | ~1,533 modules |
| With Grok (Gemini + Grok + Ollama) | $5-10 | Unlimited |
| OpenRouter only (legacy) | $60-150 | Unlimited |

## 🎯 Key Features

- **Form.xml Validation** - Advanced validation for 1C:Enterprise forms ([Guide](features/FORM_XML_VALIDATION.md))
  - Cross-validation Form.xml ↔ Module.bsl
  - Quality scoring (0-100)
  - Missing/orphaned handler detection
  - Automatic integration with documentation
- **BSL Support** - Native 1C:Enterprise support with tree-sitter
  - Context-aware prompts for 11 module types
  - Russian language documentation
- **Smart Directory Analysis** - Bottom-up processing
- **AI-Powered Documentation** - Multiple providers
- **Test Plan Generation** - Automated test planning
- **Code Review** - Automated analysis
- **Provider Rotation** - Cost optimization
- **Free Tier Support** - Zero-cost operation possible

## 📊 System Overview

```
MCP Server (stdio)
    ↓
Provider Rotation Manager
    ↓
├─→ Gemini (free, 1500/day)
├─→ Groq (free, 500k tokens/day)
├─→ Ollama (local, unlimited)
├─→ Grok (paid, advanced reasoning)
└─→ OpenRouter (paid, fallback)
    ↓
Documentation Tools
├─→ generate_documentation
├─→ autotestplan
└─→ autoreview
```

## 🔧 Main Tools

### generate_documentation
Generates comprehensive documentation for code:
- Analyzes directory structure
- Documents each file
- Creates organized documentation files
- Supports update mode

### autotestplan
Creates test plans for code:
- Identifies test scenarios
- Suggests test cases
- Generates test structure
- Documents test requirements

### autoreview
Performs automated code review:
- Security analysis
- Best practices check
- Performance review
- Code quality assessment

## 📝 Documentation Standards

This reorganized structure follows best practices:
- **Separation of concerns** - Architecture, guides, reference, troubleshooting
- **Progressive disclosure** - Quick start → Deep dive
- **Clear navigation** - README in each directory
- **Consistent formatting** - Markdown standards

## 🤝 Contributing

See [development/](development/) for:
- Code quality guidelines
- Known issues and roadmap
- Development setup
- Contributing guidelines

## 📚 External Resources

- [MCP Documentation](https://code.claude.com/docs/en/mcp)
- [Google Gemini API](https://ai.google.dev/)
- [Groq API](https://console.groq.com/)
- [Ollama](https://ollama.com/)
- [OpenRouter](https://openrouter.ai/)

## 📄 License

See main project README for license information.

---

**Last Updated:** 2025-11-25
**Version:** 2.0 (Form.xml Validation + BSL Support)
