/**
 * 1C Structure Analyzer
 * Detects metadata object types and provides structural information
 * for 1C:Enterprise configurations
 */
/**
 * 1C Metadata object types
 */
export declare enum MetadataObjectType {
    CATALOG = "Catalog",
    DOCUMENT = "Document",
    DOCUMENT_JOURNAL = "DocumentJournal",
    ENUM = "Enum",
    INFORMATION_REGISTER = "InformationRegister",
    ACCUMULATION_REGISTER = "AccumulationRegister",
    ACCOUNTING_REGISTER = "AccountingRegister",
    CALCULATION_REGISTER = "CalculationRegister",
    DATA_PROCESSOR = "DataProcessor",
    REPORT = "Report",
    BUSINESS_PROCESS = "BusinessProcess",
    TASK = "Task",
    EXCHANGE_PLAN = "ExchangePlan",
    CHART_OF_ACCOUNTS = "ChartOfAccounts",
    CHART_OF_CHARACTERISTIC_TYPES = "ChartOfCharacteristicTypes",
    CHART_OF_CALCULATION_TYPES = "ChartOfCalculationTypes",
    COMMON_MODULE = "CommonModule",
    COMMON_FORM = "CommonForm",
    COMMON_COMMAND = "CommonCommand",
    COMMON_TEMPLATE = "CommonTemplate",
    COMMON_PICTURE = "CommonPicture",
    WEB_SERVICE = "WebService",
    HTTP_SERVICE = "HTTPService",
    EXTERNAL_DATA_SOURCE = "ExternalDataSource",
    SEQUENCE = "Sequence",
    SCHEDULED_JOB = "ScheduledJob",
    FUNCTIONAL_OPTION = "FunctionalOption",
    FUNCTIONAL_OPTIONS_PARAMETER = "FunctionalOptionsParameter",
    SUBSYSTEM = "Subsystem",
    CONSTANT = "Constant",
    SESSION_PARAMETER = "SessionParameter",
    ROLE = "Role",
    CONFIGURATION = "Configuration",
    UNKNOWN = "Unknown"
}
/**
 * Module types within metadata objects
 */
export declare enum ModuleType {
    OBJECT_MODULE = "ObjectModule",
    MANAGER_MODULE = "ManagerModule",
    FORM_MODULE = "FormModule",
    COMMAND_MODULE = "CommandModule",
    RECORDSET_MODULE = "RecordSetModule",
    VALUE_MANAGER_MODULE = "ValueManagerModule",
    SESSION_MODULE = "SessionModule",
    APPLICATION_MODULE = "ApplicationModule",
    MANAGED_APPLICATION_MODULE = "ManagedApplicationModule",
    EXTERNAL_CONNECTION_MODULE = "ExternalConnectionModule",
    COMMON_MODULE = "CommonModule",
    UNKNOWN = "Unknown"
}
/**
 * Information about a parsed 1C file path
 */
export interface FilePathInfo {
    /** Original file path */
    filePath: string;
    /** Type of metadata object (Catalog, Document, etc.) */
    metadataType: MetadataObjectType;
    /** Name of the metadata object */
    objectName: string;
    /** Type of module (ObjectModule, ManagerModule, FormModule, etc.) */
    moduleType: ModuleType;
    /** Form name if it's a form module */
    formName?: string;
    /** Command name if it's a command module */
    commandName?: string;
    /** Full path from configuration root */
    relativePath: string;
    /** Russian description of metadata type */
    metadataTypeDescription: string;
    /** Russian description of module type */
    moduleTypeDescription: string;
}
/**
 * 1C Structure Analyzer class
 * Analyzes file paths to detect metadata object types and extract structural information
 */
export declare class Structure1CAnalyzer {
    /**
     * Analyzes a file path and returns structural information
     * @param filePath Path to the BSL file
     * @returns Parsed file path information
     */
    analyze(filePath: string): FilePathInfo;
    /**
     * Detects metadata type from file path
     */
    private detectMetadataType;
    /**
     * Extracts object name from file path
     */
    private extractObjectName;
    /**
     * Detects module type from file path
     */
    private detectModuleType;
    /**
     * Extracts form name from file path
     */
    private extractFormName;
    /**
     * Extracts command name from file path
     */
    private extractCommandName;
    /**
     * Builds relative path from configuration root
     */
    private buildRelativePath;
    /**
     * Gets context information for documentation
     * @param info Parsed file path information
     * @returns Context string for LLM prompts
     */
    getContextInfo(info: FilePathInfo): string;
    /**
     * Gets documentation guidance based on metadata and module type
     */
    private getDocumentationGuidance;
    private getCatalogGuidance;
    private getDocumentGuidance;
    private getDataProcessorGuidance;
    private getReportGuidance;
    private getCommonModuleGuidance;
    private getInformationRegisterGuidance;
    private getAccumulationRegisterGuidance;
    private getDefaultGuidance;
    /**
     * Checks if path belongs to 1C configuration
     * @param filePath Path to check
     * @returns true if path appears to be part of 1C configuration
     */
    isConfigurationPath(filePath: string): boolean;
    /**
     * Gets all metadata types with descriptions
     * @returns Array of metadata type entries
     */
    getAllMetadataTypes(): Array<{
        type: MetadataObjectType;
        description: string;
    }>;
}
export declare const structure1CAnalyzer: Structure1CAnalyzer;
export declare function analyze1CStructure(filePath: string): FilePathInfo;
export declare function get1CContextInfo(filePath: string): string;
