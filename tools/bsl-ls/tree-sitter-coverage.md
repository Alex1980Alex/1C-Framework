# tree-sitter-bsl Coverage Analysis Report

Date: 2026-04-17
tree-sitter-bsl version: 0.1.6
tree-sitter version: 0.25.2

## Test Files

| # | Module | Type | Lines | Parse OK | Errors |
|---|--------|------|-------|----------|--------|
| 1 | гкс_АсинхронныеСервисы (CommonModule Server) | CommonModule (server) | 102 | NO | 6 |
| 2 | гкс_ИнтеграцияMFM (CommonModule Integration) | CommonModule (integration) | 528 | YES | 0 |
| 3 | MCPToolkit Form (Form Module) | Form Module (managed) | 12442 | NO | 181 |

## File 1: гкс_АсинхронныеСервисы (CommonModule Server)

- **Path**: `D:\1С-Framework\src\projects\configuration\260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС\src\CommonModules\гкс_АсинхронныеСервисы\Ext\Module.bsl`
- **Lines**: 102
- **Parse error**: True
- **Root node type**: `source_file`
- **Total nodes**: 770
- **Top-level nodes**: 12

### Top-level Node Types

- `preprocessor`
- `line_comment`
- `line_comment`
- `function_definition`
- `preprocessor`
- `preprocessor`
- `function_definition`
- `function_definition`
- `preprocessor`
- `preprocessor`
- `procedure_definition`
- `preprocessor`

### ERROR Nodes

**6 ERROR nodes found.** First 10:

| Line | Col | Text |
|------|-----|------|
| 89 | 28 | `(` |
| 89 | 86 | `)` |
| 90 | 22 | `(` |
| 90 | 74 | `)` |
| 92 | 15 | `(` |
| 92 | 66 | `)` |

### Preprocessor Directives

- **Count**: 6
- **Node types found**: ['preprocessor', 'text_match:#КонецОбласти', 'text_match:#Область']
- **Text matches**: ['text_match:#КонецОбласти', 'text_match:#Область']

### Compile Directives

- **Count**: 0
- **Node types found**: []
- **Text matches**: []

### Export Keyword

- **Count**: 7
- **Node types**: ['EXPORT_KEYWORD', 'function_definition', 'source_file']

### Query Language in Strings

- **Count**: 0
- **Node types**: []

### Node Type Distribution (top 20)

| Node Type | Count |
|-----------|-------|
| `identifier` | 120 |
| `expression` | 87 |
| `(` | 43 |
| `)` | 43 |
| `;` | 41 |
| `method_call` | 36 |
| `arguments` | 36 |
| `"` | 36 |
| `access` | 30 |
| `.` | 29 |
| `call_expression` | 20 |
| `const_expression` | 20 |
| `assignment_statement` | 19 |
| `=` | 19 |
| `string` | 18 |
| `string_content` | 18 |
| `,` | 11 |
| `operator` | 10 |
| `call_statement` | 9 |
| `property` | 9 |

## File 2: гкс_ИнтеграцияMFM (CommonModule Integration)

- **Path**: `D:\1С-Framework\src\projects\configuration\260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС\src\CommonModules\гкс_ИнтеграцияMFM\Ext\Module.bsl`
- **Lines**: 528
- **Parse error**: False
- **Root node type**: `source_file`
- **Total nodes**: 3481
- **Top-level nodes**: 88

### Top-level Node Types

- `preprocessor`
- `preprocessor`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `procedure_definition`
- `line_comment`
- `preprocessor`
- `line_comment`
- `procedure_definition`
- `preprocessor`
- `preprocessor`
- `preprocessor`
- `procedure_definition`
- `function_definition`
- `function_definition`
- `preprocessor`
- `preprocessor`
- `function_definition`
- `function_definition`
- `function_definition`
- `function_definition`
- `function_definition`
- `function_definition`
- `function_definition`
- `function_definition`
- `function_definition`
- `function_definition`
- `preprocessor`
- `preprocessor`
- `function_definition`
- `procedure_definition`
- `procedure_definition`
- `procedure_definition`
- `procedure_definition`
- `preprocessor`
- `preprocessor`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `function_definition`
- `function_definition`
- `procedure_definition`
- `function_definition`
- `preprocessor`
- `preprocessor`

### ERROR Nodes

No ERROR nodes found.

### Preprocessor Directives

- **Count**: 14
- **Node types found**: ['preprocessor', 'text_match:#КонецОбласти', 'text_match:#Область']
- **Text matches**: ['text_match:#КонецОбласти', 'text_match:#Область']

### Compile Directives

- **Count**: 0
- **Node types found**: []
- **Text matches**: []

### Export Keyword

- **Count**: 5
- **Node types**: ['EXPORT_KEYWORD', 'procedure_definition', 'source_file']

### Query Language in Strings

- **Count**: 0
- **Node types**: []

### Node Type Distribution (top 20)

| Node Type | Count |
|-----------|-------|
| `identifier` | 563 |
| `expression` | 384 |
| `;` | 195 |
| `)` | 176 |
| `(` | 172 |
| `arguments` | 148 |
| `access` | 146 |
| `.` | 146 |
| `method_call` | 130 |
| `=` | 107 |
| `assignment_statement` | 103 |
| `,` | 102 |
| `"` | 102 |
| `property` | 81 |
| `const_expression` | 75 |
| `property_access` | 71 |
| `call_expression` | 65 |
| `string_content` | 56 |
| `line_comment` | 53 |
| `//` | 53 |

## File 3: MCPToolkit Form (Form Module)

- **Path**: `D:\1С-Framework\tools\1c-mcp-toolkit\toolkit\1c-mcp-toolkit-main\1c\MCPToolkit\MCPToolkit\Forms\Форма\Ext\Form\Module.bsl`
- **Lines**: 12442
- **Parse error**: True
- **Root node type**: `source_file`
- **Total nodes**: 109186
- **Top-level nodes**: 1076

### Top-level Node Types

- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `var_definition`
- `preprocessor`
- `var_definition`
- `preprocessor`
- `var_definition`
- `preprocessor`
- `var_definition`
- `preprocessor`
- `var_definition`
- `preprocessor`
- `var_definition`
- `line_comment`
- `preprocessor`
- `var_definition`
- `line_comment`
- `preprocessor`
- `var_definition`
- `line_comment`
- `preprocessor`
- `var_definition`
- `line_comment`
- `preprocessor`
- `var_definition`
- `line_comment`
- `preprocessor`
- `var_definition`
- `line_comment`
- `preprocessor`
- `var_definition`
- `line_comment`
- `preprocessor`
- `var_definition`
- `line_comment`
- `preprocessor`
- `var_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `function_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `line_comment`
- `line_comment`
- `line_comment`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `procedure_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`
- `preprocessor`
- `function_definition`

### ERROR Nodes

**181 ERROR nodes found.** First 10:

| Line | Col | Text |
|------|-----|------|
| 1178 | 33 | `(` |
| 1178 | 96 | `)` |
| 1766 | 18 | `(` |
| 1766 | 113 | `)` |
| 1829 | 22 | `;` |
| 1995 | 40 | `(` |
| 1995 | 94 | `)` |
| 1995 | 103 | `(` |
| 1995 | 217 | `)` |
| 2105 | 38 | `(` |

### Preprocessor Directives

- **Count**: 236
- **Node types found**: ['preprocessor']
- **Text matches**: []

### Compile Directives

- **Count**: 236
- **Node types found**: ['annotation', 'text_match:&НаКлиенте', 'text_match:&НаСервере']
- **Text matches**: ['text_match:&НаСервере', 'text_match:&НаКлиенте']

### Export Keyword

- **Count**: 27
- **Node types**: ['EXPORT_KEYWORD', 'procedure_definition', 'source_file']

### Query Language in Strings

- **Count**: 183
- **Node types**: ['arguments', 'assignment_statement', 'binary_expression', 'call_expression', 'call_statement', 'const_expression', 'else_clause', 'elseif_clause', 'expression', 'function_definition', 'if_statement', 'line_comment', 'method_call', 'new_expression', 'source_file', 'string', 'string_content', 'try_statement']

### Node Type Distribution (top 20)

| Node Type | Count |
|-----------|-------|
| `expression` | 14202 |
| `identifier` | 13705 |
| `"` | 6868 |
| `;` | 5834 |
| `const_expression` | 4997 |
| `)` | 4482 |
| `(` | 4468 |
| `arguments` | 4169 |
| `method_call` | 3886 |
| `string` | 3435 |
| `string_content` | 3434 |
| `access` | 3245 |
| `.` | 3178 |
| `,` | 2410 |
| `operator` | 2209 |
| `call_expression` | 2184 |
| `binary_expression` | 2074 |
| `call_statement` | 1880 |
| `=` | 1820 |
| `assignment_statement` | 1762 |

## Gap Analysis Summary

### Overall Statistics

- **Total files analyzed**: 3
- **Total ERROR nodes**: 187
- **Unique node types seen**: 35
- **Preprocessor node types**: ['preprocessor', 'text_match:#КонецОбласти', 'text_match:#Область']
- **Compile directive node types**: ['annotation', 'text_match:&НаКлиенте', 'text_match:&НаСервере']

### Preprocessor Directive Coverage

- PASS: Preprocessor directives have dedicated AST node types.

### Compile Directive Coverage

- PASS: Compile directives have dedicated AST node types.

### Query Language Coverage

- Queries are present in source files (inside string literals).
- **GAP**: Query language inside strings is NOT parsed as query AST nodes. This is expected for a BSL grammar (queries are string-domain), but means tree-sitter cannot provide query-level AST without a separate grammar.

### Export Keyword Coverage

- PASS: Export keyword is present in parsed nodes.

## Recommendations

1. **ERROR nodes**: Investigate each ERROR node to determine if the grammar lacks rules for specific BSL constructs.
2. **Preprocessor directives**: If grammar does not recognize preprocessor directives, add them as grammar rules.
3. **Compile directives**: If compile directives are not parsed correctly, form module analysis will be incomplete.
4. **Query language**: Query text inside strings is expected to be opaque to the BSL grammar. A separate query language grammar (tree-sitter-1c-query) would be needed for query AST support.
