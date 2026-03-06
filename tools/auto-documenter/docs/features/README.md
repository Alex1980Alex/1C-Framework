# Features Documentation

This directory contains detailed documentation for Auto-Documenter's key features.

## 📋 Available Features

### [Form.xml Validation](FORM_XML_VALIDATION.md) ⭐ **NEW in 2.0**

**Advanced validation system for 1C:Enterprise forms**

Automatically validates 1C forms during documentation generation:

- **Cross-validation** between Form.xml and Module.bsl
- **Quality scoring** (0-100 points)
- **Missing handler detection** - control events and commands
- **Orphaned handler detection** - code without XML references
- **DataPath integrity** checking
- **ConditionalAppearance** validation
- **Automatic integration** - results in documentation context
- **224 unit tests** ensuring reliability

**Status:** ✅ Production Ready

**Documentation:** Complete with examples and API reference

**Use case:** Automatically validates 1C:Enterprise form modules when generating documentation for Catalogs, Documents, and other metadata objects.

---

## 🔧 BSL Support Features

### Context-Aware Prompts

**Intelligent module-type detection for 1C:Enterprise**

The system automatically detects module types and applies specialized documentation prompts:

**11 Module Types:**
1. **Forms** (Формы) - UI event handlers, initialization
2. **Objects** (Объекты) - Business logic, event handlers
3. **Managers** (Менеджеры) - API methods, query generation
4. **Common Modules** (Общие модули) - Shared utilities
5. **Commands** (Команды) - User actions
6. **Session** - Session management
7. **Application** - Application lifecycle
8. **External Connection** - Integration points
9. **Managed Application** - Client-side logic
10. **RecordSet** - Data manipulation
11. **Value Manager** - Computed values

**Implementation:** `src/prompts/bsl-context-prompts.ts` (589 lines)

**Status:** ✅ Production Ready

### Tree-sitter BSL Analyzer

**100% accurate AST-based BSL parsing**

- Procedure/function extraction with parameters
- Export keyword detection (Экспорт/Export)
- Region analysis (#Область/#Region)
- Comment extraction and preservation
- Code statistics (LOC, comment lines)
- Complexity estimation

**Implementation:** `src/analyzer/bsl-treesitter-analyzer.ts` (464 lines)

**Status:** ✅ Production Ready

### Russian Language Documentation

**Native Russian documentation generation**

- Russian language prompts and templates
- 1C:Enterprise terminology
- Parameter and return value documentation
- Usage examples in Russian

**Status:** ✅ Production Ready

### 1C Structure Analyzer ⭐ **NEW in 2.0**

**Automatic detection of 1C:Enterprise configuration structure**

Analyzes file paths to detect metadata object types and module types:

**19 Metadata Object Types:**
- Catalogs (Справочники)
- Documents (Документы)
- DataProcessors (Обработки)
- Reports (Отчеты)
- CommonModules (Общие модули)
- InformationRegisters (Регистры сведений)
- AccumulationRegisters (Регистры накопления)
- AccountingRegisters (Регистры бухгалтерии)
- CalculationRegisters (Регистры расчета)
- BusinessProcesses (Бизнес-процессы)
- Tasks (Задачи)
- ChartsOfCharacteristicTypes (Планы видов характеристик)
- ChartsOfAccounts (Планы счетов)
- ChartsOfCalculationTypes (Планы видов расчета)
- ExchangePlans (Планы обмена)
- Constants (Константы)
- Enums (Перечисления)
- SettingsStorages (Хранилища настроек)
- ScheduledJobs (Регламентные задания)

**10 Module Types:**
- ObjectModule (Модуль объекта)
- ManagerModule (Модуль менеджера)
- FormModule (Модуль формы)
- CommandModule (Модуль команды)
- RecordSetModule (Модуль набора записей)
- ValueManagerModule (Модуль менеджера значений)
- CommonModule (Общий модуль)
- SessionModule (Модуль сеанса)
- ApplicationModule (Модуль приложения)
- ExternalConnectionModule (Модуль внешнего соединения)

**Features:**
- Automatic path parsing for 1C configuration structure
- Support for both English and Russian folder names
- Context generation for LLM documentation prompts
- Documentation guidance based on metadata/module type
- Integration with DocumentationTool

**Implementation:** `src/analyzer/structure-1c-analyzer.ts` (650 lines)

**Test Coverage:** 74 unit tests

**Status:** ✅ Production Ready

---

## 🚀 Provider Rotation

**Automatic failover between AI providers**

Minimize costs and maximize availability:

**5 Supported Providers:**
1. **Google Gemini** (free, 1,500 req/day) - Primary
2. **Groq** (free, 500k tokens/day) - Fallback 1
3. **Ollama** (local, unlimited) - Fallback 2
4. **xAI Grok** (paid) - Optional advanced
5. **OpenRouter** (paid) - Last resort

**Features:**
- Automatic error detection and switching
- Graceful degradation
- Provider health monitoring
- Cost optimization

**Monthly Cost:**
- Free-only: **$0** (~1,533 modules/day)
- With Grok: **$5-10** (unlimited)

**Documentation:** [Provider Rotation Guide](../architecture/ROTATION_IMPLEMENTATION.md)

**Status:** ✅ Production Ready

---

## 📊 Feature Comparison

| Feature | Status | Test Coverage | Documentation |
|---------|--------|---------------|---------------|
| **Form.xml Validation** | ✅ Production | 224 tests | Complete |
| **BSL Context-Aware Prompts** | ✅ Production | Integrated | Complete |
| **Tree-sitter Analyzer** | ✅ Production | Unit tests | Complete |
| **Provider Rotation** | ✅ Production | 36 tests | Complete |
| **Russian Documentation** | ✅ Production | Via BSL tests | Complete |
| **1C Structure Analyzer** | ✅ Production | 74 tests | Complete |
| **Inline Docs Tool** | ⏳ Planned | - | v2.2.0 |

---

## 🎯 Usage Examples

### Form.xml Validation (Automatic)

```typescript
// Just run documentation generation on a 1C form directory
generate_documentation({
  path: "D:/1C-Config/src/Catalogs/Товары/Forms/ФормаЭлемента"
})

// Validation runs automatically and results appear in context:
// === ВАЛИДАЦИЯ ФОРМ ===
// Форма: ФормаЭлемента
// Оценка качества: 85/100
// Отсутствующие обработчики: 2
```

### Context-Aware BSL Documentation

```typescript
// Documentation automatically uses specialized prompts based on module type
generate_documentation({
  path: "D:/1C-Config/src/CommonModules/УправлениеДоступом"
})

// Result: Documentation with Common Module best practices
```

### Provider Rotation

```json
{
  "env": {
    "ENABLE_ROTATION": "true",
    "PRIMARY_PROVIDER": "gemini",
    "GEMINI_API_KEY": "your-key",
    "GROQ_API_KEY": "your-key"
  }
}
```

---

## 📚 Additional Resources

- **[Main README](../../README.md)** - Project overview
- **[Architecture Docs](../architecture/)** - System design
- **[Setup Guides](../guides/)** - Configuration help
- **[Troubleshooting](../troubleshooting/)** - Common issues

---

**Last Updated:** 2025-11-25
**Version:** 2.0 (Form.xml Validation + BSL Support)
