import { BSLAnalysisResult } from './bsl-treesitter-analyzer.js';
/**
 * Enhanced analysis result that includes BSL-specific information
 */
export interface EnhancedAnalysisFile {
    path: string;
    content: string;
    extension: string;
    bslAnalysis?: BSLAnalysisResult;
}
/**
 * Formats BSL analysis result as markdown for documentation
 */
export declare function formatBSLAnalysisAsMarkdown(analysis: BSLAnalysisResult, filePath: string): string;
/**
 * Creates a structured summary of BSL code for LLM analysis
 */
export declare function createBSLSummary(analysis: BSLAnalysisResult, filePath: string): string;
/**
 * Analyzes BSL file and enhances it with BSL-specific information
 */
export declare function analyzeBSLFile(filePath: string, content: string): Promise<EnhancedAnalysisFile>;
/**
 * Checks if BSL file should be included in documentation
 * BSL files with only internal procedures might be utility modules
 */
export declare function shouldDocumentBSLFile(analysis: BSLAnalysisResult): boolean;
/**
 * Extracts key information for LLM prompt
 * Returns concise summary suitable for inclusion in documentation prompt
 */
export declare function extractBSLKeyInfo(analysis: BSLAnalysisResult): {
    isPublicAPI: boolean;
    exportedMethods: string[];
    internalMethods: string[];
    regions: string[];
    complexity: 'low' | 'medium' | 'high';
};
