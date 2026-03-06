/**
 * Event Handler Detection for 1C:Enterprise Forms
 *
 * Analyzes form module BSL code to detect and categorize event handlers.
 * Event handlers are procedures that respond to form and control events.
 */
import * as fs from 'fs';
/**
 * Known 1C form event names
 */
const FORM_EVENTS = new Set([
    // Creation and opening
    'ПриСозданииНаСервере',
    'ПриОткрытии',
    'ПриСозданииНаКлиенте',
    'ПриЧтенииНаСервере',
    // Closing
    'ПриЗакрытии',
    'ПередЗакрытием',
    // Writing and validation
    'ПередЗаписью',
    'ПередЗаписьюНаСервере',
    'ПослеЗаписи',
    'ПослеЗаписиНаСервере',
    'ПриЗаписи',
    // Notifications
    'ОбработкаОповещения',
    'ОбработкаВыбора',
    // Other form events
    'ПриПовторномОткрытии',
    'ПриИзмененииВидимости',
    'ПриАктивизации'
]);
/**
 * Known control event suffixes
 */
const CONTROL_EVENT_SUFFIXES = [
    'ПриИзменении',
    'НачалоВыбора',
    'Нажатие',
    'ИзменениеТекстаРедактирования',
    'АвтоПодбор',
    'ОбработкаВыбора',
    'ОкончаниеВводаТекста',
    'ПриАктивизацииСтроки',
    'ПриВыводеСтроки',
    'ПриПолученииДанныхНаСервере',
    'ПередНачаломДобавления',
    'ПередУдалением',
    'ПередОкончаниемРедактирования',
    'ПриНачалеРедактирования',
    'ПриОкончанииРедактирования',
    'Выбор',
    'ПередРазворачиванием',
    'ПередСворачиванием'
];
/**
 * Event Handler Detector
 */
export class EventHandlerDetector {
    /**
     * Analyze form module BSL file for event handlers
     * @param bslFilePath Path to form Module.bsl file
     * @returns Event handler analysis result
     */
    async analyzeFormModule(bslFilePath) {
        if (!fs.existsSync(bslFilePath)) {
            throw new Error(`Form module file not found: ${bslFilePath}`);
        }
        const content = fs.readFileSync(bslFilePath, 'utf-8');
        const lines = content.split('\n');
        const handlers = [];
        // Parse line by line to find procedures
        let currentContext = 'Unknown';
        let currentComment = [];
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            const lineNumber = i + 1;
            // Track compilation directives
            if (line.startsWith('&НаСервере')) {
                currentContext = 'Server';
                continue;
            }
            else if (line.startsWith('&НаКлиенте')) {
                currentContext = 'Client';
                continue;
            }
            else if (line.startsWith('&НаСервереБезКонтекста')) {
                currentContext = 'ServerNoContext';
                continue;
            }
            // Collect comments
            if (line.startsWith('//')) {
                currentComment.push(line.substring(2).trim());
                continue;
            }
            // Check for procedure declaration
            // Note: Use Cyrillic Unicode range [\u0400-\u04FF] instead of \w for procedure names
            const procedureMatch = line.match(/^Процедура\s+([\u0400-\u04FF_a-zA-Z0-9]+)\s*\((.*?)\)(?:\s+Экспорт)?/i);
            if (procedureMatch) {
                const procedureName = procedureMatch[1];
                const paramsStr = procedureMatch[2];
                const isExported = line.includes('Экспорт');
                // Parse parameters
                const parameters = paramsStr
                    .split(',')
                    .map(p => p.trim())
                    .filter(p => p.length > 0);
                // Detect handler type
                const handler = this.detectHandlerType(procedureName, parameters, currentContext, isExported, lineNumber, currentComment.length > 0 ? currentComment.join('\n') : undefined);
                handlers.push(handler);
                // Reset state
                currentContext = 'Unknown';
                currentComment = [];
            }
        }
        // Categorize handlers
        return this.categorizeHandlers(handlers);
    }
    /**
     * Detect handler type and extract metadata
     */
    detectHandlerType(name, parameters, context, isExported, lineNumber, comment) {
        const baseHandler = {
            name,
            type: 'Unknown',
            context,
            parameters,
            isExported,
            lineNumber,
            comment
        };
        // Check if it's a form event
        if (FORM_EVENTS.has(name)) {
            return {
                ...baseHandler,
                type: name === 'ОбработкаОповещения' ? 'NotificationHandler' : 'FormEvent'
            };
        }
        // Check if it's a command handler
        if (name.startsWith('Подключаемый_')) {
            return {
                ...baseHandler,
                type: 'CommandHandler'
            };
        }
        // Check if it's a control event handler
        for (const suffix of CONTROL_EVENT_SUFFIXES) {
            if (name.endsWith(suffix)) {
                const controlName = name.substring(0, name.length - suffix.length);
                return {
                    ...baseHandler,
                    type: 'ControlEvent',
                    controlName,
                    eventType: suffix
                };
            }
        }
        // Unknown type (likely a utility procedure)
        return baseHandler;
    }
    /**
     * Categorize handlers by type and context
     */
    categorizeHandlers(handlers) {
        const result = {
            totalHandlers: handlers.length,
            handlersByType: {
                formEvents: [],
                controlEvents: [],
                commandHandlers: [],
                notificationHandlers: [],
                unknown: []
            },
            handlersByContext: {
                server: [],
                client: [],
                serverNoContext: [],
                unknown: []
            }
        };
        for (const handler of handlers) {
            // Categorize by type
            switch (handler.type) {
                case 'FormEvent':
                    result.handlersByType.formEvents.push(handler);
                    break;
                case 'ControlEvent':
                    result.handlersByType.controlEvents.push(handler);
                    break;
                case 'CommandHandler':
                    result.handlersByType.commandHandlers.push(handler);
                    break;
                case 'NotificationHandler':
                    result.handlersByType.notificationHandlers.push(handler);
                    break;
                default:
                    result.handlersByType.unknown.push(handler);
            }
            // Categorize by context
            switch (handler.context) {
                case 'Server':
                    result.handlersByContext.server.push(handler);
                    break;
                case 'Client':
                    result.handlersByContext.client.push(handler);
                    break;
                case 'ServerNoContext':
                    result.handlersByContext.serverNoContext.push(handler);
                    break;
                default:
                    result.handlersByContext.unknown.push(handler);
            }
        }
        return result;
    }
    /**
     * Generate human-readable summary of event handlers
     */
    generateSummary(analysis) {
        let summary = `### Event Handlers (${analysis.totalHandlers} total)\n\n`;
        // Summary by type
        summary += `#### By Type\n`;
        summary += `- Form Events: ${analysis.handlersByType.formEvents.length}\n`;
        summary += `- Control Events: ${analysis.handlersByType.controlEvents.length}\n`;
        summary += `- Command Handlers: ${analysis.handlersByType.commandHandlers.length}\n`;
        summary += `- Notification Handlers: ${analysis.handlersByType.notificationHandlers.length}\n`;
        if (analysis.handlersByType.unknown.length > 0) {
            summary += `- Other Procedures: ${analysis.handlersByType.unknown.length}\n`;
        }
        summary += `\n`;
        // Summary by context
        summary += `#### By Execution Context\n`;
        summary += `- Server: ${analysis.handlersByContext.server.length}\n`;
        summary += `- Client: ${analysis.handlersByContext.client.length}\n`;
        summary += `- Server (No Context): ${analysis.handlersByContext.serverNoContext.length}\n`;
        if (analysis.handlersByContext.unknown.length > 0) {
            summary += `- Unknown Context: ${analysis.handlersByContext.unknown.length}\n`;
        }
        summary += `\n`;
        // List form events
        if (analysis.handlersByType.formEvents.length > 0) {
            summary += `#### Form Events\n`;
            for (const handler of analysis.handlersByType.formEvents) {
                summary += `- \`${handler.name}\` (${handler.context}) - Line ${handler.lineNumber}\n`;
            }
            summary += `\n`;
        }
        // List control events (grouped by control)
        if (analysis.handlersByType.controlEvents.length > 0) {
            summary += `#### Control Events\n`;
            // Group by control name
            const byControl = new Map();
            for (const handler of analysis.handlersByType.controlEvents) {
                const controlName = handler.controlName || 'Unknown';
                if (!byControl.has(controlName)) {
                    byControl.set(controlName, []);
                }
                byControl.get(controlName).push(handler);
            }
            // Output grouped
            for (const [controlName, handlers] of byControl.entries()) {
                summary += `- **${controlName}**:\n`;
                for (const handler of handlers) {
                    summary += `  - \`${handler.eventType}\` (${handler.context}) - Line ${handler.lineNumber}\n`;
                }
            }
            summary += `\n`;
        }
        // List command handlers
        if (analysis.handlersByType.commandHandlers.length > 0) {
            summary += `#### Command Handlers\n`;
            for (const handler of analysis.handlersByType.commandHandlers) {
                const commandName = handler.name.replace('Подключаемый_', '');
                summary += `- \`${commandName}\` (${handler.context}) - Line ${handler.lineNumber}\n`;
            }
            summary += `\n`;
        }
        return summary;
    }
    /**
     * Generate context prompt for LLM with event handler information
     */
    generateContextPrompt(analysis, formName) {
        let prompt = `\n### Event Handlers\n\n`;
        if (formName) {
            prompt += `Форма **${formName}** содержит ${analysis.totalHandlers} обработчиков событий:\n\n`;
        }
        // Form events
        if (analysis.handlersByType.formEvents.length > 0) {
            prompt += `**События формы:**\n`;
            for (const handler of analysis.handlersByType.formEvents) {
                prompt += `- \`${handler.name}(${handler.parameters.join(', ')})\` - выполняется на ${this.contextToRussian(handler.context)}\n`;
            }
            prompt += `\n`;
        }
        // Control events with grouping
        if (analysis.handlersByType.controlEvents.length > 0) {
            prompt += `**События элементов управления:**\n`;
            const byControl = new Map();
            for (const handler of analysis.handlersByType.controlEvents) {
                const controlName = handler.controlName || 'Unknown';
                if (!byControl.has(controlName)) {
                    byControl.set(controlName, []);
                }
                byControl.get(controlName).push(handler);
            }
            for (const [controlName, handlers] of byControl.entries()) {
                prompt += `- Элемент **${controlName}**:\n`;
                for (const handler of handlers) {
                    prompt += `  - \`${handler.eventType}\` (${this.contextToRussian(handler.context)})\n`;
                }
            }
            prompt += `\n`;
        }
        // Command handlers
        if (analysis.handlersByType.commandHandlers.length > 0) {
            prompt += `**Обработчики команд:**\n`;
            for (const handler of analysis.handlersByType.commandHandlers) {
                const commandName = handler.name.replace('Подключаемый_', '');
                prompt += `- \`${commandName}\` (${this.contextToRussian(handler.context)})\n`;
            }
            prompt += `\n`;
        }
        prompt += `\n**ВАЖНО для документирования:** Опишите назначение каждого обработчика событий и его взаимодействие с другими элементами формы.\n`;
        return prompt;
    }
    /**
     * Convert context to Russian description
     */
    contextToRussian(context) {
        switch (context) {
            case 'Server': return 'сервере';
            case 'Client': return 'клиенте';
            case 'ServerNoContext': return 'сервере без контекста';
            default: return 'неизвестно';
        }
    }
}
//# sourceMappingURL=event-handler-detector.js.map