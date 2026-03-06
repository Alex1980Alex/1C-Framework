/**
 * Context-aware prompts for BSL (1C:Enterprise) modules
 * These prompts provide specialized guidance based on module type
 */
/**
 * BSL module types in 1C:Enterprise
 */
export declare enum BSLModuleType {
    FORM = "form",// Модуль формы
    OBJECT = "object",// Модуль объекта
    MANAGER = "manager",// Модуль менеджера
    COMMON = "common",// Общий модуль
    COMMAND = "command",// Модуль команды
    SESSION = "session",// Модуль сеанса
    APPLICATION = "application",// Модуль приложения
    EXTERNAL_CONNECTION = "external",// Модуль внешнего соединения
    MANAGED_APPLICATION = "managed",// Модуль управляемого приложения
    RECORDSET = "recordset",// Модуль набора записей
    VALUE_MANAGER = "valuemanager",// Модуль менеджера значения
    UNKNOWN = "unknown"
}
/**
 * Context-specific prompts for each BSL module type
 */
export declare const bslContextPrompts: {
    /**
     * Form module (Модуль формы)
     * Contains UI event handlers and form logic
     */
    form: string;
    /**
     * Object module (Модуль объекта)
     * Contains business logic for documents, catalogs, etc.
     */
    object: string;
    /**
     * Manager module (Модуль менеджера)
     * Contains API functions for working with metadata objects
     */
    manager: string;
    /**
     * Common module (Общий модуль)
     * Contains shared utility functions
     */
    common: string;
    /**
     * Command module (Модуль команды)
     * Contains command execution logic
     */
    command: string;
    /**
     * Session/Application modules
     * Contains system-level event handlers
     */
    session: string;
    /**
     * Application module (Модуль приложения)
     * Contains application-level event handlers
     */
    application: string;
    /**
     * External connection module (Модуль внешнего соединения)
     * Handles external connections to the infobase
     */
    external: string;
    /**
     * Managed application module (Модуль управляемого приложения)
     * Contains managed application event handlers
     */
    managed: string;
    /**
     * Record set module (Модуль набора записей)
     * Contains event handlers for register record sets
     */
    recordset: string;
    /**
     * Value manager module (Модуль менеджера значения)
     * Contains methods for value manager objects
     */
    valuemanager: string;
    /**
     * Default/Unknown module type
     */
    unknown: string;
};
/**
 * Detects BSL module type from file path
 * @param filePath Path to BSL file
 * @returns Detected module type
 */
export declare function detectBSLModuleType(filePath: string): BSLModuleType;
/**
 * Gets context-aware prompt for BSL module
 * @param filePath Path to BSL file
 * @returns Context-specific prompt for the module type
 */
export declare function getBSLContextPrompt(filePath: string): string;
/**
 * Gets module type description in Russian
 * @param moduleType BSL module type
 * @returns Russian description of module type
 */
export declare function getModuleTypeDescription(moduleType: BSLModuleType): string;
