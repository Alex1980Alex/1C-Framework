## Documentation Overview

This directory contains files related to generating context-aware documentation prompts for 1C:Enterprise (BSL) code. The primary goal is to provide specialized guidance for documenting different types of BSL modules and metadata objects, as well as general prompts for inline documentation generation in various languages and formats.

---

### `bsl-context-prompts.ts`

This file defines context-specific prompts for documenting various BSL module types within the 1C:Enterprise platform.

**Key Features:**

*   **`BSLModuleType` Enum:** An enumeration defining distinct types of BSL modules (e.g., `FORM`, `OBJECT`, `MANAGER`, `COMMON`).
*   **`bslContextPrompts` Object:** A collection of detailed prompts, each tailored to a specific `BSLModuleType`. These prompts outline the typical context, specific documentation considerations, and recommended comment formats for each module type.
*   **`detectBSLModuleType(filePath: string)` Function:** This utility function analyzes a given file path to determine the BSL module type. It uses pattern matching on the file path to identify the module's role within the 1C:Enterprise structure.
*   **`getBSLContextPrompt(filePath: string)` Function:** This function combines `detectBSLModuleType` with `bslContextPrompts` to retrieve the appropriate documentation prompt for a given BSL file.
*   **`getModuleTypeDescription(moduleType: BSLModuleType)` Function:** Provides a Russian description for each `BSLModuleType`.

**Relationships:**

*   This file provides the core logic for understanding BSL module types and generating relevant documentation guidance.
*   It serves as a data source for documentation generation tools that need to provide context-specific instructions to developers.

---

### `inline-docs-prompts.ts`

This file centralizes prompts and logic for generating inline documentation comments for various code types, including BSL, TypeScript, and JavaScript.

**Key Features:**

*   **`bslModulePrompts` and `bslMetadataPrompts`:** These objects provide additional context for BSL documentation based on the module type (e.g., `OBJECT_MODULE`, `MANAGER_MODULE`) and metadata object type (e.g., `CATALOG`, `DOCUMENT`). This enhances the prompts defined in `bsl-context-prompts.ts`.
*   **`inlineDocsPrompts` Object:** Contains system prompts for LLMs to generate documentation in different formats:
    *   `jsdoc`: For generating JSDoc/TSDoc comments for TypeScript/JavaScript.
    *   `bsl`: For generating inline comments for BSL code.
    *   `update`: For updating existing documentation.
    *   `classDoc`, `interfaceDoc`, `typeDoc`: Specific prompts for documenting classes, interfaces, and type aliases.
*   **`BSLSymbolInfo` Interface:** Defines a structure to hold information about a BSL symbol (function, procedure), such as its name, export status, parameters, and compilation directives.
*   **`getInlineDocsPrompt(...)` Function:** Selects the appropriate system prompt based on the file extension and the type of code symbol being documented.
*   **`getBSLContextPrompt(...)` Function:** Generates a comprehensive BSL documentation prompt by combining general BSL prompts with specific module and metadata context, and optionally symbol-specific information.
*   **`formatCodeContext(...)` Function:** A utility to format the source code and file path for inclusion in a prompt, aiding LLMs in understanding the code to be documented.

**Relationships:**

*   This file acts as a central hub for defining documentation generation strategies and prompts across different languages and contexts.
*   It leverages and extends the module type definitions from `bsl-context-prompts.ts` to provide richer BSL documentation guidance.
*   The prompts defined here are intended to be used by AI models or other tools to automate the creation of inline documentation.