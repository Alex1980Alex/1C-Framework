/**
 * Prompts for inline documentation generation (JSDoc, TSDoc, BSL comments)
 */
import { ModuleType, MetadataObjectType } from '../analyzer/structure-1c-analyzer.js';
/**
 * Context-aware BSL prompts based on module type
 */
export declare const bslModulePrompts: Record<string, string>;
/**
 * Context-aware BSL prompts based on metadata object type
 */
export declare const bslMetadataPrompts: Record<string, string>;
/**
 * Prompts for JSDoc/TSDoc inline documentation
 */
export declare const inlineDocsPrompts: {
    /**
     * System prompt for generating JSDoc/TSDoc comments
     */
    jsdoc: string;
    /**
     * System prompt for generating BSL inline comments
     */
    bsl: string;
    /**
     * Prompt for updating existing documentation
     */
    update: string;
    /**
     * Prompt for class-level documentation
     */
    classDoc: string;
    /**
     * Prompt for interface documentation
     */
    interfaceDoc: string;
    /**
     * Prompt for type documentation
     */
    typeDoc: string;
};
/**
 * BSL symbol info for context-aware prompts
 */
export interface BSLSymbolInfo {
    name: string;
    isExport: boolean;
    isFunction: boolean;
    parameters: Array<{
        name: string;
        hasDefault: boolean;
    }>;
    directive?: string;
}
/**
 * Helper function to get the appropriate prompt based on file type
 * @param fileExtension File extension (.ts, .js, .bsl, etc.)
 * @param symbolType Type of symbol (function, class, interface, type)
 * @returns System prompt for inline docs generation
 */
export declare function getInlineDocsPrompt(fileExtension: string, symbolType?: 'function' | 'class' | 'interface' | 'type'): string;
/**
 * Get context-aware BSL prompt with module and metadata type information
 * @param moduleType Module type from Structure1CAnalyzer
 * @param metadataType Metadata object type from Structure1CAnalyzer
 * @param symbolInfo Optional symbol information for more context
 * @returns Enhanced BSL prompt with context
 */
export declare function getBSLContextPrompt(moduleType?: ModuleType, metadataType?: MetadataObjectType, symbolInfo?: BSLSymbolInfo): string;
/**
 * Formats code context for LLM prompt
 * @param code Source code of the function/class
 * @param filePath Path to the source file
 * @param symbolName Name of the symbol being documented
 * @returns Formatted prompt with code context
 */
export declare function formatCodeContext(code: string, filePath: string, symbolName: string): string;
