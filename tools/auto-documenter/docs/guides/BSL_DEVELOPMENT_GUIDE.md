# BSL Development Guide

Complete guide for using Auto-Documenter with 1C:Enterprise (BSL) projects.

## Overview

Auto-Documenter v2.0.0 includes full support for 1C:Enterprise Business Script Language (BSL) with:
- **Tree-sitter parsing** - Accurate AST-based code analysis
- **11 module types detection** - Form, Object, Manager, Common, Command, etc.
- **Russian language support** - Cyrillic folder names and documentation
- **Context-aware prompts** - Module-specific documentation templates
- **Region detection** - Support for #Область/#Region structures

## Quick Start with BSL

### 1. Basic Setup

Ensure you have configured at least one AI provider (see [FREE_TIER_SETUP.md](FREE_TIER_SETUP.md)).

### 2. Project Structure

Auto-Documenter works best with standard 1C:Enterprise project structures:

```
src/
├── Configuration/
│   ├── Ext/
│   │   ├── ManagedApplicationModule.bsl
│   │   └── SessionModule.bsl
├── Catalogs/
│   └── Товары/
│       ├── Ext/
│       │   ├── ManagerModule.bsl
│       │   └── ObjectModule.bsl
│       └── Forms/
│           └── ФормаЭлемента/
│               └── Ext/Form/Module.bsl
├── Documents/
├── DataProcessors/
└── CommonModules/
```

Both English (`Forms`) and Russian (`Формы`) folder names are supported.

### 3. Generate Documentation

```json
// Call from Claude Code
{
  "name": "generate_documentation",
  "input": {
    "path": "/path/to/your/bsl/project",
    "updateExisting": false
  }
}
```

This will:
1. Analyze all `.bsl` files recursively
2. Detect module types automatically
3. Generate context-specific documentation
4. Create `documentation.md` in each directory

## Supported BSL Module Types

Auto-Documenter recognizes 11 distinct 1C:Enterprise module types:

| Module Type | Path Pattern | Documentation Focus |
|-------------|--------------|---------------------|
| **Form** | `/Forms/*/Ext/Form/Module.bsl` | Event handlers, UI logic |
| **Object** | `/Ext/ObjectModule.bsl` | Business logic, validation |
| **Manager** | `/Ext/ManagerModule.bsl` | CRUD operations, queries |
| **Common** | `/CommonModules/*.bsl` | Utility functions, shared logic |
| **Command** | `/Commands/*/Ext/CommandModule.bsl` | User actions, entry points |
| **Session** | `SessionModule.bsl` | Session initialization |
| **Application** | `ApplicationModule.bsl` | App-level events |
| **Managed Application** | `ManagedApplicationModule.bsl` | Client application logic |
| **External Connection** | `ExternalConnectionModule.bsl` | COM/External access |
| **Recordset** | `RecordSetModule.bsl` | Record set operations |
| **Value Manager** | `ValueManagerModule.bsl` | Value type management |

### Russian Folder Name Support

Auto-Documenter automatically recognizes both English and Russian paths:

| English | Russian |
|---------|---------|
| `/Forms/` | `/Формы/` |
| `/Commands/` | `/Команды/` |
| `/CommonModules/` | `/ОбщиеМодули/` |
| `/Catalogs/` | `/Справочники/` |
| `/Documents/` | `/Документы/` |

## BSL-Specific Features

### 1. Context-Aware Documentation

Each module type receives tailored documentation prompts:

**Form Module Example:**
```markdown
## МОДУЛЬ ФОРМЫ

**Основное назначение:** Обработчики событий формы и клиентская логика

**Фокус документации:**
- Event handlers (ПриСозданииНаСервере, ПриОткрытии)
- User interaction logic
- Form initialization
- Button handlers
```

**Manager Module Example:**
```markdown
## МОДУЛЬ МЕНЕДЖЕРА

**Основное назначение:** Работа с объектами на уровне менеджера

**Фокус документации:**
- CRUD operations
- Query functions
- Selection and filtering
```

### 2. Export Detection

Auto-Documenter distinguishes between:
- **Exported procedures/functions** (`Экспорт` keyword) - Public API
- **Internal procedures/functions** - Implementation details

Documentation prioritizes exported symbols while mentioning internal ones.

### 3. Region Support

BSL code organized with regions:
```bsl
#Область ПрограммныйИнтерфейс
// Public API functions
#КонецОбласти

#Область СлужебныеПроцедурыИФункции
// Internal helper functions
#КонецОбласти
```

Auto-Documenter:
- Recognizes both Russian (`#Область`) and English (`#Region`) syntax
- Groups documentation by regions
- Preserves logical code organization

### 4. Parameter Documentation

Automatically extracts and documents:
```bsl
Функция РассчитатьСумму(Товар, Количество, Цена) Экспорт
```

Generated documentation:
```markdown
### РассчитатьСумму

**Параметры:**
- `Товар` - Product reference
- `Количество` - Quantity (number)
- `Цена` - Price (number)

**Возвращаемое значение:** Calculated total amount
```

## Example Usage

### Example 1: Catalog Manager Module

**Input file:** `src/Catalogs/Товары/Ext/ManagerModule.bsl`
```bsl
#Область ПрограммныйИнтерфейс

// Получить список товаров по категории
Функция ПолучитьТоварыПоКатегории(Категория) Экспорт
	Запрос = Новый Запрос;
	Запрос.Текст = "
		|ВЫБРАТЬ
		|	Товары.Ссылка,
		|	Товары.Наименование,
		|	Товары.Цена
		|ИЗ
		|	Справочник.Товары КАК Товары
		|ГДЕ
		|	Товары.Категория = &Категория";

	Запрос.УстановитьПараметр("Категория", Категория);
	Возврат Запрос.Выполнить().Выбрать();
КонецФункции

#КонецОбласти
```

**Generated documentation:**
```markdown
## ManagerModule.bsl - Товары (Products)

### Public API

#### ПолучитьТоварыПоКатегории(Категория)
Retrieves list of products filtered by category.

**Purpose:** Query products with specific category filter

**Parameters:**
- `Категория` - Category reference to filter by

**Returns:** Query selection with product records (Reference, Name, Price)

**Implementation details:**
- Uses parameterized query to prevent SQL injection
- Returns unfiltered selection for iteration
- Selects core product fields only
```

### Example 2: Form Module

**Input file:** `src/Catalogs/Товары/Forms/ФормаЭлемента/Ext/Form/Module.bsl`
```bsl
#Область ОбработчикиСобытийФормы

Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)
	Если Объект.Ссылка.Пустая() Тогда
		// Новый элемент - установить значения по умолчанию
		Объект.Дата = ТекущаяДата();
	КонецЕсли;
КонецПроцедуры

#КонецОбласти

#Область ОбработчикиКомандФормы

Процедура СохранитьИЗакрыть(Команда)
	Если Записать() Тогда
		Закрыть(Объект.Ссылка);
	КонецЕсли;
КонецПроцедуры

#КонецОбласти
```

**Generated documentation:**
```markdown
## Form Module - ФормаЭлемента

### Form Event Handlers

#### ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)
Server-side form initialization handler.

**Purpose:** Initialize new product form with default values

**Logic:**
- Checks if creating new object (empty reference)
- Sets current date as default Date value
- Executes before form is displayed to user

**Parameters:**
- `Отказ` - Cancel form creation if set to True
- `СтандартнаяОбработка` - Standard platform processing flag

### Command Handlers

#### СохранитьИЗакрыть(Команда)
Save and close form command handler.

**Purpose:** Persist changes and close form on success

**Logic:**
1. Attempts to save form data using Записать()
2. If successful, closes form returning object reference
3. If save fails, form remains open for corrections
```

## Testing BSL Documentation

### Unit Tests

Auto-Documenter includes comprehensive BSL unit tests (76 tests):

```bash
npm test
```

Tests cover:
- Module type detection (11 types)
- Russian/English folder names
- Export keyword detection
- Parameter extraction
- Region parsing
- Real-world code patterns

### Integration Testing

Test with sample BSL files:

```bash
# Create test structure
mkdir -p test-bsl/Catalogs/Test/Ext
mkdir -p test-bsl/Catalogs/Test/Forms/Форма/Ext/Form

# Add sample BSL files
# Run documentation
{
  "name": "generate_documentation",
  "input": {
    "path": "./test-bsl"
  }
}
```

## Advanced Features

### Inline Documentation

Generate JSDoc-style inline comments:

```json
{
  "name": "generate_inline_docs",
  "input": {
    "path": "/path/to/bsl/file.bsl"
  }
}
```

**Before:**
```bsl
Функция ПолучитьСумму(Число1, Число2) Экспорт
	Возврат Число1 + Число2;
КонецФункции
```

**After:**
```bsl
// Возвращает сумму двух чисел.
//
// Параметры:
//   Число1 - Число - Первое слагаемое
//   Число2 - Число - Второе слагаемое
//
// Возвращаемое значение:
//   Число - Сумма Число1 и Число2
Функция ПолучитьСумму(Число1, Число2) Экспорт
	Возврат Число1 + Число2;
КонецФункции
```

### Test Plan Generation

Generate test plans for BSL modules:

```json
{
  "name": "autotestplan",
  "input": {
    "path": "/path/to/bsl/project"
  }
}
```

Creates comprehensive test strategy including:
- Unit test scenarios for each function
- Integration test cases for module interactions
- Edge case coverage
- Test data requirements

### Code Review

Automated BSL code review:

```json
{
  "name": "autoreview",
  "input": {
    "path": "/path/to/bsl/project"
  }
}
```

Analyzes:
- Security issues (SQL injection, access control)
- Best practices (export usage, error handling)
- Performance concerns (query optimization)
- Code quality (naming, structure)

## Troubleshooting

### Issue: Module Type Not Detected

**Symptom:** Documentation doesn't include module-specific context

**Causes:**
1. Non-standard directory structure
2. File path doesn't match expected patterns
3. File extension is not `.bsl`

**Solutions:**
- Check file path follows 1C:Enterprise conventions
- Verify `.bsl` extension (not `.txt` or others)
- Review [BSL-specific troubleshooting](../troubleshooting/BSL_ISSUES.md)

### Issue: Russian Characters Garbled

**Symptom:** Russian text displays as ??????

**Cause:** File encoding issue (not UTF-8)

**Solution:**
1. Convert BSL files to UTF-8 encoding
2. Check your editor's encoding settings
3. Use UTF-8 with BOM if required by 1C:Enterprise

### Issue: Export Functions Not Prioritized

**Symptom:** Internal functions documented as prominently as exported

**Cause:** May be parsing issue with `Экспорт` keyword detection

**Solution:**
1. Ensure `Экспорт` keyword is on same line as function declaration
2. Check for extra spaces or typos in `Экспорт`
3. File a bug report with sample code

## Best Practices

### 1. Organize Code with Regions

Use regions to group related functionality:
```bsl
#Область ПрограммныйИнтерфейс
// Public functions exported for external use
#КонецОбласти

#Область ОбработчикиСобытийФормы
// Form event handlers
#КонецОбласти

#Область СлужебныеПроцедурыИФункции
// Internal helper functions
#КонецОбласти
```

Auto-Documenter will preserve this organization in generated docs.

### 2. Use Descriptive Function Names

Russian or transliterated English names work best:
```bsl
// Good
Функция ПолучитьСписокАктивныхПользователей()

// Also good
Функция GetActiveUsersList()

// Less ideal (too generic)
Функция Получить()
```

### 3. Export Only Public API

Mark only functions intended for external use:
```bsl
// Public - exported
Функция СоздатьДокумент(Параметры) Экспорт
	Возврат ВнутренняяФункцияСоздания(Параметры);
КонецФункции

// Internal - not exported
Функция ВнутренняяФункцияСоздания(Параметры)
	// Implementation details
КонецФункции
```

### 4. Add Manual Comments for Complex Logic

While Auto-Documenter generates good documentation, complex algorithms benefit from manual comments:
```bsl
Функция СложныйАлгоритм(Данные) Экспорт
	// Этап 1: Предварительная обработка
	// Используется алгоритм быстрой сортировки для оптимизации
	ОтсортированныеДанные = БыстраяСортировка(Данные);

	// Этап 2: Поиск медианы
	Медиана = НайтиМедиану(ОтсортированныеДанные);

	Возврат Медиана;
КонецФункции
```

### 5. Update Documentation After Refactoring

After significant code changes, regenerate documentation:
```json
{
  "name": "generate_documentation",
  "input": {
    "path": "/path/to/modified/code",
    "updateExisting": true
  }
}
```

## Limitations

### Current Limitations

1. **Metadata Analysis** - Does not analyze 1C metadata (forms, tables) directly, only BSL code
2. **Query Validation** - Does not validate 1C query syntax
3. **Platform API** - Limited knowledge of platform-specific APIs
4. **Configuration Dependencies** - Cannot trace cross-configuration dependencies

### Planned Enhancements (v2.1.0+)

- **Metadata Analyzer** - Parse and document 1C metadata objects
- **Event Handler Detection** - Automatically identify form/document event handlers
- **Enhanced Region Support** - Better handling of nested regions
- **Query Analysis** - Validate and document query complexity
- **API Reference Generation** - Create comprehensive API documentation

## Examples from Real Projects

### Catalog Manager Module
See [examples/catalog-manager.md](../reference/examples/catalog-manager.md)

### Form with Multiple Event Handlers
See [examples/complex-form.md](../reference/examples/complex-form.md)

### Common Module with Utilities
See [examples/utility-module.md](../reference/examples/utility-module.md)

## Related Documentation

- **Architecture:** [BSL Analyzer Architecture](../architecture/BSL_ANALYZER.md)
- **Development:** [BSL Tree-sitter Integration](../development/BSL_TREESITTER.md)
- **Troubleshooting:** [BSL-specific Issues](../troubleshooting/BSL_ISSUES.md)
- **Reference:** [BSL Prompt Templates](../reference/BSL_PROMPTS.md)

## Community and Support

- **GitHub Issues:** Report BSL-specific bugs
- **Examples:** Share your BSL documentation examples
- **Feedback:** Help improve BSL support

## Version History

- **v2.0.0** (Current) - Initial BSL support with tree-sitter
  - 11 module types
  - Russian folder names
  - Context-aware prompts
  - Export detection
  - Region support

- **v2.1.0** (Planned) - Enhanced BSL features
  - Metadata analyzer
  - Event handler detection
  - Improved region handling

---

**Last Updated:** 2025-11-24
**Version:** 2.0.0
