/**
 * Form.xml Parser for 1C:Enterprise Forms
 *
 * Parses Form.xml files to extract:
 * - Form structure and hierarchy
 * - Control definitions (input fields, buttons, tables)
 * - Event bindings between controls and BSL handlers
 * - Data paths linking controls to object attributes
 */
import * as fs from 'fs';
import * as path from 'path';
import { parseStringPromise } from 'xml2js';
import { EVENT_NAME_MAP, CONTROL_TYPE_MAP } from './form-types.js';
/**
 * Form Parser - parses 1C Form.xml files
 */
export class FormParser {
    /**
     * Parse Form.xml file
     * @param xmlFilePath Path to Form.xml file
     * @returns Parsed form structure
     */
    async parseFormXML(xmlFilePath) {
        if (!fs.existsSync(xmlFilePath)) {
            throw new Error(`Form.xml file not found: ${xmlFilePath}`);
        }
        // Read and parse XML
        const xmlContent = fs.readFileSync(xmlFilePath, 'utf-8');
        const xmlObj = await parseStringPromise(xmlContent, {
            trim: true,
            explicitArray: true,
            preserveChildrenOrder: true,
            xmlns: true
        });
        // Extract form name from path: .../Forms/FormName/Ext/Form.xml
        const formDir = path.dirname(path.dirname(xmlFilePath));
        const formName = path.basename(formDir);
        // Parse form structure
        const formRoot = xmlObj.Form || xmlObj['Form'];
        if (!formRoot) {
            throw new Error(`Invalid Form.xml: missing <Form> root element`);
        }
        // Extract form-level events
        const formEvents = this.parseFormEvents(formRoot);
        // Extract form attributes
        const attributes = this.parseFormAttributes(formRoot);
        // Extract controls hierarchy
        const controls = [];
        const rootControls = [];
        if (formRoot.ChildItems && formRoot.ChildItems.length > 0) {
            this.parseChildItems(formRoot.ChildItems[0], controls, rootControls, undefined);
        }
        // Collect all events
        const allEvents = [...formEvents];
        for (const control of controls) {
            allEvents.push(...control.events);
        }
        // Extract commands
        const commands = this.parseFormCommands(formRoot);
        // Extract conditional appearance
        const conditionalAppearance = this.parseConditionalAppearance(formRoot);
        return {
            formName,
            xmlFilePath,
            formEvents,
            attributes,
            controls,
            rootControls,
            allEvents,
            commands,
            conditionalAppearance
        };
    }
    /**
     * Parse form-level events from <Events> section
     */
    parseFormEvents(formRoot) {
        const events = [];
        if (!formRoot.Events || formRoot.Events.length === 0) {
            return events;
        }
        const eventsSection = formRoot.Events[0];
        if (!eventsSection.Event) {
            return events;
        }
        for (const eventNode of eventsSection.Event) {
            // xml2js with xmlns:true parses attributes as objects with .value property
            const xmlEventName = eventNode.$.name?.value || eventNode.$.name;
            const handlerName = eventNode._;
            if (xmlEventName && handlerName) {
                const eventType = EVENT_NAME_MAP[xmlEventName] || 'Unknown';
                events.push({
                    xmlEventName,
                    eventType,
                    handlerName
                });
            }
        }
        return events;
    }
    /**
     * Parse form attributes (реквизиты)
     */
    parseFormAttributes(formRoot) {
        const attributes = [];
        // Attributes are typically in <Attributes> section (not always present in all forms)
        if (!formRoot.Attributes || formRoot.Attributes.length === 0) {
            return attributes;
        }
        const attributesSection = formRoot.Attributes[0];
        if (!attributesSection.Attribute) {
            return attributes;
        }
        for (const attrNode of attributesSection.Attribute) {
            const name = attrNode.Name ? attrNode.Name[0] : undefined;
            const typeNode = attrNode.Type ? attrNode.Type[0] : undefined;
            if (name) {
                attributes.push({
                    name,
                    type: this.extractTypeFromNode(typeNode),
                    isTable: false
                });
            }
        }
        return attributes;
    }
    /**
     * Parse child items (controls) recursively
     */
    parseChildItems(childItemsNode, allControls, parentArray, parentName) {
        if (!childItemsNode)
            return;
        // Iterate through all child element types
        for (const key of Object.keys(childItemsNode)) {
            if (key === '$' || key === '_')
                continue;
            const items = childItemsNode[key];
            if (!Array.isArray(items))
                continue;
            for (const item of items) {
                const control = this.parseControl(item, key, parentName);
                if (control) {
                    allControls.push(control);
                    parentArray.push(control);
                    // Recursively parse nested controls
                    if (item.ChildItems && item.ChildItems.length > 0) {
                        control.children = [];
                        this.parseChildItems(item.ChildItems[0], allControls, control.children, control.name);
                    }
                }
            }
        }
    }
    /**
     * Parse individual control element
     */
    parseControl(controlNode, elementType, parentName) {
        // Extract control attributes
        const attrs = controlNode.$ || {};
        // xml2js with xmlns:true parses attributes as objects with .value property
        const id = attrs.id?.value || attrs.id || '';
        const name = attrs.name?.value || attrs.name || '';
        if (!name)
            return null;
        // Determine control type
        const type = CONTROL_TYPE_MAP[elementType] || 'Unknown';
        // Extract data path - DataPath is a text element, not an attribute
        const dataPath = controlNode.DataPath && controlNode.DataPath.length > 0
            ? controlNode.DataPath[0]._ || controlNode.DataPath[0]
            : undefined;
        // Extract title
        const title = this.parseTitle(controlNode);
        // Extract events
        const events = this.parseControlEvents(controlNode);
        // Extract additional properties
        const width = controlNode.Width && controlNode.Width.length > 0
            ? parseInt(controlNode.Width[0], 10)
            : undefined;
        const horizontalStretch = controlNode.HorizontalStretch && controlNode.HorizontalStretch.length > 0
            ? controlNode.HorizontalStretch[0] === 'true'
            : undefined;
        return {
            id,
            name,
            type,
            dataPath,
            title,
            events,
            parent: parentName,
            children: [],
            width,
            horizontalStretch
        };
    }
    /**
     * Parse control events from <Events> section
     */
    parseControlEvents(controlNode) {
        const events = [];
        if (!controlNode.Events || controlNode.Events.length === 0) {
            return events;
        }
        const eventsSection = controlNode.Events[0];
        if (!eventsSection.Event) {
            return events;
        }
        for (const eventNode of eventsSection.Event) {
            // xml2js with xmlns:true parses attributes as objects with .value property
            const xmlEventName = eventNode.$.name?.value || eventNode.$.name;
            const handlerName = eventNode._;
            if (xmlEventName && handlerName) {
                const eventType = EVENT_NAME_MAP[xmlEventName] || 'Unknown';
                events.push({
                    xmlEventName,
                    eventType,
                    handlerName
                });
            }
        }
        return events;
    }
    /**
     * Parse title from <Title> section
     */
    parseTitle(node) {
        if (!node.Title || node.Title.length === 0) {
            return undefined;
        }
        const titleNode = node.Title[0];
        // Handle different title formats
        // Format 1: <Title><v8:item><v8:lang>ru</v8:lang><v8:content>...</v8:content></v8:item></Title>
        if (titleNode['v8:item']) {
            const titles = [];
            for (const item of titleNode['v8:item']) {
                const lang = item['v8:lang'] && item['v8:lang'][0] ? item['v8:lang'][0] : 'ru';
                const content = item['v8:content'] && item['v8:content'][0] ? item['v8:content'][0] : '';
                if (content) {
                    titles.push({ lang, content });
                }
            }
            return titles.length > 0 ? titles : undefined;
        }
        // Format 2: Simple string title
        if (typeof titleNode === 'string') {
            return [{ lang: 'ru', content: titleNode }];
        }
        return undefined;
    }
    /**
     * Extract type string from Type node
     */
    extractTypeFromNode(typeNode) {
        if (!typeNode)
            return undefined;
        // Try to find v8:Type element
        if (typeNode['v8:Type']) {
            return typeNode['v8:Type'][0];
        }
        return undefined;
    }
    /**
     * Generate human-readable summary of form structure
     */
    generateSummary(formStructure) {
        let summary = `### Форма: ${formStructure.formName}\n\n`;
        // Form events
        if (formStructure.formEvents.length > 0) {
            summary += `**События формы (${formStructure.formEvents.length}):**\n`;
            for (const event of formStructure.formEvents) {
                summary += `- \`${event.eventType}\` → \`${event.handlerName}\`\n`;
            }
            summary += `\n`;
        }
        // Controls summary
        summary += `**Элементы управления:** ${formStructure.controls.length} всего\n\n`;
        // Group controls by type
        const controlsByType = new Map();
        for (const control of formStructure.controls) {
            if (!controlsByType.has(control.type)) {
                controlsByType.set(control.type, []);
            }
            controlsByType.get(control.type).push(control);
        }
        summary += `**По типам:**\n`;
        for (const [type, controls] of controlsByType.entries()) {
            summary += `- ${type}: ${controls.length}\n`;
        }
        summary += `\n`;
        // Controls with events
        const controlsWithEvents = formStructure.controls.filter(c => c.events.length > 0);
        if (controlsWithEvents.length > 0) {
            summary += `**Элементы с обработчиками событий (${controlsWithEvents.length}):**\n`;
            for (const control of controlsWithEvents) {
                summary += `- **${control.name}** (${control.type})`;
                if (control.dataPath) {
                    summary += ` → \`${control.dataPath}\``;
                }
                summary += `\n`;
                for (const event of control.events) {
                    summary += `  - \`${event.eventType}\` → \`${event.handlerName}\`\n`;
                }
            }
            summary += `\n`;
        }
        return summary;
    }
    /**
     * Generate LLM context prompt with form structure
     */
    generateContextPrompt(formStructure) {
        let prompt = `\n### Структура формы: ${formStructure.formName}\n\n`;
        // Form-level info
        prompt += `**Общая информация:**\n`;
        prompt += `- Всего элементов управления: ${formStructure.controls.length}\n`;
        prompt += `- Элементов с событиями: ${formStructure.controls.filter(c => c.events.length > 0).length}\n`;
        prompt += `- Всего событий: ${formStructure.allEvents.length}\n`;
        prompt += `\n`;
        // Form events
        if (formStructure.formEvents.length > 0) {
            prompt += `**События формы:**\n`;
            for (const event of formStructure.formEvents) {
                prompt += `- \`${event.handlerName}()\` - событие \`${event.eventType}\`\n`;
            }
            prompt += `\n`;
        }
        // Root-level structure
        if (formStructure.rootControls.length > 0) {
            prompt += `**Структура элементов:**\n`;
            for (const control of formStructure.rootControls) {
                prompt += this.buildControlPrompt(control, 0);
            }
        }
        prompt += `\n**ВАЖНО для документирования:**\n`;
        prompt += `1. Используйте информацию о путях данных (DataPath) для понимания связи с реквизитами\n`;
        prompt += `2. Учитывайте иерархию элементов при описании формы\n`;
        prompt += `3. Опишите назначение каждого обработчика события в контексте элемента управления\n`;
        prompt += `4. Укажите связь между элементами формы и бизнес-логикой в обработчиками\n`;
        return prompt;
    }
    /**
     * Build control information for prompt (recursive)
     */
    buildControlPrompt(control, level) {
        const indent = '  '.repeat(level);
        let result = '';
        result += `${indent}- **${control.name}** (${control.type})`;
        if (control.dataPath) {
            result += ` → \`${control.dataPath}\``;
        }
        result += `\n`;
        // Events
        if (control.events.length > 0) {
            for (const event of control.events) {
                result += `${indent}  - Событие: \`${event.eventType}\` → \`${event.handlerName}\`\n`;
            }
        }
        // Children
        if (control.children && control.children.length > 0) {
            for (const child of control.children) {
                result += this.buildControlPrompt(child, level + 1);
            }
        }
        return result;
    }
    /**
     * Parse form commands from <Commands> section
     */
    parseFormCommands(formRoot) {
        const commands = [];
        if (!formRoot.Commands || formRoot.Commands.length === 0) {
            return commands;
        }
        const commandsSection = formRoot.Commands[0];
        if (!commandsSection.Command) {
            return commands;
        }
        for (const commandNode of commandsSection.Command) {
            const attrs = commandNode.$ || {};
            const name = attrs.name?.value || attrs.name;
            const id = attrs.id?.value || attrs.id;
            if (!name)
                continue;
            // Extract Action (handler procedure name)
            const action = commandNode.Action && commandNode.Action.length > 0
                ? commandNode.Action[0]._ || commandNode.Action[0]
                : undefined;
            // Extract Title
            const title = this.parseTitle(commandNode);
            // Extract ToolTip
            const toolTip = this.parseToolTip(commandNode);
            // Extract Shortcut
            const shortcut = commandNode.Shortcut && commandNode.Shortcut.length > 0
                ? commandNode.Shortcut[0]
                : undefined;
            // Extract Picture
            const picture = commandNode.Picture && commandNode.Picture.length > 0
                ? commandNode.Picture[0]
                : undefined;
            // Extract Representation
            const representation = commandNode.Representation && commandNode.Representation.length > 0
                ? commandNode.Representation[0]
                : undefined;
            commands.push({
                name,
                id,
                title,
                toolTip,
                action,
                shortcut,
                picture,
                representation
            });
        }
        return commands;
    }
    /**
     * Parse ToolTip from <ToolTip> section (similar to Title)
     */
    parseToolTip(node) {
        if (!node.ToolTip || node.ToolTip.length === 0) {
            return undefined;
        }
        const toolTipNode = node.ToolTip[0];
        // Format 1: <ToolTip><v8:item><v8:lang>ru</v8:lang><v8:content>...</v8:content></v8:item></ToolTip>
        if (toolTipNode['v8:item']) {
            const toolTips = [];
            for (const item of toolTipNode['v8:item']) {
                const lang = item['v8:lang'] && item['v8:lang'][0] ? item['v8:lang'][0] : 'ru';
                const content = item['v8:content'] && item['v8:content'][0] ? item['v8:content'][0] : '';
                if (content) {
                    toolTips.push({ lang, content });
                }
            }
            return toolTips.length > 0 ? toolTips : undefined;
        }
        // Format 2: Simple string tooltip
        if (typeof toolTipNode === 'string') {
            return [{ lang: 'ru', content: toolTipNode }];
        }
        return undefined;
    }
    /**
     * Parse conditional appearance from <ConditionalAppearance> section
     */
    parseConditionalAppearance(formRoot) {
        const items = [];
        if (!formRoot.ConditionalAppearance || formRoot.ConditionalAppearance.length === 0) {
            return items;
        }
        const caSection = formRoot.ConditionalAppearance[0];
        if (!caSection.Item) {
            return items;
        }
        for (const itemNode of caSection.Item) {
            const attrs = itemNode.$ || {};
            const id = attrs.id?.value || attrs.id;
            if (!id)
                continue;
            // Extract event name (if any)
            const eventName = itemNode.EventName && itemNode.EventName.length > 0
                ? itemNode.EventName[0]
                : undefined;
            // Extract fields (target controls)
            const fields = [];
            if (itemNode.Fields && itemNode.Fields.length > 0) {
                const fieldsSection = itemNode.Fields[0];
                if (fieldsSection.Field) {
                    for (const fieldNode of fieldsSection.Field) {
                        const fieldName = fieldNode._ || fieldNode;
                        if (fieldName) {
                            fields.push(fieldName);
                        }
                    }
                }
            }
            // Extract appearance properties
            const appearance = this.parseAppearanceProperties(itemNode);
            // Extract conditions
            const conditions = this.parseAppearanceConditions(itemNode);
            items.push({
                id,
                eventName,
                fields,
                appearance,
                conditions
            });
        }
        return items;
    }
    /**
     * Parse appearance properties (Appearance section)
     */
    parseAppearanceProperties(itemNode) {
        const props = {};
        if (!itemNode.Appearance || itemNode.Appearance.length === 0) {
            return props;
        }
        const appearanceSection = itemNode.Appearance[0];
        // Extract common appearance properties
        if (appearanceSection.TextColor && appearanceSection.TextColor.length > 0) {
            props.textColor = appearanceSection.TextColor[0];
        }
        if (appearanceSection.BackColor && appearanceSection.BackColor.length > 0) {
            props.backColor = appearanceSection.BackColor[0];
        }
        if (appearanceSection.Font && appearanceSection.Font.length > 0) {
            props.font = appearanceSection.Font[0];
        }
        if (appearanceSection.Enabled && appearanceSection.Enabled.length > 0) {
            props.enabled = appearanceSection.Enabled[0] === 'true';
        }
        if (appearanceSection.Visible && appearanceSection.Visible.length > 0) {
            props.visible = appearanceSection.Visible[0] === 'true';
        }
        if (appearanceSection.ReadOnly && appearanceSection.ReadOnly.length > 0) {
            props.readOnly = appearanceSection.ReadOnly[0] === 'true';
        }
        return props;
    }
    /**
     * Parse appearance conditions (Filter section)
     */
    parseAppearanceConditions(itemNode) {
        const conditions = [];
        if (!itemNode.Filter || itemNode.Filter.length === 0) {
            return conditions;
        }
        const filterSection = itemNode.Filter[0];
        if (!filterSection.Item) {
            return conditions;
        }
        for (const conditionNode of filterSection.Item) {
            const left = conditionNode.LeftValue && conditionNode.LeftValue.length > 0
                ? conditionNode.LeftValue[0]
                : undefined;
            const comparisonType = conditionNode.ComparisonType && conditionNode.ComparisonType.length > 0
                ? conditionNode.ComparisonType[0]
                : undefined;
            const right = conditionNode.RightValue && conditionNode.RightValue.length > 0
                ? conditionNode.RightValue[0]
                : undefined;
            if (left && comparisonType) {
                conditions.push({
                    left,
                    comparisonType,
                    right
                });
            }
        }
        return conditions;
    }
}
//# sourceMappingURL=form-parser.js.map