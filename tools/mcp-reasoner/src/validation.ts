/**
 * Input validation and sanitization for MCP Reasoner
 * Security-focused validation for production environments
 */

import { ReasoningRequest } from './types.js';
import { ValidationError, ErrorFactory } from './errors.js';

export interface ValidationConfig {
  maxThoughtLength: number;
  maxTotalThoughts: number;
  maxBeamWidth: number;
  maxSimulations: number;
  allowedStrategies: string[];
  minThoughtNumber: number;
  allowedCharacters: RegExp;
}

export const DEFAULT_VALIDATION_CONFIG: ValidationConfig = {
  maxThoughtLength: 5000,
  maxTotalThoughts: 100,
  maxBeamWidth: 10,
  maxSimulations: 1000,
  allowedStrategies: ['beam_search', 'mcts', 'mcts-002-alpha', 'mcts-002alt-alpha', 'bsl_architecture', 'bsl_document_patterns', 'bsl_subsystem_analysis'],
  minThoughtNumber: 1,
  // Allow alphanumeric, spaces, punctuation, unicode letters/numbers
  allowedCharacters: /^[\w\s\p{L}\p{N}\p{P}\p{M}\p{S}]*$/u
};

export class InputValidator {
  private config: ValidationConfig;

  constructor(config: ValidationConfig = DEFAULT_VALIDATION_CONFIG) {
    this.config = config;
  }

  /**
   * Validate and sanitize a reasoning request
   */
  validateRequest(request: ReasoningRequest): ReasoningRequest {
    this.validateThought(request.thought);
    this.validateThoughtNumber(request.thoughtNumber);
    this.validateTotalThoughts(request.totalThoughts);
    this.validateNextThoughtNeeded(request.nextThoughtNeeded);

    if (request.parentId !== undefined) {
      this.validateParentId(request.parentId);
    }

    if (request.strategyType !== undefined) {
      this.validateStrategyType(request.strategyType);
    }

    if (request.beamWidth !== undefined) {
      this.validateBeamWidth(request.beamWidth);
    }

    if (request.numSimulations !== undefined) {
      this.validateNumSimulations(request.numSimulations);
    }

    // Return sanitized request
    return this.sanitizeRequest(request);
  }

  /**
   * Validate thought content
   */
  private validateThought(thought: string): void {
    if (typeof thought !== 'string') {
      throw ErrorFactory.invalidInput('thought', thought, 'string');
    }

    if (thought.trim().length === 0) {
      throw ErrorFactory.invalidThought(thought, 'empty or whitespace-only');
    }

    if (thought.length > this.config.maxThoughtLength) {
      throw ErrorFactory.invalidThought(
        thought,
        `exceeds maximum length of ${this.config.maxThoughtLength} characters`
      );
    }

    // Check for potentially malicious patterns
    this.checkForMaliciousContent(thought);

    // Validate character set
    if (!this.config.allowedCharacters.test(thought)) {
      throw ErrorFactory.invalidThought(thought, 'contains disallowed characters');
    }
  }

  /**
   * Validate thought number
   */
  private validateThoughtNumber(thoughtNumber: number): void {
    if (typeof thoughtNumber !== 'number' || !Number.isInteger(thoughtNumber)) {
      throw ErrorFactory.invalidInput('thoughtNumber', thoughtNumber, 'integer');
    }

    if (thoughtNumber < this.config.minThoughtNumber) {
      throw ErrorFactory.invalidInput(
        'thoughtNumber',
        thoughtNumber,
        `>= ${this.config.minThoughtNumber}`
      );
    }
  }

  /**
   * Validate total thoughts
   */
  private validateTotalThoughts(totalThoughts: number): void {
    if (typeof totalThoughts !== 'number' || !Number.isInteger(totalThoughts)) {
      throw ErrorFactory.invalidInput('totalThoughts', totalThoughts, 'integer');
    }

    if (totalThoughts < 1) {
      throw ErrorFactory.invalidInput('totalThoughts', totalThoughts, '>= 1');
    }

    if (totalThoughts > this.config.maxTotalThoughts) {
      throw ErrorFactory.invalidInput(
        'totalThoughts',
        totalThoughts,
        `<= ${this.config.maxTotalThoughts}`
      );
    }
  }

  /**
   * Validate nextThoughtNeeded
   */
  private validateNextThoughtNeeded(nextThoughtNeeded: boolean): void {
    if (typeof nextThoughtNeeded !== 'boolean') {
      throw ErrorFactory.invalidInput('nextThoughtNeeded', nextThoughtNeeded, 'boolean');
    }
  }

  /**
   * Validate parent ID
   */
  private validateParentId(parentId: string): void {
    if (typeof parentId !== 'string') {
      throw ErrorFactory.invalidInput('parentId', parentId, 'string');
    }

    if (parentId.trim().length === 0) {
      throw ErrorFactory.invalidInput('parentId', parentId, 'non-empty string');
    }

    // Validate UUID format (assuming UUIDs are used)
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(parentId)) {
      throw ErrorFactory.invalidInput('parentId', parentId, 'valid UUID format');
    }
  }

  /**
   * Validate strategy type
   */
  private validateStrategyType(strategyType: string): void {
    if (typeof strategyType !== 'string') {
      throw ErrorFactory.invalidInput('strategyType', strategyType, 'string');
    }

    if (!this.config.allowedStrategies.includes(strategyType)) {
      throw ErrorFactory.invalidStrategy(strategyType, this.config.allowedStrategies);
    }
  }

  /**
   * Validate beam width
   */
  private validateBeamWidth(beamWidth: number): void {
    if (typeof beamWidth !== 'number' || !Number.isInteger(beamWidth)) {
      throw ErrorFactory.invalidInput('beamWidth', beamWidth, 'integer');
    }

    if (beamWidth < 1) {
      throw ErrorFactory.invalidInput('beamWidth', beamWidth, '>= 1');
    }

    if (beamWidth > this.config.maxBeamWidth) {
      throw ErrorFactory.invalidInput(
        'beamWidth',
        beamWidth,
        `<= ${this.config.maxBeamWidth}`
      );
    }
  }

  /**
   * Validate number of simulations
   */
  private validateNumSimulations(numSimulations: number): void {
    if (typeof numSimulations !== 'number' || !Number.isInteger(numSimulations)) {
      throw ErrorFactory.invalidInput('numSimulations', numSimulations, 'integer');
    }

    if (numSimulations < 1) {
      throw ErrorFactory.invalidInput('numSimulations', numSimulations, '>= 1');
    }

    if (numSimulations > this.config.maxSimulations) {
      throw ErrorFactory.invalidInput(
        'numSimulations',
        numSimulations,
        `<= ${this.config.maxSimulations}`
      );
    }
  }

  /**
   * Check for potentially malicious content
   */
  private checkForMaliciousContent(thought: string): void {
    // Check for script injection patterns
    const scriptPatterns = [
      /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
      /javascript:/gi,
      /vbscript:/gi,
      /onload\s*=/gi,
      /onerror\s*=/gi,
      /onclick\s*=/gi,
      /eval\s*\(/gi,
      /document\.write/gi,
      /innerHTML/gi
    ];

    for (const pattern of scriptPatterns) {
      if (pattern.test(thought)) {
        throw ErrorFactory.invalidThought(thought, 'contains potentially malicious script content');
      }
    }

    // Check for SQL injection patterns
    const sqlPatterns = [
      /('\s*(or|and)\s*'|\'\s*or\s*\'\s*=\s*\')/gi,
      /(union\s+select|select\s+.*\s+from)/gi,
      /(drop\s+table|delete\s+from|insert\s+into|update\s+.*\s+set)/gi,
      /(-{2}|\/\*|\*\/)/gi
    ];

    for (const pattern of sqlPatterns) {
      if (pattern.test(thought)) {
        throw ErrorFactory.invalidThought(thought, 'contains potentially malicious SQL content');
      }
    }

    // Check for command injection patterns
    const commandPatterns = [
      /(\|\||&&|;|\|)/g,
      /(rm\s+-rf|del\s+\/|format\s+c:)/gi,
      /(wget|curl|nc|telnet)\s+/gi
    ];

    for (const pattern of commandPatterns) {
      if (pattern.test(thought)) {
        throw ErrorFactory.invalidThought(thought, 'contains potentially malicious command content');
      }
    }
  }

  /**
   * Sanitize the request by normalizing and cleaning input
   */
  private sanitizeRequest(request: ReasoningRequest): ReasoningRequest {
    const sanitized: ReasoningRequest = {
      thought: this.sanitizeThought(request.thought),
      thoughtNumber: request.thoughtNumber,
      totalThoughts: request.totalThoughts,
      nextThoughtNeeded: request.nextThoughtNeeded
    };

    // Copy optional fields if present
    if (request.parentId !== undefined) {
      sanitized.parentId = request.parentId.trim();
    }

    if (request.strategyType !== undefined) {
      sanitized.strategyType = request.strategyType.toLowerCase().trim();
    }

    if (request.beamWidth !== undefined) {
      sanitized.beamWidth = request.beamWidth;
    }

    if (request.numSimulations !== undefined) {
      sanitized.numSimulations = request.numSimulations;
    }

    return sanitized;
  }

  /**
   * Sanitize thought content
   */
  private sanitizeThought(thought: string): string {
    return thought
      .trim()
      .replace(/\s+/g, ' ') // Normalize whitespace
      .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '') // Remove control characters
      .substring(0, this.config.maxThoughtLength); // Ensure length limit
  }

  /**
   * Update validation configuration
   */
  updateConfig(newConfig: Partial<ValidationConfig>): void {
    this.config = { ...this.config, ...newConfig };
  }

  /**
   * Get current validation configuration
   */
  getConfig(): ValidationConfig {
    return { ...this.config };
  }
}

/**
 * Global validator instance
 */
export const validator = new InputValidator();