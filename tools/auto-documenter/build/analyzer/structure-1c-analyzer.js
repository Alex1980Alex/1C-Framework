/**
 * 1C Structure Analyzer
 * Detects metadata object types and provides structural information
 * for 1C:Enterprise configurations
 */
/**
 * 1C Metadata object types
 */
export var MetadataObjectType;
(function (MetadataObjectType) {
    // Reference Types (Справочники)
    MetadataObjectType["CATALOG"] = "Catalog";
    // Document Types (Документы)
    MetadataObjectType["DOCUMENT"] = "Document";
    MetadataObjectType["DOCUMENT_JOURNAL"] = "DocumentJournal";
    // Enumerations (Перечисления)
    MetadataObjectType["ENUM"] = "Enum";
    // Registers (Регистры)
    MetadataObjectType["INFORMATION_REGISTER"] = "InformationRegister";
    MetadataObjectType["ACCUMULATION_REGISTER"] = "AccumulationRegister";
    MetadataObjectType["ACCOUNTING_REGISTER"] = "AccountingRegister";
    MetadataObjectType["CALCULATION_REGISTER"] = "CalculationRegister";
    // Processing (Обработки и отчеты)
    MetadataObjectType["DATA_PROCESSOR"] = "DataProcessor";
    MetadataObjectType["REPORT"] = "Report";
    // Business Processes (Бизнес-процессы)
    MetadataObjectType["BUSINESS_PROCESS"] = "BusinessProcess";
    MetadataObjectType["TASK"] = "Task";
    // Exchange (Планы обмена)
    MetadataObjectType["EXCHANGE_PLAN"] = "ExchangePlan";
    // Plans (Планы)
    MetadataObjectType["CHART_OF_ACCOUNTS"] = "ChartOfAccounts";
    MetadataObjectType["CHART_OF_CHARACTERISTIC_TYPES"] = "ChartOfCharacteristicTypes";
    MetadataObjectType["CHART_OF_CALCULATION_TYPES"] = "ChartOfCalculationTypes";
    // Common (Общие)
    MetadataObjectType["COMMON_MODULE"] = "CommonModule";
    MetadataObjectType["COMMON_FORM"] = "CommonForm";
    MetadataObjectType["COMMON_COMMAND"] = "CommonCommand";
    MetadataObjectType["COMMON_TEMPLATE"] = "CommonTemplate";
    MetadataObjectType["COMMON_PICTURE"] = "CommonPicture";
    // Web Services (Веб-сервисы)
    MetadataObjectType["WEB_SERVICE"] = "WebService";
    MetadataObjectType["HTTP_SERVICE"] = "HTTPService";
    // External Data Sources (Внешние источники данных)
    MetadataObjectType["EXTERNAL_DATA_SOURCE"] = "ExternalDataSource";
    // Sequences (Последовательности)
    MetadataObjectType["SEQUENCE"] = "Sequence";
    // Scheduled Jobs (Регламентные задания)
    MetadataObjectType["SCHEDULED_JOB"] = "ScheduledJob";
    // Functional Options (Функциональные опции)
    MetadataObjectType["FUNCTIONAL_OPTION"] = "FunctionalOption";
    MetadataObjectType["FUNCTIONAL_OPTIONS_PARAMETER"] = "FunctionalOptionsParameter";
    // Subsystems (Подсистемы)
    MetadataObjectType["SUBSYSTEM"] = "Subsystem";
    // Constants (Константы)
    MetadataObjectType["CONSTANT"] = "Constant";
    // Sessions (Параметры сеанса)
    MetadataObjectType["SESSION_PARAMETER"] = "SessionParameter";
    // Roles (Роли)
    MetadataObjectType["ROLE"] = "Role";
    // Configuration (Конфигурация)
    MetadataObjectType["CONFIGURATION"] = "Configuration";
    // Unknown
    MetadataObjectType["UNKNOWN"] = "Unknown";
})(MetadataObjectType || (MetadataObjectType = {}));
/**
 * Module types within metadata objects
 */
export var ModuleType;
(function (ModuleType) {
    ModuleType["OBJECT_MODULE"] = "ObjectModule";
    ModuleType["MANAGER_MODULE"] = "ManagerModule";
    ModuleType["FORM_MODULE"] = "FormModule";
    ModuleType["COMMAND_MODULE"] = "CommandModule";
    ModuleType["RECORDSET_MODULE"] = "RecordSetModule";
    ModuleType["VALUE_MANAGER_MODULE"] = "ValueManagerModule";
    ModuleType["SESSION_MODULE"] = "SessionModule";
    ModuleType["APPLICATION_MODULE"] = "ApplicationModule";
    ModuleType["MANAGED_APPLICATION_MODULE"] = "ManagedApplicationModule";
    ModuleType["EXTERNAL_CONNECTION_MODULE"] = "ExternalConnectionModule";
    ModuleType["COMMON_MODULE"] = "CommonModule";
    ModuleType["UNKNOWN"] = "Unknown";
})(ModuleType || (ModuleType = {}));
/**
 * Mapping of directory names to metadata types
 * Supports both English and Russian folder names
 */
const metadataTypePatterns = [
    // Catalogs (Справочники)
    {
        patterns: [/[/\\]Catalogs?[/\\]/i, /[/\\]Справочники?[/\\]/i],
        type: MetadataObjectType.CATALOG,
        description: 'Справочник'
    },
    // Documents (Документы)
    {
        patterns: [/[/\\]Documents?[/\\]/i, /[/\\]Документы?[/\\]/i],
        type: MetadataObjectType.DOCUMENT,
        description: 'Документ'
    },
    // Document Journals (Журналы документов)
    {
        patterns: [/[/\\]DocumentJournals?[/\\]/i, /[/\\]ЖурналыДокументов[/\\]/i],
        type: MetadataObjectType.DOCUMENT_JOURNAL,
        description: 'Журнал документов'
    },
    // Enumerations (Перечисления)
    {
        patterns: [/[/\\]Enums?[/\\]/i, /[/\\]Перечисления?[/\\]/i],
        type: MetadataObjectType.ENUM,
        description: 'Перечисление'
    },
    // Information Registers (Регистры сведений)
    {
        patterns: [/[/\\]InformationRegisters?[/\\]/i, /[/\\]РегистрыСведений[/\\]/i],
        type: MetadataObjectType.INFORMATION_REGISTER,
        description: 'Регистр сведений'
    },
    // Accumulation Registers (Регистры накопления)
    {
        patterns: [/[/\\]AccumulationRegisters?[/\\]/i, /[/\\]РегистрыНакопления[/\\]/i],
        type: MetadataObjectType.ACCUMULATION_REGISTER,
        description: 'Регистр накопления'
    },
    // Accounting Registers (Регистры бухгалтерии)
    {
        patterns: [/[/\\]AccountingRegisters?[/\\]/i, /[/\\]РегистрыБухгалтерии[/\\]/i],
        type: MetadataObjectType.ACCOUNTING_REGISTER,
        description: 'Регистр бухгалтерии'
    },
    // Calculation Registers (Регистры расчета)
    {
        patterns: [/[/\\]CalculationRegisters?[/\\]/i, /[/\\]РегистрыРасчета[/\\]/i],
        type: MetadataObjectType.CALCULATION_REGISTER,
        description: 'Регистр расчета'
    },
    // Data Processors (Обработки)
    {
        patterns: [/[/\\]DataProcessors?[/\\]/i, /[/\\]Обработки?[/\\]/i],
        type: MetadataObjectType.DATA_PROCESSOR,
        description: 'Обработка'
    },
    // Reports (Отчеты)
    {
        patterns: [/[/\\]Reports?[/\\]/i, /[/\\]Отчеты?[/\\]/i],
        type: MetadataObjectType.REPORT,
        description: 'Отчет'
    },
    // Business Processes (Бизнес-процессы)
    {
        patterns: [/[/\\]BusinessProcess(es)?[/\\]/i, /[/\\]БизнесПроцессы?[/\\]/i],
        type: MetadataObjectType.BUSINESS_PROCESS,
        description: 'Бизнес-процесс'
    },
    // Tasks (Задачи)
    {
        patterns: [/[/\\]Tasks?[/\\]/i, /[/\\]Задачи?[/\\]/i],
        type: MetadataObjectType.TASK,
        description: 'Задача'
    },
    // Exchange Plans (Планы обмена)
    {
        patterns: [/[/\\]ExchangePlans?[/\\]/i, /[/\\]ПланыОбмена[/\\]/i],
        type: MetadataObjectType.EXCHANGE_PLAN,
        description: 'План обмена'
    },
    // Chart of Accounts (Планы счетов)
    {
        patterns: [/[/\\]ChartsOfAccounts?[/\\]/i, /[/\\]ПланыСчетов[/\\]/i],
        type: MetadataObjectType.CHART_OF_ACCOUNTS,
        description: 'План счетов'
    },
    // Chart of Characteristic Types (Планы видов характеристик)
    {
        patterns: [/[/\\]ChartsOfCharacteristicTypes?[/\\]/i, /[/\\]ПланыВидовХарактеристик[/\\]/i],
        type: MetadataObjectType.CHART_OF_CHARACTERISTIC_TYPES,
        description: 'План видов характеристик'
    },
    // Chart of Calculation Types (Планы видов расчета)
    {
        patterns: [/[/\\]ChartsOfCalculationTypes?[/\\]/i, /[/\\]ПланыВидовРасчета[/\\]/i],
        type: MetadataObjectType.CHART_OF_CALCULATION_TYPES,
        description: 'План видов расчета'
    },
    // Common Modules (Общие модули)
    {
        patterns: [/[/\\]CommonModules?[/\\]/i, /[/\\]ОбщиеМодули[/\\]/i],
        type: MetadataObjectType.COMMON_MODULE,
        description: 'Общий модуль'
    },
    // Common Forms (Общие формы)
    {
        patterns: [/[/\\]CommonForms?[/\\]/i, /[/\\]ОбщиеФормы[/\\]/i],
        type: MetadataObjectType.COMMON_FORM,
        description: 'Общая форма'
    },
    // Common Commands (Общие команды)
    {
        patterns: [/[/\\]CommonCommands?[/\\]/i, /[/\\]ОбщиеКоманды[/\\]/i],
        type: MetadataObjectType.COMMON_COMMAND,
        description: 'Общая команда'
    },
    // Common Templates (Общие макеты)
    {
        patterns: [/[/\\]CommonTemplates?[/\\]/i, /[/\\]ОбщиеМакеты[/\\]/i],
        type: MetadataObjectType.COMMON_TEMPLATE,
        description: 'Общий макет'
    },
    // Common Pictures (Общие картинки)
    {
        patterns: [/[/\\]CommonPictures?[/\\]/i, /[/\\]ОбщиеКартинки[/\\]/i],
        type: MetadataObjectType.COMMON_PICTURE,
        description: 'Общая картинка'
    },
    // Web Services (Веб-сервисы)
    {
        patterns: [/[/\\]WebServices?[/\\]/i, /[/\\]ВебСервисы[/\\]/i],
        type: MetadataObjectType.WEB_SERVICE,
        description: 'Веб-сервис'
    },
    // HTTP Services (HTTP-сервисы)
    {
        patterns: [/[/\\]HTTPServices?[/\\]/i, /[/\\]HTTPСервисы[/\\]/i],
        type: MetadataObjectType.HTTP_SERVICE,
        description: 'HTTP-сервис'
    },
    // External Data Sources (Внешние источники данных)
    {
        patterns: [/[/\\]ExternalDataSources?[/\\]/i, /[/\\]ВнешниеИсточникиДанных[/\\]/i],
        type: MetadataObjectType.EXTERNAL_DATA_SOURCE,
        description: 'Внешний источник данных'
    },
    // Sequences (Последовательности)
    {
        patterns: [/[/\\]Sequences?[/\\]/i, /[/\\]Последовательности?[/\\]/i],
        type: MetadataObjectType.SEQUENCE,
        description: 'Последовательность'
    },
    // Scheduled Jobs (Регламентные задания)
    {
        patterns: [/[/\\]ScheduledJobs?[/\\]/i, /[/\\]РегламентныеЗадания[/\\]/i],
        type: MetadataObjectType.SCHEDULED_JOB,
        description: 'Регламентное задание'
    },
    // Functional Options (Функциональные опции)
    {
        patterns: [/[/\\]FunctionalOptions?[/\\]/i, /[/\\]ФункциональныеОпции[/\\]/i],
        type: MetadataObjectType.FUNCTIONAL_OPTION,
        description: 'Функциональная опция'
    },
    // Functional Options Parameters (Параметры функциональных опций)
    {
        patterns: [/[/\\]FunctionalOptionsParameters?[/\\]/i, /[/\\]ПараметрыФункциональныхОпций[/\\]/i],
        type: MetadataObjectType.FUNCTIONAL_OPTIONS_PARAMETER,
        description: 'Параметр функциональных опций'
    },
    // Subsystems (Подсистемы)
    {
        patterns: [/[/\\]Subsystems?[/\\]/i, /[/\\]Подсистемы?[/\\]/i],
        type: MetadataObjectType.SUBSYSTEM,
        description: 'Подсистема'
    },
    // Constants (Константы)
    {
        patterns: [/[/\\]Constants?[/\\]/i, /[/\\]Константы?[/\\]/i],
        type: MetadataObjectType.CONSTANT,
        description: 'Константа'
    },
    // Session Parameters (Параметры сеанса)
    {
        patterns: [/[/\\]SessionParameters?[/\\]/i, /[/\\]ПараметрыСеанса[/\\]/i],
        type: MetadataObjectType.SESSION_PARAMETER,
        description: 'Параметр сеанса'
    },
    // Roles (Роли)
    {
        patterns: [/[/\\]Roles?[/\\]/i, /[/\\]Роли?[/\\]/i],
        type: MetadataObjectType.ROLE,
        description: 'Роль'
    }
];
/**
 * Module type descriptions in Russian
 */
const moduleTypeDescriptions = {
    [ModuleType.OBJECT_MODULE]: 'Модуль объекта',
    [ModuleType.MANAGER_MODULE]: 'Модуль менеджера',
    [ModuleType.FORM_MODULE]: 'Модуль формы',
    [ModuleType.COMMAND_MODULE]: 'Модуль команды',
    [ModuleType.RECORDSET_MODULE]: 'Модуль набора записей',
    [ModuleType.VALUE_MANAGER_MODULE]: 'Модуль менеджера значения',
    [ModuleType.SESSION_MODULE]: 'Модуль сеанса',
    [ModuleType.APPLICATION_MODULE]: 'Модуль приложения',
    [ModuleType.MANAGED_APPLICATION_MODULE]: 'Модуль управляемого приложения',
    [ModuleType.EXTERNAL_CONNECTION_MODULE]: 'Модуль внешнего соединения',
    [ModuleType.COMMON_MODULE]: 'Общий модуль',
    [ModuleType.UNKNOWN]: 'Неизвестный тип модуля'
};
/**
 * 1C Structure Analyzer class
 * Analyzes file paths to detect metadata object types and extract structural information
 */
export class Structure1CAnalyzer {
    /**
     * Analyzes a file path and returns structural information
     * @param filePath Path to the BSL file
     * @returns Parsed file path information
     */
    analyze(filePath) {
        const normalizedPath = filePath.replace(/\\/g, '/');
        // Detect metadata type
        const metadataInfo = this.detectMetadataType(normalizedPath);
        // Extract object name
        const objectName = this.extractObjectName(normalizedPath, metadataInfo.type);
        // Detect module type
        const moduleType = this.detectModuleType(normalizedPath);
        // Extract form name if applicable
        const formName = this.extractFormName(normalizedPath);
        // Extract command name if applicable
        const commandName = this.extractCommandName(normalizedPath);
        // Build relative path
        const relativePath = this.buildRelativePath(normalizedPath);
        return {
            filePath,
            metadataType: metadataInfo.type,
            objectName,
            moduleType,
            formName,
            commandName,
            relativePath,
            metadataTypeDescription: metadataInfo.description,
            moduleTypeDescription: moduleTypeDescriptions[moduleType]
        };
    }
    /**
     * Detects metadata type from file path
     */
    detectMetadataType(filePath) {
        for (const entry of metadataTypePatterns) {
            for (const pattern of entry.patterns) {
                if (pattern.test(filePath)) {
                    return { type: entry.type, description: entry.description };
                }
            }
        }
        // Check for configuration-level modules
        if (/SessionModule\.bsl$/i.test(filePath)) {
            return { type: MetadataObjectType.CONFIGURATION, description: 'Конфигурация' };
        }
        if (/ApplicationModule\.bsl$/i.test(filePath)) {
            return { type: MetadataObjectType.CONFIGURATION, description: 'Конфигурация' };
        }
        if (/ManagedApplicationModule\.bsl$/i.test(filePath)) {
            return { type: MetadataObjectType.CONFIGURATION, description: 'Конфигурация' };
        }
        if (/ExternalConnectionModule\.bsl$/i.test(filePath)) {
            return { type: MetadataObjectType.CONFIGURATION, description: 'Конфигурация' };
        }
        return { type: MetadataObjectType.UNKNOWN, description: 'Неизвестный тип' };
    }
    /**
     * Extracts object name from file path
     */
    extractObjectName(filePath, metadataType) {
        // Pattern to extract object name after metadata type folder
        // e.g., /Catalogs/Товары/... -> Товары
        // e.g., /CommonModules/ОбщегоНазначения/... -> ОбщегоНазначения
        const patterns = [
            // English patterns
            /[/\\]Catalogs?[/\\]([^/\\]+)/i,
            /[/\\]Documents?[/\\]([^/\\]+)/i,
            /[/\\]DocumentJournals?[/\\]([^/\\]+)/i,
            /[/\\]Enums?[/\\]([^/\\]+)/i,
            /[/\\]InformationRegisters?[/\\]([^/\\]+)/i,
            /[/\\]AccumulationRegisters?[/\\]([^/\\]+)/i,
            /[/\\]AccountingRegisters?[/\\]([^/\\]+)/i,
            /[/\\]CalculationRegisters?[/\\]([^/\\]+)/i,
            /[/\\]DataProcessors?[/\\]([^/\\]+)/i,
            /[/\\]Reports?[/\\]([^/\\]+)/i,
            /[/\\]BusinessProcess(?:es)?[/\\]([^/\\]+)/i,
            /[/\\]Tasks?[/\\]([^/\\]+)/i,
            /[/\\]ExchangePlans?[/\\]([^/\\]+)/i,
            /[/\\]ChartsOfAccounts?[/\\]([^/\\]+)/i,
            /[/\\]ChartsOfCharacteristicTypes?[/\\]([^/\\]+)/i,
            /[/\\]ChartsOfCalculationTypes?[/\\]([^/\\]+)/i,
            /[/\\]CommonModules?[/\\]([^/\\]+)/i,
            /[/\\]CommonForms?[/\\]([^/\\]+)/i,
            /[/\\]CommonCommands?[/\\]([^/\\]+)/i,
            /[/\\]WebServices?[/\\]([^/\\]+)/i,
            /[/\\]HTTPServices?[/\\]([^/\\]+)/i,
            /[/\\]Subsystems?[/\\]([^/\\]+)/i,
            /[/\\]Constants?[/\\]([^/\\]+)/i,
            /[/\\]Roles?[/\\]([^/\\]+)/i,
            // Russian patterns
            /[/\\]Справочники?[/\\]([^/\\]+)/i,
            /[/\\]Документы?[/\\]([^/\\]+)/i,
            /[/\\]Перечисления?[/\\]([^/\\]+)/i,
            /[/\\]РегистрыСведений[/\\]([^/\\]+)/i,
            /[/\\]РегистрыНакопления[/\\]([^/\\]+)/i,
            /[/\\]Обработки?[/\\]([^/\\]+)/i,
            /[/\\]Отчеты?[/\\]([^/\\]+)/i,
            /[/\\]ОбщиеМодули[/\\]([^/\\]+)/i,
            /[/\\]ОбщиеФормы[/\\]([^/\\]+)/i,
            /[/\\]Подсистемы?[/\\]([^/\\]+)/i
        ];
        for (const pattern of patterns) {
            const match = filePath.match(pattern);
            if (match && match[1]) {
                return match[1];
            }
        }
        return '';
    }
    /**
     * Detects module type from file path
     */
    detectModuleType(filePath) {
        const lowerPath = filePath.toLowerCase();
        // Form module
        if (/[/\\]forms?[/\\][^/\\]+[/\\]ext[/\\]form[/\\]module\.bsl$/i.test(filePath) ||
            /[/\\]формы[/\\][^/\\]+[/\\]ext[/\\]form[/\\]module\.bsl$/i.test(filePath)) {
            return ModuleType.FORM_MODULE;
        }
        // Object module
        if (lowerPath.includes('/ext/objectmodule.bsl') || lowerPath.includes('\\ext\\objectmodule.bsl')) {
            return ModuleType.OBJECT_MODULE;
        }
        // Manager module
        if (lowerPath.includes('/ext/managermodule.bsl') || lowerPath.includes('\\ext\\managermodule.bsl')) {
            return ModuleType.MANAGER_MODULE;
        }
        // Command module
        if (/[/\\]commands?[/\\][^/\\]+[/\\]ext[/\\]commandmodule\.bsl$/i.test(filePath) ||
            /[/\\]команды[/\\][^/\\]+[/\\]ext[/\\]commandmodule\.bsl$/i.test(filePath)) {
            return ModuleType.COMMAND_MODULE;
        }
        // RecordSet module
        if (lowerPath.includes('/ext/recordsetmodule.bsl') || lowerPath.includes('\\ext\\recordsetmodule.bsl')) {
            return ModuleType.RECORDSET_MODULE;
        }
        // Value manager module
        if (lowerPath.includes('/ext/valuemanagermodule.bsl') || lowerPath.includes('\\ext\\valuemanagermodule.bsl')) {
            return ModuleType.VALUE_MANAGER_MODULE;
        }
        // Session module
        if (lowerPath.endsWith('sessionmodule.bsl')) {
            return ModuleType.SESSION_MODULE;
        }
        // Managed application module (check before ApplicationModule!)
        if (lowerPath.endsWith('managedapplicationmodule.bsl')) {
            return ModuleType.MANAGED_APPLICATION_MODULE;
        }
        // Application module
        if (lowerPath.endsWith('applicationmodule.bsl')) {
            return ModuleType.APPLICATION_MODULE;
        }
        // External connection module
        if (lowerPath.endsWith('externalconnectionmodule.bsl')) {
            return ModuleType.EXTERNAL_CONNECTION_MODULE;
        }
        // Common module (ends with /Ext/Module.bsl in CommonModules)
        if (/[/\\]commonmodules?[/\\][^/\\]+[/\\]ext[/\\]module\.bsl$/i.test(filePath) ||
            /[/\\]общиемодули[/\\][^/\\]+[/\\]ext[/\\]module\.bsl$/i.test(filePath)) {
            return ModuleType.COMMON_MODULE;
        }
        return ModuleType.UNKNOWN;
    }
    /**
     * Extracts form name from file path
     */
    extractFormName(filePath) {
        // Pattern: /Forms/FormName/Ext/Form/Module.bsl
        const pattern = /[/\\](?:Forms?|Формы)[/\\]([^/\\]+)[/\\]Ext[/\\]Form[/\\]Module\.bsl$/i;
        const match = filePath.match(pattern);
        return match ? match[1] : undefined;
    }
    /**
     * Extracts command name from file path
     */
    extractCommandName(filePath) {
        // Pattern: /Commands/CommandName/Ext/CommandModule.bsl
        const pattern = /[/\\](?:Commands?|Команды)[/\\]([^/\\]+)[/\\]Ext[/\\]CommandModule\.bsl$/i;
        const match = filePath.match(pattern);
        return match ? match[1] : undefined;
    }
    /**
     * Builds relative path from configuration root
     */
    buildRelativePath(filePath) {
        // Try to find the start of the configuration structure
        const patterns = [
            /[/\\](Catalogs?|Справочники?)[/\\]/i,
            /[/\\](Documents?|Документы?)[/\\]/i,
            /[/\\](CommonModules?|ОбщиеМодули)[/\\]/i,
            /[/\\](DataProcessors?|Обработки?)[/\\]/i,
            /[/\\](Reports?|Отчеты?)[/\\]/i,
            /[/\\](InformationRegisters?|РегистрыСведений)[/\\]/i,
            /[/\\](AccumulationRegisters?|РегистрыНакопления)[/\\]/i
        ];
        for (const pattern of patterns) {
            const match = filePath.match(pattern);
            if (match) {
                const index = filePath.indexOf(match[0]);
                if (index !== -1) {
                    return filePath.substring(index + 1); // Remove leading separator
                }
            }
        }
        return filePath;
    }
    /**
     * Gets context information for documentation
     * @param info Parsed file path information
     * @returns Context string for LLM prompts
     */
    getContextInfo(info) {
        const lines = [];
        lines.push(`=== СТРУКТУРА 1С ===`);
        lines.push(`Тип объекта метаданных: ${info.metadataTypeDescription}`);
        if (info.objectName) {
            lines.push(`Имя объекта: ${info.objectName}`);
        }
        lines.push(`Тип модуля: ${info.moduleTypeDescription}`);
        if (info.formName) {
            lines.push(`Имя формы: ${info.formName}`);
        }
        if (info.commandName) {
            lines.push(`Имя команды: ${info.commandName}`);
        }
        lines.push(`Путь: ${info.relativePath}`);
        // Add context-specific guidance
        lines.push('');
        lines.push('Рекомендации по документированию:');
        lines.push(this.getDocumentationGuidance(info));
        return lines.join('\n');
    }
    /**
     * Gets documentation guidance based on metadata and module type
     */
    getDocumentationGuidance(info) {
        switch (info.metadataType) {
            case MetadataObjectType.CATALOG:
                return this.getCatalogGuidance(info.moduleType);
            case MetadataObjectType.DOCUMENT:
                return this.getDocumentGuidance(info.moduleType);
            case MetadataObjectType.DATA_PROCESSOR:
                return this.getDataProcessorGuidance(info.moduleType);
            case MetadataObjectType.REPORT:
                return this.getReportGuidance(info.moduleType);
            case MetadataObjectType.COMMON_MODULE:
                return this.getCommonModuleGuidance();
            case MetadataObjectType.INFORMATION_REGISTER:
                return this.getInformationRegisterGuidance(info.moduleType);
            case MetadataObjectType.ACCUMULATION_REGISTER:
                return this.getAccumulationRegisterGuidance(info.moduleType);
            default:
                return this.getDefaultGuidance(info.moduleType);
        }
    }
    getCatalogGuidance(moduleType) {
        switch (moduleType) {
            case ModuleType.OBJECT_MODULE:
                return '- Опишите бизнес-правила проверки данных элемента\n- Укажите обработчики событий (ПередЗаписью, ПриКопировании, ОбработкаЗаполнения)\n- Документируйте связи с другими объектами';
            case ModuleType.MANAGER_MODULE:
                return '- Опишите программный интерфейс справочника\n- Укажите функции поиска и создания элементов\n- Документируйте утилиты работы со справочником';
            case ModuleType.FORM_MODULE:
                return '- Опишите обработчики событий формы\n- Укажите валидацию данных на клиенте\n- Документируйте управление видимостью элементов';
            default:
                return '- Документируйте назначение и использование модуля';
        }
    }
    getDocumentGuidance(moduleType) {
        switch (moduleType) {
            case ModuleType.OBJECT_MODULE:
                return '- Опишите алгоритм проведения документа\n- Укажите формируемые движения по регистрам\n- Документируйте проверки перед записью и проведением';
            case ModuleType.MANAGER_MODULE:
                return '- Опишите функции формирования печатных форм\n- Укажите методы проверки и обработки документов\n- Документируйте программный интерфейс';
            case ModuleType.FORM_MODULE:
                return '- Опишите обработчики событий табличных частей\n- Укажите расчеты и автозаполнение\n- Документируйте команды документа';
            default:
                return '- Документируйте назначение и использование модуля';
        }
    }
    getDataProcessorGuidance(moduleType) {
        switch (moduleType) {
            case ModuleType.OBJECT_MODULE:
                return '- Опишите основной алгоритм обработки\n- Укажите входные и выходные данные\n- Документируйте обработку ошибок';
            case ModuleType.FORM_MODULE:
                return '- Опишите взаимодействие с пользователем\n- Укажите параметры обработки\n- Документируйте отображение результатов';
            default:
                return '- Документируйте назначение и использование обработки';
        }
    }
    getReportGuidance(moduleType) {
        switch (moduleType) {
            case ModuleType.OBJECT_MODULE:
                return '- Опишите источники данных отчета\n- Укажите параметры формирования\n- Документируйте настройки СКД';
            case ModuleType.FORM_MODULE:
                return '- Опишите управление настройками отчета\n- Укажите пользовательские команды\n- Документируйте дополнительную обработку данных';
            default:
                return '- Документируйте назначение и использование отчета';
        }
    }
    getCommonModuleGuidance() {
        return '- Четко документируйте экспортные функции API\n- Укажите параметры и возвращаемые значения\n- Добавьте примеры использования\n- Опишите зависимости от других модулей';
    }
    getInformationRegisterGuidance(moduleType) {
        switch (moduleType) {
            case ModuleType.RECORDSET_MODULE:
                return '- Опишите структуру хранения данных\n- Укажите проверки при записи\n- Документируйте связи с измерениями';
            case ModuleType.MANAGER_MODULE:
                return '- Опишите методы получения данных\n- Укажите функции записи и удаления\n- Документируйте работу со срезами';
            default:
                return '- Документируйте назначение регистра сведений';
        }
    }
    getAccumulationRegisterGuidance(moduleType) {
        switch (moduleType) {
            case ModuleType.RECORDSET_MODULE:
                return '- Опишите агрегирование данных\n- Укажите виды движений (приход/расход)\n- Документируйте измерения и ресурсы';
            case ModuleType.MANAGER_MODULE:
                return '- Опишите методы получения остатков и оборотов\n- Укажите функции анализа данных\n- Документируйте работу с виртуальными таблицами';
            default:
                return '- Документируйте назначение регистра накопления';
        }
    }
    getDefaultGuidance(moduleType) {
        switch (moduleType) {
            case ModuleType.FORM_MODULE:
                return '- Опишите обработчики событий формы\n- Укажите команды и действия\n- Документируйте валидацию данных';
            case ModuleType.OBJECT_MODULE:
                return '- Опишите бизнес-логику объекта\n- Укажите обработчики событий\n- Документируйте проверки данных';
            case ModuleType.MANAGER_MODULE:
                return '- Опишите программный интерфейс\n- Укажите экспортные функции\n- Документируйте использование';
            default:
                return '- Документируйте назначение и использование модуля';
        }
    }
    /**
     * Checks if path belongs to 1C configuration
     * @param filePath Path to check
     * @returns true if path appears to be part of 1C configuration
     */
    isConfigurationPath(filePath) {
        const info = this.analyze(filePath);
        return info.metadataType !== MetadataObjectType.UNKNOWN;
    }
    /**
     * Gets all metadata types with descriptions
     * @returns Array of metadata type entries
     */
    getAllMetadataTypes() {
        return metadataTypePatterns.map(entry => ({
            type: entry.type,
            description: entry.description
        }));
    }
}
// Export singleton instance
export const structure1CAnalyzer = new Structure1CAnalyzer();
// Export main function for convenience
export function analyze1CStructure(filePath) {
    return structure1CAnalyzer.analyze(filePath);
}
// Export context getter for convenience
export function get1CContextInfo(filePath) {
    const info = structure1CAnalyzer.analyze(filePath);
    return structure1CAnalyzer.getContextInfo(info);
}
//# sourceMappingURL=structure-1c-analyzer.js.map