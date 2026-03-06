/**
 * Extended Form Validator - advanced validation and integrity analysis
 *
 * Extends basic FormValidator with:
 * - DataPath integrity validation
 * - Form hierarchy validation
 * - Required event handler checks
 * - Best practice recommendations
 * - Quality scoring
 */
import { FormValidator } from './form-validator.js';
import { IExtendedFormValidationResult } from './form-types.js';
/**
 * Extended Form Validator with advanced integrity checks
 */
export declare class FormExtendedValidator extends FormValidator {
    /**
     * Perform extended validation with all integrity checks
     */
    validateFormExtended(formXmlPath: string, moduleBslPath?: string): Promise<IExtendedFormValidationResult>;
    /**
     * Validate DataPath integrity - check that all DataPaths reference existing attributes
     */
    private validateDataPaths;
    /**
     * Validate form hierarchy - check for invalid nesting and circular references
     */
    private validateHierarchy;
    /**
     * Check for required event handlers based on form type and controls
     */
    private checkRequiredHandlers;
    /**
     * Validate form commands - check if Action handlers exist in Module.bsl
     */
    private validateCommands;
    /**
     * Validate conditional appearance - check field references and condition structure
     */
    private validateConditionalAppearance;
    /**
     * Generate best practice recommendations
     */
    private generateRecommendations;
    /**
     * Calculate overall quality score (0-100)
     */
    private calculateQualityScore;
    /**
     * Generate extended validation report
     */
    generateExtendedReport(validation: IExtendedFormValidationResult): string;
}
