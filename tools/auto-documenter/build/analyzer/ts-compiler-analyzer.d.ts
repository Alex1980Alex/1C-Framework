/**
 * TypeScript Compiler API-based code analyzer
 * Provides accurate AST-based symbol extraction replacing regex patterns
 * @module analyzer/ts-compiler-analyzer
 */
/**
 * Symbol information extracted from TypeScript AST
 */
export interface TSSymbol {
    name: string;
    type: 'function' | 'class' | 'interface' | 'type' | 'method' | 'property';
    code: string;
    lineNumber: number;
    endLineNumber: number;
    isExported: boolean;
    isAsync: boolean;
    hasJSDoc: boolean;
    parameters?: TSParameter[];
    returnType?: string;
    modifiers?: string[];
}
/**
 * Parameter information
 */
export interface TSParameter {
    name: string;
    type?: string;
    isOptional: boolean;
    hasDefault: boolean;
}
/**
 * TypeScript Compiler API-based analyzer
 * More accurate than regex for parsing TypeScript/JavaScript code
 */
export declare class TSCompilerAnalyzer {
    private sourceFile;
    private content;
    /**
     * Analyze TypeScript/JavaScript source code
     * @param content Source code content
     * @param fileName Virtual filename for parsing (determines language features)
     * @returns Array of extracted symbols
     */
    analyze(content: string, fileName?: string): TSSymbol[];
    /**
     * Get script kind based on file extension
     */
    private getScriptKind;
    /**
     * Visit AST nodes recursively
     */
    private visitNode;
    /**
     * Extract function declaration information
     */
    private extractFunctionSymbol;
    /**
     * Extract class declaration information
     */
    private extractClassSymbol;
    /**
     * Extract interface declaration information
     */
    private extractInterfaceSymbol;
    /**
     * Extract type alias declaration information
     */
    private extractTypeSymbol;
    /**
     * Extract arrow functions from variable statements
     */
    private extractArrowFunctions;
    /**
     * Extract parameter information
     */
    private extractParameters;
    /**
     * Get line numbers for a node
     */
    private getLineNumbers;
    /**
     * Get node text including leading trivia (comments)
     */
    private getNodeText;
    /**
     * Check if node has export modifier
     */
    private hasExportModifier;
    /**
     * Check if node has async modifier
     */
    private hasAsyncModifier;
    /**
     * Check if node has JSDoc comment
     */
    private hasJSDocComment;
    /**
     * Get all modifiers as strings
     */
    private getModifiers;
    /**
     * Get only exported symbols
     */
    getExportedSymbols(content: string, fileName?: string): TSSymbol[];
    /**
     * Get symbols without existing JSDoc
     */
    getUndocumentedSymbols(content: string, fileName?: string): TSSymbol[];
    /**
     * Get exported symbols without JSDoc (main use case for inline docs)
     */
    getExportedUndocumentedSymbols(content: string, fileName?: string): TSSymbol[];
}
/**
 * Singleton instance for convenience
 */
export declare const tsAnalyzer: TSCompilerAnalyzer;
/**
 * Quick analysis function
 * @param content Source code
 * @param fileName File name for language detection
 * @returns Array of symbols
 */
export declare function analyzeTypeScript(content: string, fileName?: string): TSSymbol[];
/**
 * Quick function to get only exported symbols
 */
export declare function getExportedSymbols(content: string, fileName?: string): TSSymbol[];
