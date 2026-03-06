/**
 * Extended Form Validator - advanced validation and integrity analysis
 *
 * Extends basic FormValidator with:
 * - DataPath integrity validation
 * - Form hierarchy validation
 * - Required event handler checks
 * - Best practice recommendations
 * - Quality scoring
 */

import { FormValidator } from './form-validator.js';
import { EventHandlerDetector } from './event-handler-detector.js';
import * as fs from 'fs';
import {
  IFormStructure,
  IFormValidationResult,
  IExtendedFormValidationResult,
  IFormControl,
  IFormAttribute,
  IDataPathIssue,
  IHierarchyIssue,
  IRequiredHandlerIssue,
  IBestPracticeRecommendation,
  IMissingCommandHandler,
  IOrphanedCommandHandler,
  IConditionalAppearanceIssue,
  FormControlType
} from './form-types.js';

/**
 * Extended Form Validator with advanced integrity checks
 */
export class FormExtendedValidator extends FormValidator {
  /**
   * Perform extended validation with all integrity checks
   */
  async validateFormExtended(
    formXmlPath: string,
    moduleBslPath?: string
  ): Promise<IExtendedFormValidationResult> {
    // First, run basic validation
    const basicValidation = await this.validateForm(formXmlPath, moduleBslPath);

    // Run extended validations
    const dataPathIssues = this.validateDataPaths(basicValidation.formStructure);
    const hierarchyIssues = this.validateHierarchy(basicValidation.formStructure);
    const requiredHandlerIssues = this.checkRequiredHandlers(basicValidation.formStructure);
    const recommendations = this.generateRecommendations(basicValidation);

    // Validate commands
    const commandValidation = await this.validateCommands(basicValidation.formStructure, moduleBslPath);

    // Validate conditional appearance
    const conditionalAppearanceIssues = this.validateConditionalAppearance(basicValidation.formStructure);
    const totalConditionalAppearance = basicValidation.formStructure.conditionalAppearance.length;

    // Calculate quality score
    const qualityScore = this.calculateQualityScore({
      ...basicValidation,
      dataPathIssues,
      hierarchyIssues,
      requiredHandlerIssues,
      recommendations,
      ...commandValidation,
      totalConditionalAppearance,
      conditionalAppearanceIssues,
      qualityScore: 0 // Placeholder
    });

    return {
      ...basicValidation,
      dataPathIssues,
      hierarchyIssues,
      requiredHandlerIssues,
      recommendations,
      ...commandValidation,
      totalConditionalAppearance,
      conditionalAppearanceIssues,
      qualityScore
    };
  }

  /**
   * Validate DataPath integrity - check that all DataPaths reference existing attributes
   */
  private validateDataPaths(formStructure: IFormStructure): IDataPathIssue[] {
    const issues: IDataPathIssue[] = [];

    // Build attribute map for quick lookup
    const attributeMap = new Map<string, IFormAttribute>();
    for (const attr of formStructure.attributes) {
      attributeMap.set(attr.name, attr);

      // Add table attributes with prefix
      if (attr.isTable && attr.tableAttributes) {
        for (const tableAttr of attr.tableAttributes) {
          attributeMap.set(`${attr.name}.${tableAttr.name}`, tableAttr);
        }
      }
    }

    // Standard form object attributes
    attributeMap.set('Объект', { name: 'Объект', type: 'FormDataStructure' });

    // Special platform-provided attributes for list forms and form elements
    attributeMap.set('Список', { name: 'Список', type: 'DynamicList' });
    attributeMap.set('Элементы', { name: 'Элементы', type: 'FormItems' });
    attributeMap.set('Команды', { name: 'Команды', type: 'FormCommands' });

    // Check each control's DataPath
    for (const control of formStructure.controls) {
      if (!control.dataPath) continue;

      // Parse DataPath (e.g., "Объект.Код", "Объект.Товары.Количество")
      const parts = control.dataPath.split('.');

      if (parts.length < 2) {
        // Check if it's a special single-part attribute (like "Список" for dynamic list tables)
        if (control.type === 'Table' && attributeMap.has(control.dataPath)) {
          continue; // Valid table with dynamic list or special attribute
        }

        // Check if it's a valid form-level attribute for other controls
        if (attributeMap.has(control.dataPath)) {
          continue; // Valid form attribute
        }

        // Otherwise invalid format
        issues.push({
          controlName: control.name,
          controlType: control.type,
          dataPath: control.dataPath,
          issueType: 'invalid_format',
          suggestion: 'DataPath должен иметь формат "Объект.Реквизит" или "РеквизитФормы"'
        });
        continue;
      }

      // Check if root attribute exists
      const rootAttr = parts[0];
      if (!attributeMap.has(rootAttr) && rootAttr !== 'Объект') {
        issues.push({
          controlName: control.name,
          controlType: control.type,
          dataPath: control.dataPath,
          issueType: 'missing_attribute',
          expectedAttribute: rootAttr,
          suggestion: `Атрибут "${rootAttr}" не найден в реквизитах формы`
        });
        continue;
      }

      // For multi-level paths (table attributes), check nested attributes
      if (parts.length > 2) {
        const tableName = parts[1];
        const columnName = parts[2];
        const fullPath = `${tableName}.${columnName}`;

        if (!attributeMap.has(tableName) && !attributeMap.has(fullPath)) {
          issues.push({
            controlName: control.name,
            controlType: control.type,
            dataPath: control.dataPath,
            issueType: 'missing_table_attribute',
            expectedAttribute: fullPath,
            suggestion: `Табличный реквизит "${fullPath}" не найден`
          });
        }
      }
    }

    return issues;
  }

  /**
   * Validate form hierarchy - check for invalid nesting and circular references
   */
  private validateHierarchy(formStructure: IFormStructure): IHierarchyIssue[] {
    const issues: IHierarchyIssue[] = [];

    // Build control lookup map
    const controlMap = new Map<string, IFormControl>();
    for (const control of formStructure.controls) {
      controlMap.set(control.name, control);
    }

    // Check for invalid nesting
    for (const control of formStructure.controls) {
      // Input fields should not contain children
      if (control.type === 'InputField' && control.children && control.children.length > 0) {
        issues.push({
          controlName: control.name,
          controlType: control.type,
          issueType: 'invalid_nesting',
          description: 'Поля ввода (InputField) не должны содержать дочерние элементы'
        });
      }

      // Buttons should not contain children
      if (control.type === 'Button' && control.children && control.children.length > 0) {
        issues.push({
          controlName: control.name,
          controlType: control.type,
          issueType: 'invalid_nesting',
          description: 'Кнопки (Button) не должны содержать дочерние элементы'
        });
      }

      // Check for circular parent references
      if (control.parent) {
        const visited = new Set<string>();
        let current: IFormControl | undefined = control;

        while (current && current.parent) {
          if (visited.has(current.name)) {
            issues.push({
              controlName: control.name,
              controlType: control.type,
              parentName: control.parent,
              issueType: 'circular_reference',
              description: `Обнаружена циклическая ссылка в иерархии: ${Array.from(visited).join(' → ')}`
            });
            break;
          }

          visited.add(current.name);
          current = controlMap.get(current.parent);
        }
      }
    }

    // Check for orphaned controls (have parent reference but parent doesn't exist)
    for (const control of formStructure.controls) {
      if (control.parent && !controlMap.has(control.parent)) {
        issues.push({
          controlName: control.name,
          controlType: control.type,
          parentName: control.parent,
          issueType: 'orphaned_control',
          description: `Родительский элемент "${control.parent}" не найден`
        });
      }
    }

    return issues;
  }

  /**
   * Check for required event handlers based on form type and controls
   */
  private checkRequiredHandlers(formStructure: IFormStructure): IRequiredHandlerIssue[] {
    const issues: IRequiredHandlerIssue[] = [];

    // Check if form has OnCreateAtServer (highly recommended)
    const hasOnCreateAtServer = formStructure.formEvents.some(
      e => e.eventType === 'OnCreateAtServer'
    );

    if (!hasOnCreateAtServer) {
      issues.push({
        eventType: 'OnCreateAtServer',
        reason: 'Событие ПриСозданииНаСервере необходимо для инициализации формы на сервере',
        severity: 'warning',
        suggestedHandlerName: 'ПриСозданииНаСервере'
      });
    }

    // Check tables for required events
    const tables = formStructure.controls.filter(c => c.type === 'Table');
    for (const table of tables) {
      // Tables with editable data should have validation events
      const hasBeforeAddRow = table.events.some(e => e.eventType === 'BeforeAddRow');
      const hasBeforeDeleteRow = table.events.some(e => e.eventType === 'BeforeDeleteRow');

      if (!hasBeforeAddRow && !table.readOnly) {
        issues.push({
          eventType: 'BeforeAddRow',
          reason: `Таблица "${table.name}" должна иметь обработчик ПередНачаломДобавления для контроля добавления строк`,
          severity: 'info',
          suggestedHandlerName: `${table.name}ПередНачаломДобавления`
        });
      }

      if (!hasBeforeDeleteRow && !table.readOnly) {
        issues.push({
          eventType: 'BeforeDeleteRow',
          reason: `Таблица "${table.name}" должна иметь обработчик ПередУдалением для контроля удаления строк`,
          severity: 'info',
          suggestedHandlerName: `${table.name}ПередУдалением`
        });
      }
    }

    // Check input fields with StartChoice for ChoiceProcessing
    const fieldsWithStartChoice = formStructure.controls.filter(
      c => c.type === 'InputField' && c.events.some(e => e.eventType === 'StartChoice')
    );

    for (const field of fieldsWithStartChoice) {
      const hasChoiceProcessing = field.events.some(e => e.eventType === 'ChoiceProcessing');

      if (!hasChoiceProcessing) {
        issues.push({
          eventType: 'ChoiceProcessing',
          reason: `Поле "${field.name}" с НачалоВыбора должно иметь обработчик ОбработкаВыбора`,
          severity: 'warning',
          suggestedHandlerName: `${field.name}ОбработкаВыбора`
        });
      }
    }

    return issues;
  }

  /**
   * Validate form commands - check if Action handlers exist in Module.bsl
   */
  private async validateCommands(
    formStructure: IFormStructure,
    moduleBslPath?: string
  ): Promise<{
    totalCommands: number;
    commandsWithHandlers: number;
    missingCommandHandlers: IMissingCommandHandler[];
    orphanedCommandHandlers: IOrphanedCommandHandler[];
  }> {
    const totalCommands = formStructure.commands.length;
    let commandsWithHandlers = 0;
    const missingCommandHandlers: IMissingCommandHandler[] = [];
    const orphanedCommandHandlers: IOrphanedCommandHandler[] = [];

    if (totalCommands === 0) {
      return {
        totalCommands: 0,
        commandsWithHandlers: 0,
        missingCommandHandlers: [],
        orphanedCommandHandlers: []
      };
    }

    // If no module path provided or doesn't exist, we can't validate handlers
    if (!moduleBslPath || !fs.existsSync(moduleBslPath)) {
      return {
        totalCommands,
        commandsWithHandlers: 0,
        missingCommandHandlers: [],
        orphanedCommandHandlers: []
      };
    }

    // Analyze Module.bsl to get all procedures
    const detector = new EventHandlerDetector();
    const handlerAnalysis = await detector.analyzeFormModule(moduleBslPath);

    // Build set of all procedure names from all handler types
    const allHandlers = [
      ...handlerAnalysis.handlersByType.formEvents,
      ...handlerAnalysis.handlersByType.controlEvents,
      ...handlerAnalysis.handlersByType.commandHandlers,
      ...handlerAnalysis.handlersByType.notificationHandlers,
      ...handlerAnalysis.handlersByType.unknown
    ];

    const procedureNames = new Set(allHandlers.map(h => h.name));

    // Check each command for handler existence
    for (const command of formStructure.commands) {
      if (!command.action) {
        // Command without Action is not an error - might be a separator or menu
        continue;
      }

      if (procedureNames.has(command.action)) {
        commandsWithHandlers++;
        // Mark handler as used
        command.handlerExists = true;
      } else {
        // Missing handler
        missingCommandHandlers.push({
          commandName: command.name,
          handlerName: command.action,
          title: command.title && command.title.length > 0 ? command.title[0].content : undefined
        });
        command.handlerExists = false;
      }
    }

    // Find orphaned command handlers
    // Command handlers typically match pattern: CommandName (without suffixes like ПриИзменении)
    const commandActionNames = new Set(
      formStructure.commands.filter(c => c.action).map(c => c.action!)
    );

    for (const handler of allHandlers) {
      // Skip if it's already matched as a command handler
      if (commandActionNames.has(handler.name)) continue;

      // Skip if it's a known event handler (has event suffix)
      const eventSuffixes = [
        'ПриИзменении', 'НачалоВыбора', 'Нажатие', 'ПриАктивизацииСтроки',
        'ПриСозданииНаСервере', 'ПриОткрытии', 'ПередЗакрытием', 'ПриЗакрытии',
        'ПередНачаломДобавления', 'ПередУдалением', 'ОбработкаВыбора'
      ];

      const hasEventSuffix = eventSuffixes.some(suffix => handler.name.endsWith(suffix));
      if (hasEventSuffix) continue;

      // Check if it looks like a command handler (no common event suffixes)
      // This is a heuristic - command handlers are usually simple names
      if (handler.isExported || handler.name.length < 50) {
        orphanedCommandHandlers.push({
          handlerName: handler.name,
          lineNumber: handler.lineNumber,
          isExported: handler.isExported
        });
      }
    }

    return {
      totalCommands,
      commandsWithHandlers,
      missingCommandHandlers,
      orphanedCommandHandlers
    };
  }

  /**
   * Validate conditional appearance - check field references and condition structure
   */
  private validateConditionalAppearance(formStructure: IFormStructure): IConditionalAppearanceIssue[] {
    const issues: IConditionalAppearanceIssue[] = [];

    // Build control name map
    const controlNames = new Set(formStructure.controls.map(c => c.name));

    // Build attribute map for DataPath validation
    const attributeNames = new Set(formStructure.attributes.map(a => a.name));
    attributeNames.add('Объект');
    attributeNames.add('Список');

    for (const item of formStructure.conditionalAppearance) {
      // Validate fields - must reference existing controls
      for (const field of item.fields) {
        if (!controlNames.has(field)) {
          issues.push({
            itemId: item.id,
            issueType: 'invalid_field',
            description: `Поле "${field}" не найдено среди элементов формы`,
            affectedFields: [field],
            suggestion: `Проверьте имя элемента управления в условном оформлении`
          });
        }
      }

      // Validate conditions
      if (item.conditions.length === 0) {
        issues.push({
          itemId: item.id,
          issueType: 'missing_condition',
          description: 'Условное оформление не содержит условий применения',
          affectedFields: item.fields,
          suggestion: 'Добавьте хотя бы одно условие в Filter'
        });
        continue;
      }

      for (const condition of item.conditions) {
        // Validate left operand (usually DataPath)
        if (condition.left && condition.left.includes('.')) {
          const rootAttr = condition.left.split('.')[0];
          if (!attributeNames.has(rootAttr) && rootAttr !== 'Объект') {
            issues.push({
              itemId: item.id,
              issueType: 'invalid_datapath',
              description: `Некорректный DataPath в условии: "${condition.left}"`,
              affectedFields: item.fields,
              suggestion: `Атрибут "${rootAttr}" не найден в реквизитах формы`
            });
          }
        }

        // Validate comparison type
        const validComparisons = [
          'Equal', 'NotEqual', 'Greater', 'GreaterOrEqual',
          'Less', 'LessOrEqual', 'InList', 'NotInList',
          'Filled', 'NotFilled'
        ];

        if (!validComparisons.includes(condition.comparisonType)) {
          issues.push({
            itemId: item.id,
            issueType: 'invalid_condition',
            description: `Неизвестный тип сравнения: "${condition.comparisonType}"`,
            affectedFields: item.fields,
            suggestion: `Используйте один из стандартных типов: ${validComparisons.join(', ')}`
          });
        }
      }
    }

    return issues;
  }

  /**
   * Generate best practice recommendations
   */
  private generateRecommendations(validation: IFormValidationResult): IBestPracticeRecommendation[] {
    const recommendations: IBestPracticeRecommendation[] = [];

    // Performance: Too many controls with events
    if (validation.controlsWithHandlers > 20) {
      recommendations.push({
        category: 'performance',
        title: 'Большое количество элементов с обработчиками',
        description: `Форма содержит ${validation.controlsWithHandlers} элементов с обработчиками событий. Рассмотрите возможность оптимизации логики.`,
        priority: 'medium'
      });
    }

    // Usability: Too many unused controls
    if (validation.unusedControls.length > 10) {
      recommendations.push({
        category: 'usability',
        title: 'Много неиспользуемых элементов управления',
        description: `Форма содержит ${validation.unusedControls.length} элементов без обработчиков. Возможно, они не нужны или требуют доработки.`,
        affectedItems: validation.unusedControls.slice(0, 5).map(c => c.name),
        priority: 'low'
      });
    }

    // Maintainability: Low event coverage
    if (validation.coverage.eventCoverage < 80) {
      recommendations.push({
        category: 'maintainability',
        title: 'Низкое покрытие событий обработчиками',
        description: `Только ${validation.coverage.eventCoverage.toFixed(1)}% событий имеют реализованные обработчики. Это может указывать на незавершенную разработку.`,
        priority: 'high'
      });
    }

    // Maintainability: Orphaned handlers
    if (validation.orphanedHandlers.length > 5) {
      recommendations.push({
        category: 'maintainability',
        title: 'Много неиспользуемых обработчиков',
        description: `Найдено ${validation.orphanedHandlers.length} обработчиков, не привязанных к событиям формы. Рекомендуется удалить устаревший код.`,
        affectedItems: validation.orphanedHandlers.slice(0, 5).map(h => h.handlerName),
        priority: 'medium'
      });
    }

    // Security: Form events without handlers (potential security issue)
    const formEventsWithoutHandlers = validation.formStructure.formEvents.filter(
      e => !e.handlerExists
    );

    if (formEventsWithoutHandlers.length > 0) {
      recommendations.push({
        category: 'security',
        title: 'События формы без обработчиков',
        description: 'Некоторые события формы объявлены в Form.xml, но не имеют реализации. Это может привести к ошибкам выполнения.',
        affectedItems: formEventsWithoutHandlers.map(e => e.handlerName),
        priority: 'high'
      });
    }

    return recommendations;
  }

  /**
   * Calculate overall quality score (0-100)
   */
  private calculateQualityScore(validation: IExtendedFormValidationResult): number {
    let score = 100;

    // Deduct points for errors
    score -= validation.errors.length * 10;

    // Deduct points for warnings
    score -= validation.warnings.length * 2;

    // Deduct points for DataPath issues
    score -= validation.dataPathIssues.length * 5;

    // Deduct points for hierarchy issues
    score -= validation.hierarchyIssues.length * 8;

    // Deduct points for missing required handlers
    const criticalHandlers = validation.requiredHandlerIssues.filter(h => h.severity === 'critical').length;
    const warningHandlers = validation.requiredHandlerIssues.filter(h => h.severity === 'warning').length;
    score -= criticalHandlers * 10;
    score -= warningHandlers * 5;

    // Deduct points for missing command handlers
    score -= validation.missingCommandHandlers.length * 6;

    // Deduct points for conditional appearance issues
    score -= validation.conditionalAppearanceIssues.length * 4;

    // Bonus for high coverage
    if (validation.coverage.eventCoverage >= 90) {
      score += 10;
    }

    // Bonus for complete command implementation
    if (validation.totalCommands > 0 && validation.commandsWithHandlers === validation.totalCommands) {
      score += 5;
    }

    // Ensure score is within bounds
    return Math.max(0, Math.min(100, score));
  }

  /**
   * Generate extended validation report
   */
  generateExtendedReport(validation: IExtendedFormValidationResult): string {
    let report = this.generateValidationReport(validation);

    // Add quality score section
    report += `\n## 🎯 Оценка качества: ${validation.qualityScore}/100\n\n`;

    // Quality interpretation
    if (validation.qualityScore >= 90) {
      report += `✅ **Отлично!** Форма имеет высокое качество и соответствует лучшим практикам.\n\n`;
    } else if (validation.qualityScore >= 70) {
      report += `✔️ **Хорошо.** Форма в целом качественная, но есть области для улучшения.\n\n`;
    } else if (validation.qualityScore >= 50) {
      report += `⚠️ **Удовлетворительно.** Форма требует доработки в нескольких областях.\n\n`;
    } else {
      report += `❌ **Требуется доработка.** Форма имеет множественные проблемы, требующие исправления.\n\n`;
    }

    // DataPath issues
    if (validation.dataPathIssues.length > 0) {
      report += `## 🔗 Проблемы DataPath (${validation.dataPathIssues.length})\n\n`;
      for (const issue of validation.dataPathIssues) {
        report += `- **${issue.controlName}** (${issue.controlType})\n`;
        report += `  - DataPath: \`${issue.dataPath}\`\n`;
        report += `  - Проблема: ${issue.issueType}\n`;
        if (issue.suggestion) {
          report += `  - Рекомендация: ${issue.suggestion}\n`;
        }
        report += `\n`;
      }
    }

    // Hierarchy issues
    if (validation.hierarchyIssues.length > 0) {
      report += `## 🏗️ Проблемы иерархии (${validation.hierarchyIssues.length})\n\n`;
      for (const issue of validation.hierarchyIssues) {
        report += `- **${issue.controlName}** (${issue.controlType})\n`;
        report += `  - Тип проблемы: ${issue.issueType}\n`;
        report += `  - Описание: ${issue.description}\n`;
        report += `\n`;
      }
    }

    // Required handlers
    if (validation.requiredHandlerIssues.length > 0) {
      report += `## 📋 Рекомендуемые обработчики (${validation.requiredHandlerIssues.length})\n\n`;

      const bySeverity = {
        critical: validation.requiredHandlerIssues.filter(h => h.severity === 'critical'),
        warning: validation.requiredHandlerIssues.filter(h => h.severity === 'warning'),
        info: validation.requiredHandlerIssues.filter(h => h.severity === 'info')
      };

      if (bySeverity.critical.length > 0) {
        report += `### ❌ Критические (${bySeverity.critical.length})\n\n`;
        for (const issue of bySeverity.critical) {
          report += `- **${issue.eventType}**\n`;
          report += `  - Причина: ${issue.reason}\n`;
          if (issue.suggestedHandlerName) {
            report += `  - Предлагаемое имя: \`${issue.suggestedHandlerName}\`\n`;
          }
          report += `\n`;
        }
      }

      if (bySeverity.warning.length > 0) {
        report += `### ⚠️ Предупреждения (${bySeverity.warning.length})\n\n`;
        for (const issue of bySeverity.warning) {
          report += `- **${issue.eventType}**\n`;
          report += `  - Причина: ${issue.reason}\n`;
          if (issue.suggestedHandlerName) {
            report += `  - Предлагаемое имя: \`${issue.suggestedHandlerName}\`\n`;
          }
          report += `\n`;
        }
      }

      if (bySeverity.info.length > 0) {
        report += `### ℹ️ Информационные (${bySeverity.info.length})\n\n`;
        for (const issue of bySeverity.info.slice(0, 5)) {
          report += `- **${issue.eventType}**: ${issue.reason}\n`;
        }
        if (bySeverity.info.length > 5) {
          report += `- ... и еще ${bySeverity.info.length - 5}\n`;
        }
        report += `\n`;
      }
    }

    // Commands validation
    if (validation.totalCommands > 0) {
      report += `## ⌘ Команды формы (${validation.totalCommands})\n\n`;
      report += `**Команд с обработчиками:** ${validation.commandsWithHandlers}/${validation.totalCommands}\n\n`;

      if (validation.missingCommandHandlers.length > 0) {
        report += `### ❌ Отсутствующие обработчики команд (${validation.missingCommandHandlers.length})\n\n`;
        for (const missing of validation.missingCommandHandlers) {
          report += `- **${missing.commandName}**\n`;
          if (missing.title) {
            report += `  - Заголовок: "${missing.title}"\n`;
          }
          report += `  - Требуемый обработчик: \`${missing.handlerName}\`\n`;
          report += `\n`;
        }
      }

      if (validation.orphanedCommandHandlers.length > 0 && validation.orphanedCommandHandlers.length <= 10) {
        report += `### ⚠️ Возможно неиспользуемые обработчики (${validation.orphanedCommandHandlers.length})\n\n`;
        for (const orphaned of validation.orphanedCommandHandlers.slice(0, 5)) {
          report += `- \`${orphaned.handlerName}\` (строка ${orphaned.lineNumber})${orphaned.isExported ? ' [Экспорт]' : ''}\n`;
        }
        if (validation.orphanedCommandHandlers.length > 5) {
          report += `- ... и еще ${validation.orphanedCommandHandlers.length - 5}\n`;
        }
        report += `\n`;
      }
    }

    // Conditional appearance validation
    if (validation.totalConditionalAppearance > 0) {
      report += `## 🎨 Условное оформление (${validation.totalConditionalAppearance})\n\n`;

      if (validation.conditionalAppearanceIssues.length > 0) {
        report += `### ❌ Проблемы условного оформления (${validation.conditionalAppearanceIssues.length})\n\n`;

        const byType = {
          invalid_field: validation.conditionalAppearanceIssues.filter(i => i.issueType === 'invalid_field'),
          invalid_datapath: validation.conditionalAppearanceIssues.filter(i => i.issueType === 'invalid_datapath'),
          missing_condition: validation.conditionalAppearanceIssues.filter(i => i.issueType === 'missing_condition'),
          invalid_condition: validation.conditionalAppearanceIssues.filter(i => i.issueType === 'invalid_condition')
        };

        if (byType.invalid_field.length > 0) {
          report += `**Некорректные поля (${byType.invalid_field.length}):**\n\n`;
          for (const issue of byType.invalid_field.slice(0, 5)) {
            report += `- Элемент ${issue.itemId}: ${issue.description}\n`;
            if (issue.suggestion) {
              report += `  - ${issue.suggestion}\n`;
            }
          }
          report += `\n`;
        }

        if (byType.invalid_datapath.length > 0) {
          report += `**Некорректные DataPath (${byType.invalid_datapath.length}):**\n\n`;
          for (const issue of byType.invalid_datapath.slice(0, 5)) {
            report += `- Элемент ${issue.itemId}: ${issue.description}\n`;
          }
          report += `\n`;
        }

        if (byType.missing_condition.length > 0) {
          report += `**Отсутствующие условия (${byType.missing_condition.length}):**\n\n`;
          for (const issue of byType.missing_condition) {
            report += `- Элемент ${issue.itemId}: ${issue.description}\n`;
          }
          report += `\n`;
        }

        if (byType.invalid_condition.length > 0) {
          report += `**Некорректные условия (${byType.invalid_condition.length}):**\n\n`;
          for (const issue of byType.invalid_condition) {
            report += `- Элемент ${issue.itemId}: ${issue.description}\n`;
          }
          report += `\n`;
        }
      } else {
        report += `✅ Проблем не обнаружено.\n\n`;
      }
    }

    // Best practices
    if (validation.recommendations.length > 0) {
      report += `## 💡 Рекомендации (${validation.recommendations.length})\n\n`;

      const byPriority = {
        high: validation.recommendations.filter(r => r.priority === 'high'),
        medium: validation.recommendations.filter(r => r.priority === 'medium'),
        low: validation.recommendations.filter(r => r.priority === 'low')
      };

      if (byPriority.high.length > 0) {
        report += `### 🔴 Высокий приоритет (${byPriority.high.length})\n\n`;
        for (const rec of byPriority.high) {
          report += `- **${rec.title}** [${rec.category}]\n`;
          report += `  ${rec.description}\n`;
          if (rec.affectedItems && rec.affectedItems.length > 0) {
            report += `  Затронуто: ${rec.affectedItems.join(', ')}\n`;
          }
          report += `\n`;
        }
      }

      if (byPriority.medium.length > 0) {
        report += `### 🟡 Средний приоритет (${byPriority.medium.length})\n\n`;
        for (const rec of byPriority.medium) {
          report += `- **${rec.title}** [${rec.category}]\n`;
          report += `  ${rec.description}\n`;
          report += `\n`;
        }
      }

      if (byPriority.low.length > 0) {
        report += `### 🟢 Низкий приоритет (${byPriority.low.length})\n\n`;
        for (const rec of byPriority.low) {
          report += `- **${rec.title}**: ${rec.description}\n`;
        }
        report += `\n`;
      }
    }

    return report;
  }
}
