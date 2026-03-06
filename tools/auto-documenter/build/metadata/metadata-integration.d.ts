/**
 * Integration module for 1C Metadata Analyzer with Documentation Tool
 *
 * This module provides functions to enrich documentation generation
 * with metadata information from XML files.
 */
import { IMetadataAnalysisResult } from './metadata-types.js';
import { AnalysisResult } from '../analyzer/index.js';
import { IEventHandlerAnalysis } from './event-handler-detector.js';
import { IExtendedFormValidationResult } from './form-types.js';
/**
 * Check if directory contains 1C metadata XML files
 * @param directoryPath Path to directory
 * @returns True if directory contains metadata XML
 */
export declare function hasMetadataXML(directoryPath: string): boolean;
/**
 * Find metadata XML file for a given directory
 * @param directoryPath Path to directory (e.g., src/Catalogs/Валюты/Ext)
 * @returns Path to metadata XML file or null
 */
export declare function findMetadataXML(directoryPath: string): string | null;
/**
 * Enrich analysis result with metadata information
 * @param directoryPath Directory being analyzed
 * @param analysisResult Current analysis result
 * @returns Metadata analysis result if available, null otherwise
 */
export declare function enrichWithMetadata(directoryPath: string, analysisResult: AnalysisResult): Promise<IMetadataAnalysisResult | null>;
/**
 * Analyze form modules for event handlers
 * @param metadataResult Metadata analysis result
 * @returns Map of form names to event handler analysis results
 */
export declare function analyzeFormEventHandlers(metadataResult: IMetadataAnalysisResult): Promise<Map<string, IEventHandlerAnalysis>>;
/**
 * Validate all form modules using FormExtendedValidator
 * @param metadataResult Metadata analysis result
 * @returns Map of form names to extended validation results
 */
export declare function validateFormModules(metadataResult: IMetadataAnalysisResult): Promise<Map<string, IExtendedFormValidationResult>>;
/**
 * Generate form validation context prompt for LLM
 * @param formValidationResults Map of form validation results
 * @returns Context prompt describing form validation status
 */
export declare function generateFormValidationPrompt(formValidationResults: Map<string, IExtendedFormValidationResult>): string;
/**
 * Generate metadata context prompt for LLM
 * @param metadataResult Metadata analysis result
 * @param formEventHandlers Optional event handler analysis for forms
 * @param formValidationResults Optional form validation results
 * @returns Context prompt describing metadata structure
 */
export declare function generateMetadataContextPrompt(metadataResult: IMetadataAnalysisResult, formEventHandlers?: Map<string, IEventHandlerAnalysis>, formValidationResults?: Map<string, IExtendedFormValidationResult>): string;
/**
 * Get metadata summary for parent directory aggregation
 * @param metadataResult Metadata analysis result
 * @returns Short metadata summary
 */
export declare function getMetadataSummary(metadataResult: IMetadataAnalysisResult): string;
