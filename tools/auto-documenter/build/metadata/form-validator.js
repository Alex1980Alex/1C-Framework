/**
 * Form Validation - validates consistency between Form.xml and Module.bsl
 *
 * Combines FormParser and EventHandlerDetector to:
 * - Find missing handlers (referenced in Form.xml but not in Module.bsl)
 * - Find orphaned handlers (exist in Module.bsl but not referenced in Form.xml)
 * - Calculate coverage metrics
 * - Generate validation reports
 */
import * as fs from 'fs';
import * as path from 'path';
import { FormParser } from './form-parser.js';
import { EventHandlerDetector } from './event-handler-detector.js';
/**
 * Form Validator - cross-references Form.xml with Module.bsl
 */
export class FormValidator {
    constructor() {
        this.formParser = new FormParser();
        this.handlerDetector = new EventHandlerDetector();
    }
    /**
     * Validate form by analyzing both Form.xml and Module.bsl
     * @param formXmlPath Path to Form.xml file
     * @param moduleBslPath Path to Module.bsl file (optional, auto-detected if not provided)
     * @returns Validation result with coverage metrics and inconsistencies
     */
    async validateForm(formXmlPath, moduleBslPath) {
        // Parse Form.xml
        const formStructure = await this.formParser.parseFormXML(formXmlPath);
        // Auto-detect Module.bsl path if not provided
        if (!moduleBslPath) {
            // Form.xml is at: .../Forms/FormName/Ext/Form.xml
            // Module.bsl is at: .../Forms/FormName/Ext/Form/Module.bsl
            const formDir = path.dirname(formXmlPath);
            moduleBslPath = path.join(formDir, 'Form', 'Module.bsl');
        }
        // Check if Module.bsl exists
        if (!fs.existsSync(moduleBslPath)) {
            throw new Error(`Module.bsl file not found: ${moduleBslPath}`);
        }
        // Analyze Module.bsl
        const handlerAnalysis = await this.handlerDetector.analyzeFormModule(moduleBslPath);
        // Perform validation
        return this.performValidation(formStructure, handlerAnalysis);
    }
    /**
     * Perform cross-validation between Form.xml and Module.bsl
     */
    performValidation(formStructure, handlerAnalysis) {
        const errors = [];
        const warnings = [];
        // Build handler lookup map (handler name → IEventHandler)
        const handlersMap = new Map();
        for (const handler of [
            ...handlerAnalysis.handlersByType.formEvents,
            ...handlerAnalysis.handlersByType.controlEvents,
            ...handlerAnalysis.handlersByType.notificationHandlers,
            ...handlerAnalysis.handlersByType.commandHandlers
        ]) {
            handlersMap.set(handler.name, handler);
        }
        // Find missing handlers (referenced in Form.xml but not in Module.bsl)
        const missingHandlers = [];
        for (const event of formStructure.allEvents) {
            const handlerExists = handlersMap.has(event.handlerName);
            event.handlerExists = handlerExists;
            if (!handlerExists) {
                // Determine which control references this handler
                let controlName = 'Form';
                let controlType = 'Form';
                let dataPath;
                // Check if it's a control event
                for (const control of formStructure.controls) {
                    if (control.events.some(e => e.handlerName === event.handlerName)) {
                        controlName = control.name;
                        controlType = control.type;
                        dataPath = control.dataPath;
                        break;
                    }
                }
                missingHandlers.push({
                    controlName,
                    controlType,
                    eventType: event.eventType,
                    handlerName: event.handlerName,
                    dataPath
                });
                errors.push(`Missing handler: ${event.handlerName}() referenced by ${controlName} (${event.eventType})`);
            }
        }
        // Build set of referenced handler names
        const referencedHandlers = new Set();
        for (const event of formStructure.allEvents) {
            referencedHandlers.add(event.handlerName);
        }
        // Find orphaned handlers (exist in Module.bsl but not referenced in Form.xml)
        const orphanedHandlers = [];
        for (const handler of [
            ...handlerAnalysis.handlersByType.formEvents,
            ...handlerAnalysis.handlersByType.controlEvents,
            ...handlerAnalysis.handlersByType.notificationHandlers
        ]) {
            if (!referencedHandlers.has(handler.name)) {
                orphanedHandlers.push({
                    handlerName: handler.name,
                    handlerType: handler.type,
                    guessedControlName: handler.controlName,
                    guessedEventType: handler.eventType,
                    lineNumber: handler.lineNumber,
                    isExported: handler.isExported
                });
                warnings.push(`Orphaned handler: ${handler.name}() at line ${handler.lineNumber} not referenced in Form.xml`);
            }
        }
        // Find unused controls (controls with no events)
        const unusedControls = [];
        for (const control of formStructure.controls) {
            if (control.events.length === 0 && control.type !== 'UsualGroup' && control.type !== 'Label') {
                unusedControls.push(control);
            }
        }
        // Calculate coverage metrics
        const totalControls = formStructure.controls.filter(c => c.type !== 'UsualGroup' && c.type !== 'Label' && c.type !== 'LabelDecoration').length;
        const controlsWithHandlers = formStructure.controls.filter(c => c.events.length > 0).length;
        const totalEvents = formStructure.allEvents.length;
        const eventsWithHandlers = formStructure.allEvents.filter(e => e.handlerExists).length;
        const controlCoverage = totalControls > 0 ? (controlsWithHandlers / totalControls) * 100 : 0;
        const eventCoverage = totalEvents > 0 ? (eventsWithHandlers / totalEvents) * 100 : 0;
        // Determine overall validation status
        const isValid = errors.length === 0;
        return {
            formStructure,
            totalControls,
            controlsWithHandlers,
            totalEvents,
            eventsWithHandlers,
            missingHandlers,
            orphanedHandlers,
            unusedControls,
            coverage: {
                controlCoverage,
                eventCoverage
            },
            isValid,
            errors,
            warnings
        };
    }
    /**
     * Generate human-readable validation report
     */
    generateValidationReport(validation) {
        let report = `# Form Validation Report: ${validation.formStructure.formName}\n\n`;
        // Overall status
        report += `## Статус валидации: ${validation.isValid ? '✅ PASSED' : '❌ FAILED'}\n\n`;
        // Summary statistics
        report += `## Общая статистика\n\n`;
        report += `- **Элементов управления:** ${validation.totalControls} всего\n`;
        report += `- **Элементов с обработчиками:** ${validation.controlsWithHandlers} (${validation.coverage.controlCoverage.toFixed(1)}%)\n`;
        report += `- **Событий:** ${validation.totalEvents} всего\n`;
        report += `- **Событий с обработчиками:** ${validation.eventsWithHandlers} (${validation.coverage.eventCoverage.toFixed(1)}%)\n`;
        report += `\n`;
        // Coverage metrics
        report += `## Покрытие обработчиками\n\n`;
        report += `- **Покрытие элементов:** ${validation.coverage.controlCoverage.toFixed(1)}% (${validation.controlsWithHandlers}/${validation.totalControls})\n`;
        report += `- **Покрытие событий:** ${validation.coverage.eventCoverage.toFixed(1)}% (${validation.eventsWithHandlers}/${validation.totalEvents})\n`;
        report += `\n`;
        // Errors section
        if (validation.errors.length > 0) {
            report += `## ❌ Ошибки (${validation.errors.length})\n\n`;
            report += `### Отсутствующие обработчики\n\n`;
            report += `Следующие обработчики указаны в Form.xml, но не найдены в Module.bsl:\n\n`;
            for (const missing of validation.missingHandlers) {
                report += `- **\`${missing.handlerName}()\`**\n`;
                report += `  - Элемент: \`${missing.controlName}\` (${missing.controlType})\n`;
                report += `  - Событие: \`${missing.eventType}\`\n`;
                if (missing.dataPath) {
                    report += `  - DataPath: \`${missing.dataPath}\`\n`;
                }
                report += `\n`;
            }
        }
        // Warnings section
        if (validation.warnings.length > 0) {
            report += `## ⚠️ Предупреждения (${validation.warnings.length})\n\n`;
            if (validation.orphanedHandlers.length > 0) {
                report += `### Неиспользуемые обработчики\n\n`;
                report += `Следующие обработчики существуют в Module.bsl, но не указаны в Form.xml:\n\n`;
                for (const orphaned of validation.orphanedHandlers) {
                    report += `- **\`${orphaned.handlerName}()\`** (строка ${orphaned.lineNumber})\n`;
                    report += `  - Тип: ${orphaned.handlerType}\n`;
                    if (orphaned.guessedControlName) {
                        report += `  - Предполагаемый элемент: \`${orphaned.guessedControlName}\`\n`;
                    }
                    if (orphaned.guessedEventType) {
                        report += `  - Предполагаемое событие: \`${orphaned.guessedEventType}\`\n`;
                    }
                    report += `  - Экспортируется: ${orphaned.isExported ? 'Да' : 'Нет'}\n`;
                    report += `\n`;
                }
            }
            if (validation.unusedControls.length > 0) {
                report += `### Элементы без обработчиков\n\n`;
                report += `Следующие элементы управления не имеют обработчиков событий:\n\n`;
                for (const control of validation.unusedControls) {
                    report += `- **\`${control.name}\`** (${control.type})`;
                    if (control.dataPath) {
                        report += ` → \`${control.dataPath}\``;
                    }
                    report += `\n`;
                }
                report += `\n`;
            }
        }
        // Success message
        if (validation.isValid && validation.warnings.length === 0) {
            report += `## ✅ Все проверки пройдены!\n\n`;
            report += `Форма полностью согласована с модулем. Все обработчики событий определены.\n`;
        }
        return report;
    }
    /**
     * Generate LLM context with validation information
     */
    generateValidationContext(validation) {
        let context = `\n### Валидация формы: ${validation.formStructure.formName}\n\n`;
        context += `**Статус:** ${validation.isValid ? '✅ Валидна' : '❌ Есть ошибки'}\n\n`;
        // Coverage
        context += `**Покрытие обработчиками:**\n`;
        context += `- Элементы: ${validation.coverage.controlCoverage.toFixed(1)}% (${validation.controlsWithHandlers}/${validation.totalControls})\n`;
        context += `- События: ${validation.coverage.eventCoverage.toFixed(1)}% (${validation.eventsWithHandlers}/${validation.totalEvents})\n\n`;
        // Issues
        if (validation.missingHandlers.length > 0) {
            context += `**⚠️ Отсутствующие обработчики (${validation.missingHandlers.length}):**\n`;
            for (const missing of validation.missingHandlers.slice(0, 5)) {
                context += `- \`${missing.handlerName}()\` для \`${missing.controlName}\` (${missing.eventType})\n`;
            }
            if (validation.missingHandlers.length > 5) {
                context += `- ... и еще ${validation.missingHandlers.length - 5}\n`;
            }
            context += `\n`;
        }
        if (validation.orphanedHandlers.length > 0) {
            context += `**ℹ️ Неиспользуемые обработчики (${validation.orphanedHandlers.length}):**\n`;
            for (const orphaned of validation.orphanedHandlers.slice(0, 5)) {
                context += `- \`${orphaned.handlerName}()\` (строка ${orphaned.lineNumber})\n`;
            }
            if (validation.orphanedHandlers.length > 5) {
                context += `- ... и еще ${validation.orphanedHandlers.length - 5}\n`;
            }
            context += `\n`;
        }
        context += `**ВАЖНО при документировании:** Учитывайте результаты валидации для более точного описания формы.\n`;
        return context;
    }
}
//# sourceMappingURL=form-validator.js.map