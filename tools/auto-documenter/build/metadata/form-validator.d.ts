/**
 * Form Validation - validates consistency between Form.xml and Module.bsl
 *
 * Combines FormParser and EventHandlerDetector to:
 * - Find missing handlers (referenced in Form.xml but not in Module.bsl)
 * - Find orphaned handlers (exist in Module.bsl but not referenced in Form.xml)
 * - Calculate coverage metrics
 * - Generate validation reports
 */
import { IFormValidationResult } from './form-types.js';
/**
 * Form Validator - cross-references Form.xml with Module.bsl
 */
export declare class FormValidator {
    private formParser;
    private handlerDetector;
    constructor();
    /**
     * Validate form by analyzing both Form.xml and Module.bsl
     * @param formXmlPath Path to Form.xml file
     * @param moduleBslPath Path to Module.bsl file (optional, auto-detected if not provided)
     * @returns Validation result with coverage metrics and inconsistencies
     */
    validateForm(formXmlPath: string, moduleBslPath?: string): Promise<IFormValidationResult>;
    /**
     * Perform cross-validation between Form.xml and Module.bsl
     */
    private performValidation;
    /**
     * Generate human-readable validation report
     */
    generateValidationReport(validation: IFormValidationResult): string;
    /**
     * Generate LLM context with validation information
     */
    generateValidationContext(validation: IFormValidationResult): string;
}
