/**
 * Input validation and sanitization for MCP Reasoner
 * Security-focused validation for production environments
 */
import { ReasoningRequest } from './types.js';
export interface ValidationConfig {
    maxThoughtLength: number;
    maxTotalThoughts: number;
    maxBeamWidth: number;
    maxSimulations: number;
    allowedStrategies: string[];
    minThoughtNumber: number;
    allowedCharacters: RegExp;
}
export declare const DEFAULT_VALIDATION_CONFIG: ValidationConfig;
export declare class InputValidator {
    private config;
    constructor(config?: ValidationConfig);
    /**
     * Validate and sanitize a reasoning request
     */
    validateRequest(request: ReasoningRequest): ReasoningRequest;
    /**
     * Validate thought content
     */
    private validateThought;
    /**
     * Validate thought number
     */
    private validateThoughtNumber;
    /**
     * Validate total thoughts
     */
    private validateTotalThoughts;
    /**
     * Validate nextThoughtNeeded
     */
    private validateNextThoughtNeeded;
    /**
     * Validate parent ID
     */
    private validateParentId;
    /**
     * Validate strategy type
     */
    private validateStrategyType;
    /**
     * Validate beam width
     */
    private validateBeamWidth;
    /**
     * Validate number of simulations
     */
    private validateNumSimulations;
    /**
     * Check for potentially malicious content
     */
    private checkForMaliciousContent;
    /**
     * Sanitize the request by normalizing and cleaning input
     */
    private sanitizeRequest;
    /**
     * Sanitize thought content
     */
    private sanitizeThought;
    /**
     * Update validation configuration
     */
    updateConfig(newConfig: Partial<ValidationConfig>): void;
    /**
     * Get current validation configuration
     */
    getConfig(): ValidationConfig;
}
/**
 * Global validator instance
 */
export declare const validator: InputValidator;
