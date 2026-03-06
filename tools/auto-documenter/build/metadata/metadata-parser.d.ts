/**
 * 1C:Enterprise Metadata XML Parser
 *
 * Parses XML metadata files from 1C:Enterprise configurations
 * and converts them to TypeScript interfaces for documentation generation.
 */
import { IMetadataAnalysisResult } from './metadata-types.js';
/**
 * Main metadata parser class
 */
export declare class MetadataParser {
    /**
     * Parse metadata XML file
     * @param xmlFilePath Path to metadata XML file (e.g., Catalogs/Валюты.xml)
     * @returns Parsed metadata analysis result
     */
    parseMetadataFile(xmlFilePath: string): Promise<IMetadataAnalysisResult>;
    /**
     * Detect metadata type from file path structure
     */
    private detectTypeFromPath;
    /**
     * Parse generic metadata when specific type parsing is not available
     */
    private parseGenericMetadata;
    /**
     * Extract name from properties or file path
     */
    private extractName;
    /**
     * Parse Form metadata
     */
    private parseForm;
    /**
     * Parse Command metadata
     */
    private parseCommand;
    /**
     * Parse Template metadata
     */
    private parseTemplate;
    /**
     * Parse UsePurposes array
     */
    private parseUsePurposes;
    /**
     * Parse Catalog metadata
     */
    private parseCatalog;
    /**
     * Parse Document metadata
     */
    private parseDocument;
    /**
     * Parse DataProcessor metadata
     */
    private parseDataProcessor;
    /**
     * Parse CommonModule metadata
     */
    private parseCommonModule;
    /**
     * Parse multi-language string (Synonym fields)
     */
    private parseMultiLanguageString;
    /**
     * Parse generated types
     */
    private parseGeneratedTypes;
    /**
     * Parse standard attributes
     */
    private parseStandardAttributes;
    /**
     * Parse custom attributes
     */
    private parseCustomAttributes;
    /**
     * Parse attribute type
     */
    private parseAttributeType;
    /**
     * Parse tabular sections
     */
    private parseTabularSections;
    /**
     * Parse form references
     */
    private parseFormReferences;
    /**
     * Parse command references
     */
    private parseCommandReferences;
    /**
     * Find related BSL module files
     */
    private findRelatedFiles;
    /**
     * Get human-readable metadata summary
     */
    getSummary(result: IMetadataAnalysisResult): string;
}
