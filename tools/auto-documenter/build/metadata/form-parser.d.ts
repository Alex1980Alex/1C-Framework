/**
 * Form.xml Parser for 1C:Enterprise Forms
 *
 * Parses Form.xml files to extract:
 * - Form structure and hierarchy
 * - Control definitions (input fields, buttons, tables)
 * - Event bindings between controls and BSL handlers
 * - Data paths linking controls to object attributes
 */
import { IFormStructure } from './form-types.js';
/**
 * Form Parser - parses 1C Form.xml files
 */
export declare class FormParser {
    /**
     * Parse Form.xml file
     * @param xmlFilePath Path to Form.xml file
     * @returns Parsed form structure
     */
    parseFormXML(xmlFilePath: string): Promise<IFormStructure>;
    /**
     * Parse form-level events from <Events> section
     */
    private parseFormEvents;
    /**
     * Parse form attributes (реквизиты)
     */
    private parseFormAttributes;
    /**
     * Parse child items (controls) recursively
     */
    private parseChildItems;
    /**
     * Parse individual control element
     */
    private parseControl;
    /**
     * Parse control events from <Events> section
     */
    private parseControlEvents;
    /**
     * Parse title from <Title> section
     */
    private parseTitle;
    /**
     * Extract type string from Type node
     */
    private extractTypeFromNode;
    /**
     * Generate human-readable summary of form structure
     */
    generateSummary(formStructure: IFormStructure): string;
    /**
     * Generate LLM context prompt with form structure
     */
    generateContextPrompt(formStructure: IFormStructure): string;
    /**
     * Build control information for prompt (recursive)
     */
    private buildControlPrompt;
    /**
     * Parse form commands from <Commands> section
     */
    private parseFormCommands;
    /**
     * Parse ToolTip from <ToolTip> section (similar to Title)
     */
    private parseToolTip;
    /**
     * Parse conditional appearance from <ConditionalAppearance> section
     */
    private parseConditionalAppearance;
    /**
     * Parse appearance properties (Appearance section)
     */
    private parseAppearanceProperties;
    /**
     * Parse appearance conditions (Filter section)
     */
    private parseAppearanceConditions;
}
