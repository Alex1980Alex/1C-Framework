# Codebase Documentation

This document provides an overview of the code structure and functionality within this directory.

## `bsl-integration.ts`

This file provides utilities for analyzing and integrating with 1C:Enterprise (BSL) code. It leverages a Tree-sitter parser for accurate code analysis.

**Key Functionality:**

*   **`EnhancedAnalysisFile` Interface:** Defines a structure to hold BSL analysis results alongside file content and metadata.
*   **`formatBSLAnalysisAsMarkdown`:** Converts BSL analysis results into a human-readable Markdown format, suitable for documentation. It includes statistics, code regions, and details about exported and internal procedures/functions.
*   **`createBSLSummary`:** Generates a concise summary of BSL code analysis, optimized for large language model (LLM) prompts.
*   **`analyzeBSLFile`:** The main function for analyzing a single BSL file. It reads the file content, uses the `BSLTreesitterAnalyzer` to parse it, and returns an `EnhancedAnalysisFile` object.
*   **`shouldDocumentBSLFile`:** A helper function to determine if a BSL file warrants documentation, based on whether it exports public APIs or contains a significant amount of code.
*   **`extractBSLKeyInfo`:** Extracts key structural information from BSL analysis results (e.g., public API status, method lists, code complexity) for use in LLM prompts.

## `bsl-treesitter-analyzer.ts`

This file contains the core logic for parsing and analyzing 1C:Enterprise (BSL) code using the `web-tree-sitter` library. It provides a robust way to extract detailed information about BSL code structure.

**Key Functionality:**

*   **`BSLElementType` Enum:** Defines the types of code elements that can be identified (e.g., `PROCEDURE`, `FUNCTION`, `EXPORT`, `REGION`).
*   **`BSLCodeElement` Interface:** Represents a single identified code element with properties like type, name, line numbers, parameters, and comments.
*   **`BSLAnalysisResult` Interface:** Aggregates all the extracted `BSLCodeElement`s and statistical information (total lines, code lines, comment lines) for a given BSL file.
*   **`BSLTreesitterAnalyzer` Class:**
    *   **`initialize`:** Loads the BSL Tree-sitter grammar WASM file, preparing the parser.
    *   **`analyze`:** Parses the provided BSL code and traverses the Abstract Syntax Tree (AST) to extract procedures, functions, variables, regions, and comments. It populates a `BSLAnalysisResult` object.
    *   **`extractSignatures`:** A utility to quickly get just the names and parameters of procedures and functions.
    *   **`hasExports`:** Checks if a given BSL code snippet contains any export declarations.
*   **`getBSLAnalyzer`:** A factory function that provides a singleton instance of the `BSLTreesitterAnalyzer`, ensuring efficient reuse and proper initialization.

## `index.ts`

This file acts as the main entry point and re-exports functionality from other modules, providing a unified interface for file analysis.

**Key Functionality:**

*   **Re-exports:** Imports and re-exports key types and functions from `bsl-integration.ts` and `bsl-treesitter-analyzer.ts`, as well as `structure-1c-analyzer.ts` and `ts-compiler-analyzer.ts`.
*   **`AnalysisResult` Interface:** Defines the structure for the overall results of analyzing a directory of files, including lists of analyzed and excluded files, and any limitations encountered.
*   **`FileAnalyzer` Class:**
    *   **`analyzeFiles`:** Orchestrates the analysis of multiple files within a given directory. It filters files based on configuration, respects size and count limits, and delegates the actual analysis of BSL files to `analyzeBSLFile`.
    *   **`shouldDocument`:** Determines if a directory should be considered for documentation generation, based on the presence of code files and subdirectories.
    *   **`createUndocumentedContent`:** Generates a placeholder Markdown file (`undocumented.md`) for directories that are skipped during documentation generation, explaining the reason.
    *   **`processFile`:** Handles the reading and initial analysis of individual files, including size checks and delegation to BSL-specific analysis if applicable.

## `structure-1c-analyzer.ts`

This module is designed to analyze file paths within a 1C:Enterprise configuration structure. It identifies the type of metadata object and module based on directory and file naming conventions.

**Key Functionality:**

*   **`MetadataObjectType` Enum:** Lists all recognized types of 1C metadata objects (e.g., `CATALOG`, `DOCUMENT`, `COMMON_MODULE`).
*   **`ModuleType` Enum:** Lists the different types of modules found within 1C metadata objects (e.g., `OBJECT_MODULE`, `MANAGER_MODULE`, `FORM_MODULE`).
*   **`FilePathInfo` Interface:** A data structure holding the parsed information about a file's path, including its metadata type, object name, module type, and relative path within the configuration.
*   **`Structure1CAnalyzer` Class:**
    *   **`analyze`:** The primary method that takes a file path and returns a `FilePathInfo` object by applying various detection logic.
    *   **`detectMetadataType`:** Identifies the metadata object type based on directory names (supporting both English and Russian conventions).
    *   **`extractObjectName`:** Extracts the name of the metadata object from the path.
    *   **`detectModuleType`:** Determines the module type based on file naming patterns (e.g., `ObjectModule.bsl`, `FormModule.bsl`).
    *   **`getContextInfo`:** Generates a context string for LLM prompts, summarizing the structural information of the file and providing relevant documentation guidance.
    *   **`isConfigurationPath`:** A utility to check if a given path likely belongs to a 1C configuration.
*   **`structure1CAnalyzer` (Singleton):** An exported instance of the analyzer for convenient use.
*   **`analyze1CStructure` & `get1CContextInfo`:** Convenience functions that wrap the analyzer's core methods.

## `ts-compiler-analyzer.ts`

This file implements a code analyzer for TypeScript and JavaScript files using the official TypeScript Compiler API. This approach provides more accurate and robust parsing compared to regular expressions.

**Key Functionality:**

*   **`TSSymbol` Interface:** Defines the structure for extracted symbols, including name, type (function, class, etc.), code snippet, line numbers, export status, JSDoc presence, parameters, and return type.
*   **`TSParameter` Interface:** Represents information about a function parameter.
*   **`TSCompilerAnalyzer` Class:**
    *   **`analyze`:** Parses the provided TypeScript/JavaScript code content using `ts.createSourceFile` and traverses the resulting AST to identify and extract symbols.
    *   **`visitNode`:** A recursive function that walks the AST, identifying relevant node types (functions, classes, interfaces, type aliases, arrow functions assigned to variables).
    *   **`extractFunctionSymbol`, `extractClassSymbol`, `extractInterfaceSymbol`, `extractTypeSymbol`:** Methods responsible for extracting detailed information for each specific symbol type.
    *   **`extractArrowFunctions`:** Handles the specific case of arrow functions assigned to variables.
    *   **`getExportedSymbols`, `getUndocumentedSymbols`, `getExportedUndocumentedSymbols`:** Utility methods to filter the analyzed symbols based on export status and the presence of JSDoc comments.
*   **`tsAnalyzer` (Singleton):** An exported instance of the analyzer for convenient use.
*   **`analyzeTypeScript`, `getExportedSymbols`:** Convenience functions that wrap the analyzer's core methods.