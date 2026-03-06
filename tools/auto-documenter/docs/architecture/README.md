# Architecture Documentation

This directory contains architectural documentation for the Auto-Documenter MCP server.

## Files

### project-plan.md
Original architectural plan with system diagrams:
- System architecture flowchart
- Bottom-up processing sequence diagram
- Core components overview
- **Note:** This document predates the Provider Rotation implementation

### ROTATION_IMPLEMENTATION.md
Technical documentation of the Provider Rotation system:
- Architecture of provider switching mechanism
- Factory pattern implementation (`provider-factory.ts`)
- Rotation manager (`provider-rotation.ts`)
- Usage tracking and statistics
- Three operational modes (free-only, local-only, paid+free)
- Integration points with OpenRouter client

### BSL_ANALYZER.md
Technical architecture of BSL (1C:Enterprise) code analysis:
- Tree-sitter-based parsing system
- 11 module type detection algorithms
- BSL-specific context prompt generation
- Export detection and region extraction
- Bottom-up documentation aggregation
- Data flow diagrams and processing pipelines
- Performance characteristics and test coverage
- Future enhancements roadmap (v2.1.0+)

### METADATA_ANALYZER.md ⭐ NEW
Technical architecture of 1C:Enterprise metadata XML parsing:
- TypeScript type system for 1C metadata structures
- XML parsing with xml2js (Catalog, Document, DataProcessor, CommonModule)
- Automatic BSL file discovery and linking
- LLM context generation with metadata information
- 5-strategy XML file location algorithm
- Integration with documentation tool
- Non-blocking error handling and graceful degradation
- Performance characteristics and future enhancements (v2.2.0+)

## Key Concepts

### Provider Rotation
Automatic failover system that switches between AI providers to minimize costs and maximize availability:

```
Gemini (free, 1500/day)
   ↓ fallback on error/limit
Groq (free, 500k tokens/day)
   ↓ fallback on error
Ollama (local, unlimited)
   ↓ fallback on error
OpenRouter (paid, backup)
```

### Bottom-Up Processing
The system analyzes directories starting from leaf nodes and working upward, ensuring child documentation is available when processing parent directories.

## Related Documentation

- **Guides:** [../guides/](../guides/) - Setup and usage instructions
- **Development:** [../development/](../development/) - Code reviews and technical analysis
- **Reference:** [../reference/](../reference/) - API reference (to be added)
