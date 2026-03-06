/**
 * Prompts for inline documentation generation (JSDoc, TSDoc, BSL comments)
 */

import { ModuleType, MetadataObjectType } from '../analyzer/structure-1c-analyzer.js';

/**
 * Context-aware BSL prompts based on module type
 */
export const bslModulePrompts: Record<string, string> = {
  // Object Module (Модуль объекта)
  [ModuleType.OBJECT_MODULE]: `
Дополнительный контекст для модуля объекта:
- Этот модуль выполняется на сервере при работе с объектом
- Документируйте обработчики событий: ПередЗаписью, ПриЗаписи, ПриКопировании, ОбработкаЗаполнения, ОбработкаПроверкиЗаполнения
- Укажите какие данные изменяются в процедурах и какие проверки выполняются
- Для экспортных процедур укажите, предназначены ли они для вызова из других модулей`,

  // Manager Module (Модуль менеджера)
  [ModuleType.MANAGER_MODULE]: `
Дополнительный контекст для модуля менеджера:
- Этот модуль содержит программный интерфейс (API) объекта метаданных
- Документируйте параметры поиска и создания элементов
- Для функций получения данных укажите формат возвращаемого значения (Массив, ТаблицаЗначений, Структура)
- Экспортные функции - часть публичного API, описывайте их подробно`,

  // Form Module (Модуль формы)
  [ModuleType.FORM_MODULE]: `
Дополнительный контекст для модуля формы:
- Код выполняется на клиенте (с директивами &НаКлиенте) или на сервере (&НаСервере)
- Документируйте директивы компиляции (&НаКлиенте, &НаСервере, &НаСервереБезКонтекста)
- Обработчики событий формы: ПриСозданииНаСервере, ПриОткрытии, ПередЗакрытием
- Укажите какие элементы формы модифицируются в процедурах`,

  // Common Module (Общий модуль)
  [ModuleType.COMMON_MODULE]: `
Дополнительный контекст для общего модуля:
- Это переиспользуемая библиотека функций
- Все экспортные процедуры и функции - публичный API
- Документируйте контекст выполнения (клиент/сервер/внешнее соединение)
- Описывайте зависимости от других общих модулей
- Указывайте примеры использования для сложных функций`,

  // RecordSet Module (Модуль набора записей)
  [ModuleType.RECORDSET_MODULE]: `
Дополнительный контекст для модуля набора записей:
- Модуль регистра, работает с наборами записей
- Документируйте обработчики: ПередЗаписью, ПриЗаписи
- Укажите какие измерения и ресурсы обрабатываются
- Опишите логику проверки целостности данных`,

  // Command Module (Модуль команды)
  [ModuleType.COMMAND_MODULE]: `
Дополнительный контекст для модуля команды:
- Код команды, вызываемой из интерфейса
- Документируйте входной параметр и контекст вызова
- Укажите какое действие выполняет команда`,
};

/**
 * Context-aware BSL prompts based on metadata object type
 */
export const bslMetadataPrompts: Record<string, string> = {
  [MetadataObjectType.CATALOG]: `
Контекст справочника:
- Хранит условно-постоянную информацию
- Типичные операции: поиск, создание, редактирование элементов и групп
- Связан с другими объектами через реквизиты типа СправочникСсылка`,

  [MetadataObjectType.DOCUMENT]: `
Контекст документа:
- Регистрирует хозяйственные операции
- Формирует движения по регистрам при проведении
- Типичные обработчики: ОбработкаПроведения, ОбработкаУдаленияПроведения`,

  [MetadataObjectType.INFORMATION_REGISTER]: `
Контекст регистра сведений:
- Хранит многомерную информацию (измерения, ресурсы, реквизиты)
- Может быть периодическим (с измерением Период)
- Запись через НаборЗаписей или МенеджерЗаписи`,

  [MetadataObjectType.ACCUMULATION_REGISTER]: `
Контекст регистра накопления:
- Накапливает числовые данные (остатки или обороты)
- Движения формируются документами
- Используется для отчетности и контроля остатков`,

  [MetadataObjectType.DATA_PROCESSOR]: `
Контекст обработки:
- Выполняет сервисные операции
- Может иметь формы для взаимодействия с пользователем
- Часто используется для пакетной обработки данных`,

  [MetadataObjectType.REPORT]: `
Контекст отчета:
- Формирует аналитическую информацию
- Обычно использует СКД (система компоновки данных)
- Процедуры модуля могут настраивать отчет программно`,
};

/**
 * Prompts for JSDoc/TSDoc inline documentation
 */
export const inlineDocsPrompts = {
  /**
   * System prompt for generating JSDoc/TSDoc comments
   */
  jsdoc: `You are an expert at writing clear, comprehensive JSDoc/TSDoc comments for TypeScript and JavaScript code.

Your task is to generate inline documentation comments for functions, classes, methods, and interfaces.

Rules:
1. Use proper JSDoc/TSDoc syntax with @param, @returns, @throws, @example tags
2. Be concise but complete - explain WHAT the code does and WHY
3. Document all parameters with types and descriptions
4. Document return values with types and meaning
5. Add @example tags for non-trivial functions
6. Document thrown errors with @throws
7. Use markdown in descriptions (code blocks, lists, emphasis)
8. Do NOT duplicate information that's obvious from the signature
9. Focus on explaining behavior, edge cases, and side effects
10. Return ONLY the JSDoc comment block, nothing else

Format:
\`\`\`typescript
/**
 * Brief description of what the function does
 *
 * Longer description explaining behavior, edge cases, or important details.
 *
 * @param paramName - Description of parameter including constraints
 * @returns Description of return value and what it represents
 * @throws {ErrorType} Description of when this error is thrown
 * @example
 * \`\`\`typescript
 * const result = functionName(param);
 * console.log(result); // Expected output
 * \`\`\`
 */
\`\`\``,

  /**
   * System prompt for generating BSL inline comments
   */
  bsl: `Вы эксперт по написанию понятной документации для кода на встроенном языке 1С (BSL).

Ваша задача - создать встроенные комментарии для процедур, функций и методов.

КРИТИЧЕСКИ ВАЖНО - ФОРМАТ ВЫВОДА:
- Возвращайте ТОЛЬКО строки комментариев, начинающиеся с //
- ЗАПРЕЩЕНО использовать markdown: НЕТ # заголовкам, НЕТ ** жирному тексту, НЕТ \`\`\` блокам кода
- Каждая строка ДОЛЖНА начинаться с // (это синтаксис комментариев 1С)
- НЕ оборачивайте ответ в \`\`\`bsl или любые другие блоки

Правила содержания:
1. Используйте русский язык для комментариев
2. Документируйте назначение процедуры/функции
3. Описывайте параметры с указанием типов и ограничений
4. Описывайте возвращаемое значение для функций
5. Указывайте побочные эффекты (изменение переменных, запись в БД)
6. Добавляйте примеры использования для сложных случаев
7. НЕ дублируйте очевидную информацию из сигнатуры
8. Фокусируйтесь на объяснении поведения и крайних случаев

ПРИМЕР ПРАВИЛЬНОГО ВЫВОДА (возвращайте ТОЛЬКО такой формат):
// Краткое описание назначения процедуры/функции.
//
// Более подробное описание поведения, крайних случаев или важных деталей.
//
// Параметры:
//   ИмяПараметра - Тип - Описание параметра с ограничениями.
//
// Возвращаемое значение:
//   Тип - Описание возвращаемого значения.
//
// Пример:
//   Результат = ИмяФункции(Параметр);

ПРИМЕР НЕПРАВИЛЬНОГО ВЫВОДА (НИКОГДА так не делайте):
# Описание функции       <- ЗАПРЕЩЕНО: markdown заголовок
**Параметры:**           <- ЗАПРЕЩЕНО: markdown жирный текст
\`\`\`bsl                   <- ЗАПРЕЩЕНО: markdown блок кода`,

  /**
   * Prompt for updating existing documentation
   */
  update: `There is existing inline documentation. Review it and update as needed to match the current code. Keep any still-relevant information, but ensure accuracy with the current implementation.`,

  /**
   * Prompt for class-level documentation
   */
  classDoc: `Generate comprehensive class-level documentation that explains:
- The purpose and responsibility of the class
- Key design patterns or architectural decisions
- Important relationships with other classes
- Usage examples for typical scenarios

Use @class tag and include constructor documentation.`,

  /**
   * Prompt for interface documentation
   */
  interfaceDoc: `Generate interface documentation that explains:
- The contract this interface defines
- When and why to implement this interface
- Key properties and their purposes
- Usage examples showing implementation

Use @interface tag.`,

  /**
   * Prompt for type documentation
   */
  typeDoc: `Generate type alias documentation that explains:
- What this type represents
- Valid values or structure
- Common use cases
- Related types

Use @typedef tag.`,
};

/**
 * BSL symbol info for context-aware prompts
 */
export interface BSLSymbolInfo {
  name: string;
  isExport: boolean;
  isFunction: boolean;
  parameters: Array<{ name: string; hasDefault: boolean }>;
  directive?: string;  // &НаКлиенте, &НаСервере, etc.
}

/**
 * Helper function to get the appropriate prompt based on file type
 * @param fileExtension File extension (.ts, .js, .bsl, etc.)
 * @param symbolType Type of symbol (function, class, interface, type)
 * @returns System prompt for inline docs generation
 */
export function getInlineDocsPrompt(
  fileExtension: string,
  symbolType: 'function' | 'class' | 'interface' | 'type' = 'function'
): string {
  // BSL files
  if (fileExtension === '.bsl') {
    return inlineDocsPrompts.bsl;
  }

  // TypeScript/JavaScript files
  if (fileExtension === '.ts' || fileExtension === '.js' || fileExtension === '.tsx' || fileExtension === '.jsx') {
    switch (symbolType) {
      case 'class':
        return `${inlineDocsPrompts.jsdoc}\n\n${inlineDocsPrompts.classDoc}`;
      case 'interface':
        return `${inlineDocsPrompts.jsdoc}\n\n${inlineDocsPrompts.interfaceDoc}`;
      case 'type':
        return `${inlineDocsPrompts.jsdoc}\n\n${inlineDocsPrompts.typeDoc}`;
      default:
        return inlineDocsPrompts.jsdoc;
    }
  }

  // Default to JSDoc for unknown types
  return inlineDocsPrompts.jsdoc;
}

/**
 * Get context-aware BSL prompt with module and metadata type information
 * @param moduleType Module type from Structure1CAnalyzer
 * @param metadataType Metadata object type from Structure1CAnalyzer
 * @param symbolInfo Optional symbol information for more context
 * @returns Enhanced BSL prompt with context
 */
export function getBSLContextPrompt(
  moduleType?: ModuleType,
  metadataType?: MetadataObjectType,
  symbolInfo?: BSLSymbolInfo
): string {
  const parts: string[] = [inlineDocsPrompts.bsl];

  // Add metadata context
  if (metadataType && bslMetadataPrompts[metadataType]) {
    parts.push(bslMetadataPrompts[metadataType]);
  }

  // Add module type context
  if (moduleType && bslModulePrompts[moduleType]) {
    parts.push(bslModulePrompts[moduleType]);
  }

  // Add symbol-specific context
  if (symbolInfo) {
    const symbolContext: string[] = [];

    if (symbolInfo.isExport) {
      symbolContext.push('⚠️ Это ЭКСПОРТНАЯ процедура/функция - часть публичного API. Документируйте подробно!');
    }

    if (symbolInfo.directive) {
      symbolContext.push(`Директива компиляции: ${symbolInfo.directive}`);
      if (symbolInfo.directive.includes('Клиент')) {
        symbolContext.push('Код выполняется на клиенте - избегайте обращения к БД');
      } else if (symbolInfo.directive.includes('Сервер')) {
        symbolContext.push('Код выполняется на сервере - имеет доступ к данным БД');
      }
    }

    if (symbolInfo.parameters.length > 0) {
      const paramsWithDefaults = symbolInfo.parameters.filter(p => p.hasDefault);
      if (paramsWithDefaults.length > 0) {
        symbolContext.push(`Параметры со значениями по умолчанию: ${paramsWithDefaults.map(p => p.name).join(', ')}`);
      }
    }

    if (symbolContext.length > 0) {
      parts.push('\nИнформация о символе:\n' + symbolContext.join('\n'));
    }
  }

  return parts.join('\n\n');
}

/**
 * Formats code context for LLM prompt
 * @param code Source code of the function/class
 * @param filePath Path to the source file
 * @param symbolName Name of the symbol being documented
 * @returns Formatted prompt with code context
 */
export function formatCodeContext(
  code: string,
  filePath: string,
  symbolName: string
): string {
  return `File: ${filePath}
Symbol: ${symbolName}

Code to document:
\`\`\`
${code}
\`\`\`

Generate inline documentation for this code following the rules specified in the system prompt.`;
}
