/**
 * BSL code element types
 */
export declare enum BSLElementType {
    PROCEDURE = "procedure",
    FUNCTION = "function",
    VARIABLE = "variable",
    EXPORT = "export",
    REGION = "region",
    COMMENT = "comment"
}
/**
 * Extracted BSL code element
 */
export interface BSLCodeElement {
    type: BSLElementType;
    name: string;
    startLine: number;
    endLine: number;
    parameters?: string[];
    returnType?: string;
    isExport?: boolean;
    comment?: string;
    body?: string;
}
/**
 * Result of BSL code analysis
 */
export interface BSLAnalysisResult {
    procedures: BSLCodeElement[];
    functions: BSLCodeElement[];
    variables: BSLCodeElement[];
    exports: BSLCodeElement[];
    regions: BSLCodeElement[];
    comments: BSLCodeElement[];
    totalLines: number;
    codeLines: number;
    commentLines: number;
}
/**
 * BSL Treesitter Analyzer
 * Provides 100% accurate parsing of BSL (1C:Enterprise) code using tree-sitter-bsl
 */
export declare class BSLTreesitterAnalyzer {
    private parser?;
    private initialized;
    constructor();
    /**
     * Initializes the analyzer by loading BSL language WASM
     * Must be called before using any parsing methods
     */
    initialize(): Promise<void>;
    /**
     * Ensures the analyzer is initialized before use
     */
    private ensureInitialized;
    /**
     * Analyzes BSL code and extracts all elements
     * @param code BSL source code
     * @param filePath Optional file path for context
     * @returns Detailed analysis result
     */
    analyze(code: string, filePath?: string): BSLAnalysisResult;
    /**
     * Extracts only procedure and function signatures (no bodies)
     * Useful for quick overview
     */
    extractSignatures(code: string): Array<{
        name: string;
        type: 'procedure' | 'function';
        parameters: string[];
    }>;
    /**
     * Checks if code contains export declarations
     */
    hasExports(code: string): boolean;
    /**
     * Extracts procedures from AST
     */
    private extractProcedures;
    /**
     * Extracts functions from AST
     */
    private extractFunctions;
    /**
     * Extracts variables from AST
     */
    private extractVariables;
    /**
     * Extracts regions from code (BSL preprocessing directives)
     */
    private extractRegions;
    /**
     * Extracts comments from code
     */
    private extractComments;
    /**
     * Creates a code element from AST node
     */
    private createCodeElement;
    /**
     * Extracts parameters from function/procedure declaration
     */
    private extractParameters;
    /**
     * Checks if declaration has Export keyword
     */
    private isExportDeclaration;
    /**
     * Extracts comment preceding the node
     */
    private extractPrecedingComment;
    /**
     * Calculates code statistics
     */
    private calculateStatistics;
    /**
     * Traverses AST nodes recursively
     */
    private traverseNode;
    /**
     * Finds first child node of specific type
     */
    private findChildByType;
}
/**
 * Gets or creates BSL analyzer instance
 * Automatically initializes the analyzer on first use
 */
export declare function getBSLAnalyzer(): Promise<BSLTreesitterAnalyzer>;
