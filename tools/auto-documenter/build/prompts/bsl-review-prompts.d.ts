/**
 * BSL Code Review Prompts with 1C Development Standards Integration
 *
 * These prompts are based on official 1C development standards (СП 1С)
 * and best practices for 1C:Enterprise platform development.
 *
 * @see https://its.1c.ru/db/v8std - Official 1C Standards
 */
/**
 * Categories of issues to check during BSL code review
 */
export declare const bslReviewCategories: {
    /**
     * Security issues specific to 1C platform
     */
    security: string[];
    /**
     * Performance issues
     */
    performance: string[];
    /**
     * Code structure and standards
     */
    standards: string[];
    /**
     * Transaction and data integrity
     */
    transactions: string[];
    /**
     * Error handling
     */
    errorHandling: string[];
    /**
     * Business logic issues
     */
    businessLogic: string[];
};
/**
 * Main BSL code review prompt with 1C standards integration
 */
export declare const bslCodeReviewPrompts: {
    /**
     * System prompt for BSL code review
     */
    systemPrompt: string;
    /**
     * Top-level prompt for project/configuration review
     */
    topLevelPrompt: string;
    /**
     * Prompt for directories with child components
     */
    withChildrenPrompt: string;
};
/**
 * Specific review rules for different module types
 */
export declare const bslModuleTypeReviewRules: {
    /**
     * Object module review rules (documents, catalogs)
     */
    objectModule: string;
    /**
     * Manager module review rules
     */
    managerModule: string;
    /**
     * Form module review rules
     */
    formModule: string;
    /**
     * Common module review rules
     */
    commonModule: string;
    /**
     * Recordset module review rules
     */
    recordsetModule: string;
};
/**
 * Anti-patterns to detect in BSL code
 */
export declare const bslAntiPatterns: {
    name: string;
    pattern: string;
    severity: string;
    recommendation: string;
}[];
/**
 * Helper function to detect if content is BSL code
 */
export declare function isBSLContent(filePath: string, content: string): boolean;
/**
 * Get module type specific review rules
 */
export declare function getModuleTypeRules(filePath: string): string;
