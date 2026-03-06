/**
 * 1C:Enterprise Metadata XML Parser
 *
 * Parses XML metadata files from 1C:Enterprise configurations
 * and converts them to TypeScript interfaces for documentation generation.
 */
import * as fs from 'fs';
import * as path from 'path';
import { parseStringPromise } from 'xml2js';
/**
 * Main metadata parser class
 */
export class MetadataParser {
    /**
     * Parse metadata XML file
     * @param xmlFilePath Path to metadata XML file (e.g., Catalogs/Валюты.xml)
     * @returns Parsed metadata analysis result
     */
    async parseMetadataFile(xmlFilePath) {
        if (!fs.existsSync(xmlFilePath)) {
            throw new Error(`Metadata file not found: ${xmlFilePath}`);
        }
        const xmlContent = fs.readFileSync(xmlFilePath, 'utf-8');
        const parsedXml = await parseStringPromise(xmlContent);
        // Determine metadata object type from XML root element
        const metadataRoot = parsedXml.MetaDataObject;
        if (!metadataRoot) {
            throw new Error(`Invalid metadata XML structure: ${xmlFilePath}`);
        }
        // Detect object type
        let objectType;
        let metadata;
        if (metadataRoot.Catalog) {
            objectType = 'Catalog';
            metadata = await this.parseCatalog(metadataRoot.Catalog[0], xmlFilePath);
        }
        else if (metadataRoot.Document) {
            objectType = 'Document';
            metadata = await this.parseDocument(metadataRoot.Document[0], xmlFilePath);
        }
        else if (metadataRoot.DataProcessor) {
            objectType = 'DataProcessor';
            metadata = await this.parseDataProcessor(metadataRoot.DataProcessor[0], xmlFilePath);
        }
        else if (metadataRoot.CommonModule) {
            objectType = 'CommonModule';
            metadata = await this.parseCommonModule(metadataRoot.CommonModule[0], xmlFilePath);
        }
        else if (metadataRoot.Form) {
            objectType = 'Form';
            metadata = await this.parseForm(metadataRoot.Form[0], xmlFilePath);
        }
        else if (metadataRoot.Command) {
            objectType = 'Command';
            metadata = await this.parseCommand(metadataRoot.Command[0], xmlFilePath);
        }
        else if (metadataRoot.Template) {
            objectType = 'Template';
            metadata = await this.parseTemplate(metadataRoot.Template[0], xmlFilePath);
        }
        else {
            // Try to detect from file path structure
            const detectedType = this.detectTypeFromPath(xmlFilePath);
            if (detectedType) {
                objectType = detectedType.type;
                metadata = await this.parseGenericMetadata(detectedType.xmlNode || metadataRoot, xmlFilePath, objectType);
            }
            else {
                throw new Error(`Unsupported metadata type in: ${xmlFilePath}`);
            }
        }
        // Find related BSL files
        const relatedFiles = await this.findRelatedFiles(xmlFilePath, objectType);
        return {
            objectType,
            metadata,
            relatedFiles
        };
    }
    /**
     * Detect metadata type from file path structure
     */
    detectTypeFromPath(xmlFilePath) {
        const normalizedPath = xmlFilePath.replace(/\\/g, '/').toLowerCase();
        if (normalizedPath.includes('/forms/') || normalizedPath.includes('/формы/')) {
            return { type: 'Form' };
        }
        if (normalizedPath.includes('/commands/') || normalizedPath.includes('/команды/')) {
            return { type: 'Command' };
        }
        if (normalizedPath.includes('/templates/') || normalizedPath.includes('/макеты/')) {
            return { type: 'Template' };
        }
        return null;
    }
    /**
     * Parse generic metadata when specific type parsing is not available
     */
    async parseGenericMetadata(xmlNode, xmlFilePath, objectType) {
        // Try to find properties in various possible structures
        const properties = xmlNode.Properties?.[0] || xmlNode;
        const name = this.extractName(properties, xmlFilePath);
        const baseMetadata = {
            uuid: xmlNode.$?.uuid || '',
            name: name,
            synonym: this.parseMultiLanguageString(properties.Synonym),
            comment: properties.Comment?.[0] || ''
        };
        switch (objectType) {
            case 'Form':
                return {
                    ...baseMetadata,
                    type: 'Form',
                    formType: (properties.FormType?.[0] || 'Managed'),
                    usePurposes: this.parseUsePurposes(properties.UsePurposes),
                    includeHelpInContents: properties.IncludeHelpInContents?.[0] === 'true',
                    extendedPresentation: properties.ExtendedPresentation?.[0]
                };
            case 'Command':
                return {
                    ...baseMetadata,
                    type: 'Command',
                    group: properties.Group?.[0],
                    commandParameterType: properties.CommandParameterType?.[0],
                    modifiesData: properties.ModifiesData?.[0] === 'true',
                    representation: properties.Representation?.[0]
                };
            case 'Template':
                return {
                    ...baseMetadata,
                    type: 'Template',
                    templateType: properties.TemplateType?.[0]
                };
        }
    }
    /**
     * Extract name from properties or file path
     */
    extractName(properties, xmlFilePath) {
        if (properties.Name?.[0]) {
            return properties.Name[0];
        }
        // Fallback: extract from file path
        const baseName = path.basename(xmlFilePath, '.xml');
        return baseName;
    }
    /**
     * Parse Form metadata
     */
    async parseForm(formXml, xmlFilePath) {
        const properties = formXml.Properties?.[0] || {};
        return {
            type: 'Form',
            uuid: formXml.$?.uuid || '',
            name: properties.Name?.[0] || path.basename(xmlFilePath, '.xml'),
            synonym: this.parseMultiLanguageString(properties.Synonym),
            comment: properties.Comment?.[0] || '',
            formType: (properties.FormType?.[0] || 'Managed'),
            usePurposes: this.parseUsePurposes(properties.UsePurposes),
            includeHelpInContents: properties.IncludeHelpInContents?.[0] === 'true',
            extendedPresentation: properties.ExtendedPresentation?.[0],
            formModule: undefined // Will be filled by findRelatedFiles
        };
    }
    /**
     * Parse Command metadata
     */
    async parseCommand(commandXml, xmlFilePath) {
        const properties = commandXml.Properties?.[0] || {};
        return {
            type: 'Command',
            uuid: commandXml.$?.uuid || '',
            name: properties.Name?.[0] || path.basename(xmlFilePath, '.xml'),
            synonym: this.parseMultiLanguageString(properties.Synonym),
            comment: properties.Comment?.[0] || '',
            group: properties.Group?.[0],
            commandParameterType: properties.CommandParameterType?.[0],
            modifiesData: properties.ModifiesData?.[0] === 'true',
            representation: properties.Representation?.[0],
            commandModule: undefined // Will be filled by findRelatedFiles
        };
    }
    /**
     * Parse Template metadata
     */
    async parseTemplate(templateXml, xmlFilePath) {
        const properties = templateXml.Properties?.[0] || {};
        return {
            type: 'Template',
            uuid: templateXml.$?.uuid || '',
            name: properties.Name?.[0] || path.basename(xmlFilePath, '.xml'),
            synonym: this.parseMultiLanguageString(properties.Synonym),
            comment: properties.Comment?.[0] || '',
            templateType: properties.TemplateType?.[0]
        };
    }
    /**
     * Parse UsePurposes array
     */
    parseUsePurposes(usePurposesXml) {
        if (!usePurposesXml)
            return [];
        // Handle both array and nested xr:EnumValue structures
        if (Array.isArray(usePurposesXml)) {
            return usePurposesXml.map((up) => {
                if (typeof up === 'string')
                    return up;
                if (up['xr:EnumValue'])
                    return up['xr:EnumValue'][0];
                return String(up);
            }).filter(Boolean);
        }
        const enumValues = usePurposesXml['xr:EnumValue'];
        if (enumValues) {
            return enumValues.map((ev) => typeof ev === 'string' ? ev : String(ev));
        }
        return [];
    }
    /**
     * Parse Catalog metadata
     */
    async parseCatalog(catalogXml, xmlFilePath) {
        const properties = catalogXml.Properties?.[0] || {};
        return {
            type: 'Catalog',
            uuid: catalogXml.$?.uuid || '',
            name: properties.Name?.[0] || '',
            synonym: this.parseMultiLanguageString(properties.Synonym),
            comment: properties.Comment?.[0] || '',
            // Generated types
            generatedTypes: this.parseGeneratedTypes(catalogXml.InternalInfo),
            // Properties
            hierarchical: properties.Hierarchical?.[0] === 'true',
            hierarchyType: properties.HierarchyType?.[0] || '',
            codeLength: parseInt(properties.CodeLength?.[0]) || 0,
            descriptionLength: parseInt(properties.DescriptionLength?.[0]) || 0,
            codeType: properties.CodeType?.[0] || 'String',
            checkUnique: properties.CheckUnique?.[0] === 'true',
            autonumbering: properties.Autonumbering?.[0] === 'true',
            defaultPresentation: properties.DefaultPresentation?.[0] || '',
            // Attributes
            standardAttributes: this.parseStandardAttributes(properties.StandardAttributes),
            attributes: this.parseCustomAttributes(catalogXml.ChildObjects?.[0]?.Attribute),
            // Forms and commands
            forms: this.parseFormReferences(catalogXml.ChildObjects?.[0]?.Form),
            commands: this.parseCommandReferences(catalogXml.ChildObjects?.[0]?.Command),
            // Modules (will be filled by findRelatedFiles)
            managerModule: undefined,
            objectModule: undefined
        };
    }
    /**
     * Parse Document metadata
     */
    async parseDocument(documentXml, xmlFilePath) {
        const properties = documentXml.Properties?.[0] || {};
        return {
            type: 'Document',
            uuid: documentXml.$?.uuid || '',
            name: properties.Name?.[0] || '',
            synonym: this.parseMultiLanguageString(properties.Synonym),
            comment: properties.Comment?.[0] || '',
            generatedTypes: this.parseGeneratedTypes(documentXml.InternalInfo),
            numberLength: parseInt(properties.NumberLength?.[0]) || 0,
            numberType: properties.NumberType?.[0] || 'String',
            checkUnique: properties.CheckUnique?.[0] === 'true',
            autonumbering: properties.Autonumbering?.[0] === 'true',
            standardAttributes: this.parseStandardAttributes(properties.StandardAttributes),
            attributes: this.parseCustomAttributes(documentXml.ChildObjects?.[0]?.Attribute),
            tabularSections: this.parseTabularSections(documentXml.ChildObjects?.[0]?.TabularSection),
            forms: this.parseFormReferences(documentXml.ChildObjects?.[0]?.Form),
            commands: this.parseCommandReferences(documentXml.ChildObjects?.[0]?.Command),
            managerModule: undefined,
            objectModule: undefined
        };
    }
    /**
     * Parse DataProcessor metadata
     */
    async parseDataProcessor(dpXml, xmlFilePath) {
        const properties = dpXml.Properties?.[0] || {};
        return {
            type: 'DataProcessor',
            uuid: dpXml.$?.uuid || '',
            name: properties.Name?.[0] || '',
            synonym: this.parseMultiLanguageString(properties.Synonym),
            comment: properties.Comment?.[0] || '',
            generatedTypes: this.parseGeneratedTypes(dpXml.InternalInfo),
            defaultForm: properties.DefaultForm?.[0],
            attributes: this.parseCustomAttributes(dpXml.ChildObjects?.[0]?.Attribute),
            tabularSections: this.parseTabularSections(dpXml.ChildObjects?.[0]?.TabularSection),
            forms: this.parseFormReferences(dpXml.ChildObjects?.[0]?.Form),
            commands: this.parseCommandReferences(dpXml.ChildObjects?.[0]?.Command),
            objectModule: undefined
        };
    }
    /**
     * Parse CommonModule metadata
     */
    async parseCommonModule(cmXml, xmlFilePath) {
        const properties = cmXml.Properties?.[0] || {};
        return {
            type: 'CommonModule',
            uuid: cmXml.$?.uuid || '',
            name: properties.Name?.[0] || '',
            synonym: this.parseMultiLanguageString(properties.Synonym),
            comment: properties.Comment?.[0] || '',
            global: properties.Global?.[0] === 'true',
            clientManagedApplication: properties.ClientManagedApplication?.[0] === 'true',
            server: properties.Server?.[0] === 'true',
            externalConnection: properties.ExternalConnection?.[0] === 'true',
            clientOrdinaryApplication: properties.ClientOrdinaryApplication?.[0] === 'true',
            serverCall: properties.ServerCall?.[0] === 'true',
            privileged: properties.Privileged?.[0] === 'true',
            returnValuesReuse: properties.ReturnValuesReuse?.[0] || 'DontUse',
            module: undefined
        };
    }
    /**
     * Parse multi-language string (Synonym fields)
     */
    parseMultiLanguageString(synonymXml) {
        if (!synonymXml || !synonymXml[0])
            return undefined;
        const items = synonymXml[0]['v8:item'];
        if (!items)
            return undefined;
        return {
            items: items.map((item) => ({
                lang: item['v8:lang']?.[0] || 'ru',
                content: item['v8:content']?.[0] || ''
            }))
        };
    }
    /**
     * Parse generated types
     */
    parseGeneratedTypes(internalInfoXml) {
        if (!internalInfoXml || !internalInfoXml[0])
            return [];
        const types = internalInfoXml[0]['xr:GeneratedType'];
        if (!types)
            return [];
        return types.map((type) => ({
            name: type.$?.name || '',
            category: type.$?.category || 'Object',
            typeId: type['xr:TypeId']?.[0] || '',
            valueId: type['xr:ValueId']?.[0] || ''
        }));
    }
    /**
     * Parse standard attributes
     */
    parseStandardAttributes(stdAttrsXml) {
        if (!stdAttrsXml || !stdAttrsXml[0])
            return [];
        const attrs = stdAttrsXml[0]['xr:StandardAttribute'];
        if (!attrs)
            return [];
        return attrs.map((attr) => ({
            name: attr.$?.name || '',
            fillChecking: attr['xr:FillChecking']?.[0],
            dataHistory: attr['xr:DataHistory']?.[0],
            fullTextSearch: attr['xr:FullTextSearch']?.[0],
            multiLine: attr['xr:MultiLine']?.[0] === 'true',
            format: attr['xr:Format']?.[0],
            synonym: this.parseMultiLanguageString(attr['xr:Synonym'])
        }));
    }
    /**
     * Parse custom attributes
     */
    parseCustomAttributes(attrsXml) {
        if (!attrsXml)
            return [];
        return attrsXml.map((attr) => ({
            name: attr.Name?.[0] || '',
            synonym: this.parseMultiLanguageString(attr.Synonym),
            comment: attr.Comment?.[0] || '',
            type: this.parseAttributeType(attr.Type),
            fillChecking: attr.FillChecking?.[0],
            fullTextSearch: attr.FullTextSearch?.[0],
            format: attr.Format?.[0],
            choiceForm: attr.ChoiceForm?.[0],
            tooltip: attr.ToolTip?.[0]
        }));
    }
    /**
     * Parse attribute type
     */
    parseAttributeType(typeXml) {
        // Simplified type parsing - can be enhanced
        if (!typeXml || !typeXml[0])
            return { types: [] };
        return {
            types: ['String'], // Placeholder
            stringQualifiers: undefined,
            numberQualifiers: undefined,
            dateQualifiers: undefined
        };
    }
    /**
     * Parse tabular sections
     */
    parseTabularSections(tabSecXml) {
        if (!tabSecXml)
            return [];
        return tabSecXml.map((ts) => ({
            name: ts.Properties?.[0]?.Name?.[0] || '',
            synonym: this.parseMultiLanguageString(ts.Properties?.[0]?.Synonym),
            comment: ts.Properties?.[0]?.Comment?.[0] || '',
            standardAttributes: this.parseStandardAttributes(ts.StandardAttributes),
            attributes: this.parseCustomAttributes(ts.Attributes?.[0]?.Attribute)
        }));
    }
    /**
     * Parse form references
     */
    parseFormReferences(formsXml) {
        if (!formsXml)
            return [];
        return formsXml.map((form) => ({
            name: form.$?.name || '',
            synonym: this.parseMultiLanguageString(form.Synonym),
            formType: form.FormType?.[0],
            usePurposes: form.UsePurposes?.map((up) => up) || [],
            xmlPath: undefined // Will be filled by findRelatedFiles
        }));
    }
    /**
     * Parse command references
     */
    parseCommandReferences(cmdsXml) {
        if (!cmdsXml)
            return [];
        return cmdsXml.map((cmd) => ({
            name: cmd.$?.name || '',
            synonym: this.parseMultiLanguageString(cmd.Synonym),
            group: cmd.Group?.[0],
            commandParameterType: cmd.CommandParameterType?.[0],
            modifiesData: cmd.ModifiesData?.[0] === 'true',
            xmlPath: undefined // Will be filled by findRelatedFiles
        }));
    }
    /**
     * Find related BSL module files
     */
    async findRelatedFiles(xmlFilePath, objectType) {
        // For 1C structure: Catalogs/Валюты.xml -> Catalogs/Валюты/ directory
        const parentDir = path.dirname(xmlFilePath);
        const objectName = path.basename(xmlFilePath, '.xml');
        const dir = path.join(parentDir, objectName);
        const result = {
            xmlFile: xmlFilePath
        };
        // For Form/Command/Template, look for module in Ext directory relative to XML
        if (objectType === 'Form') {
            // Form module: Forms/FormName/Ext/Form/Module.bsl
            const formModule = path.join(parentDir, objectName, 'Ext', 'Form', 'Module.bsl');
            if (fs.existsSync(formModule)) {
                result.formModules = [formModule];
            }
            return result;
        }
        if (objectType === 'Command') {
            // Command module: Commands/CommandName/Ext/CommandModule.bsl
            const commandModule = path.join(parentDir, objectName, 'Ext', 'CommandModule.bsl');
            if (fs.existsSync(commandModule)) {
                result.commandModules = [commandModule];
            }
            return result;
        }
        if (objectType === 'Template') {
            // Templates don't have modules
            return result;
        }
        // Look for Ext directory
        const extDir = path.join(dir, 'Ext');
        if (fs.existsSync(extDir)) {
            // Manager module
            const managerModule = path.join(extDir, 'ManagerModule.bsl');
            if (fs.existsSync(managerModule)) {
                result.managerModule = managerModule;
            }
            // Object module
            const objectModule = path.join(extDir, 'ObjectModule.bsl');
            if (fs.existsSync(objectModule)) {
                result.objectModule = objectModule;
            }
        }
        // Look for Commands directory
        const commandsDir = path.join(dir, 'Commands');
        if (fs.existsSync(commandsDir)) {
            const commandModules = [];
            const commands = fs.readdirSync(commandsDir);
            for (const cmdName of commands) {
                const cmdModule = path.join(commandsDir, cmdName, 'Ext', 'CommandModule.bsl');
                if (fs.existsSync(cmdModule)) {
                    commandModules.push(cmdModule);
                }
            }
            if (commandModules.length > 0) {
                result.commandModules = commandModules;
            }
        }
        // Look for Forms directory
        const formsDir = path.join(dir, 'Forms');
        const formsDirRu = path.join(dir, 'Формы');
        const actualFormsDir = fs.existsSync(formsDir) ? formsDir : formsDirRu;
        if (fs.existsSync(actualFormsDir)) {
            const formModules = [];
            const forms = fs.readdirSync(actualFormsDir);
            for (const formName of forms) {
                const formModule = path.join(actualFormsDir, formName, 'Ext', 'Form', 'Module.bsl');
                if (fs.existsSync(formModule)) {
                    formModules.push(formModule);
                }
            }
            if (formModules.length > 0) {
                result.formModules = formModules;
            }
        }
        return result;
    }
    /**
     * Get human-readable metadata summary
     */
    getSummary(result) {
        const meta = result.metadata;
        const lang = meta.synonym?.items[0]?.lang || 'ru';
        const displayName = meta.synonym?.items.find((i) => i.lang === lang)?.content || meta.name;
        let summary = `## ${result.objectType}: ${displayName} (${meta.name})\n\n`;
        summary += `**UUID:** ${meta.uuid}\n`;
        summary += `**Type:** ${result.objectType}\n\n`;
        if (meta.type === 'Catalog') {
            const catalog = meta;
            summary += `### Properties\n`;
            summary += `- Code Length: ${catalog.codeLength}\n`;
            summary += `- Description Length: ${catalog.descriptionLength}\n`;
            summary += `- Hierarchical: ${catalog.hierarchical ? 'Yes' : 'No'}\n`;
            summary += `- Unique Check: ${catalog.checkUnique ? 'Yes' : 'No'}\n\n`;
            if (catalog.attributes.length > 0) {
                summary += `### Attributes (${catalog.attributes.length})\n`;
                catalog.attributes.forEach((attr) => {
                    const attrName = attr.synonym?.items[0]?.content || attr.name;
                    summary += `- ${attrName} (${attr.name})\n`;
                });
                summary += `\n`;
            }
        }
        if (meta.type === 'Form') {
            const form = meta;
            summary += `### Form Properties\n`;
            summary += `- Form Type: ${form.formType}\n`;
            if (form.usePurposes.length > 0) {
                summary += `- Use Purposes: ${form.usePurposes.join(', ')}\n`;
            }
            summary += `\n`;
        }
        if (meta.type === 'Command') {
            const command = meta;
            summary += `### Command Properties\n`;
            if (command.group) {
                summary += `- Group: ${command.group}\n`;
            }
            summary += `- Modifies Data: ${command.modifiesData ? 'Yes' : 'No'}\n`;
            summary += `\n`;
        }
        summary += `### Related Files\n`;
        if (result.relatedFiles.managerModule) {
            summary += `- Manager Module: ${path.basename(result.relatedFiles.managerModule)}\n`;
        }
        if (result.relatedFiles.objectModule) {
            summary += `- Object Module: ${path.basename(result.relatedFiles.objectModule)}\n`;
        }
        if (result.relatedFiles.formModules && result.relatedFiles.formModules.length > 0) {
            summary += `- Form Modules: ${result.relatedFiles.formModules.length}\n`;
        }
        if (result.relatedFiles.commandModules && result.relatedFiles.commandModules.length > 0) {
            summary += `- Command Modules: ${result.relatedFiles.commandModules.length}\n`;
        }
        return summary;
    }
}
//# sourceMappingURL=metadata-parser.js.map