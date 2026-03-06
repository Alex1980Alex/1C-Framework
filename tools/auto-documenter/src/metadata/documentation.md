# Project Documentation

This document provides an overview of the code files in this directory, explaining their functionality and relationships.

## `event-handler-detector.ts`

This file defines the `EventHandlerDetector` class, responsible for analyzing 1C:Enterprise form module BSL code to identify and categorize event handlers.

**Key Functionality:**

*   **Event Handler Detection:** Identifies procedures that act as event handlers for forms and controls.
*   **Categorization:** Classifies detected handlers into types such as `FormEvent`, `ControlEvent`, `CommandHandler`, and `NotificationHandler`.
*   **Context Detection:** Determines the execution context (`Server`, `Client`, `ServerNoContext`) for each handler.
*   **Metadata Extraction:** Extracts handler names, parameters, export status, line numbers, and associated comments.
*   **Analysis Reporting:** Provides a structured analysis result (`IEventHandlerAnalysis`) summarizing handlers by type and context.
*   **Summary Generation:** Creates human-readable summaries and LLM context prompts from the analysis results.

**Key Types:**

*   `EventHandlerType`: Enum for handler categories.
*   `EventContext`: Enum for execution contexts.
*   `IEventHandler`: Interface for individual event handler details.
*   `IEventHandlerAnalysis`: Interface for the overall analysis result.

## `form-extended-validator.ts`

This file defines the `FormExtendedValidator` class, which extends the basic `FormValidator` to perform advanced integrity checks on 1C:Enterprise forms.

**Key Functionality:**

*   **DataPath Integrity:** Validates that all `DataPath` references in controls point to existing form attributes.
*   **Form Hierarchy Validation:** Checks for invalid nesting and circular references within the form's control hierarchy.
*   **Required Event Handler Checks:** Verifies the presence of essential event handlers based on form type and control usage.
*   **Best Practice Recommendations:** Generates recommendations for improving form quality, performance, and maintainability.
*   **Quality Scoring:** Calculates an overall quality score for the form based on various validation checks.
*   **Conditional Appearance Validation:** Analyzes conditional appearance rules for correctness and references.
*   **Command Validation:** Checks for the existence of handlers for form commands.

**Key Relationships:**

*   Inherits from `FormValidator`.
*   Utilizes `EventHandlerDetector` for analyzing BSL code.
*   Depends on `form-types.ts` for data structures.

## `form-parser.ts`

This file defines the `FormParser` class, responsible for parsing 1C:Enterprise `Form.xml` files.

**Key Functionality:**

*   **XML Parsing:** Reads and parses `Form.xml` content using `xml2js`.
*   **Structure Extraction:** Extracts the form's structure, including controls, attributes, events, commands, and conditional appearance settings.
*   **Hierarchy Traversal:** Recursively parses the control hierarchy defined in the XML.
*   **Event Binding:** Identifies event handlers linked to form-level events and control events.
*   **Data Path Linking:** Extracts `DataPath` properties to link controls with form attributes.
*   **Summary Generation:** Provides human-readable summaries and LLM context prompts of the parsed form structure.

**Key Relationships:**

*   Utilizes `form-types.ts` for defining the parsed structure.

## `form-types.ts`

This file contains TypeScript type definitions for representing the structure and validation results of 1C:Enterprise forms.

**Key Functionality:**

*   **Type Definitions:** Defines interfaces and types for form structures, controls, attributes, events, commands, and validation results.
*   **Event and Control Mapping:** Includes mappings (`EVENT_NAME_MAP`, `CONTROL_TYPE_MAP`) to translate XML names to semantic types.
*   **Validation Interfaces:** Defines interfaces for various validation issues, such as missing handlers, orphaned handlers, DataPath problems, and hierarchy issues.
*   **Extended Validation Types:** Includes types for advanced validation features like conditional appearance issues, required handlers, and best practice recommendations.

**Key Relationships:**

*   Used by `form-parser.ts`, `event-handler-detector.ts`, `form-validator.ts`, and `form-extended-validator.ts` to ensure consistent data structures.

## `form-validator.ts`

This file defines the `FormValidator` class, which orchestrates the validation process by combining `FormParser` and `EventHandlerDetector`.

**Key Functionality:**

*   **Cross-Referencing:** Compares `Form.xml` definitions with `Module.bsl` code to find inconsistencies.
*   **Missing Handler Detection:** Identifies handlers defined in `Form.xml` but not found in `Module.bsl`.
*   **Orphaned Handler Detection:** Identifies handlers present in `Module.bsl` but not referenced in `Form.xml`.
*   **Coverage Metrics:** Calculates the percentage of controls and events that have associated handlers.
*   **Validation Reporting:** Generates a human-readable report detailing validation results, errors, and warnings.
*   **Context Generation:** Creates an LLM context prompt summarizing validation findings.

**Key Relationships:**

*   Utilizes `FormParser` to parse `Form.xml`.
*   Utilizes `EventHandlerDetector` to analyze `Module.bsl`.
*   Depends on `form-types.ts` for data structures.

## `metadata-integration.ts`

This file provides functions for integrating metadata analysis with the documentation tool, specifically focusing on enriching documentation with information from 1C metadata XML files.

**Key Functionality:**

*   **Metadata XML Detection:** Functions to check for and locate metadata XML files within a directory structure.
*   **Metadata Enrichment:** Integrates parsed metadata (from `MetadataParser`) into the overall analysis results.
*   **Form Event Handler Analysis:** Analyzes form modules found in metadata to detect event handlers.
*   **Form Module Validation:** Performs extended validation on form modules using `FormExtendedValidator`.
*   **Context Prompt Generation:** Creates LLM context prompts that include metadata details, form validation status, and event handler information.
*   **Metadata Summary:** Generates concise summaries of metadata objects for aggregation.

**Key Relationships:**

*   Utilizes `MetadataParser` to parse metadata XML.
*   Utilizes `EventHandlerDetector` and `FormExtendedValidator` for form analysis.
*   Depends on `metadata-types.ts` and `form-types.ts`.

## `metadata-parser.ts`

This file defines the `MetadataParser` class, responsible for parsing 1C:Enterprise metadata XML files.

**Key Functionality:**

*   **XML Parsing:** Reads and parses metadata XML files.
*   **Metadata Object Identification:** Detects the type of metadata object (Catalog, Document, DataProcessor, CommonModule) from the XML structure.
*   **Metadata Extraction:** Parses properties, attributes, forms, commands, and modules associated with each metadata object type.
*   **Related File Discovery:** Locates associated BSL module files (manager, object, form, command modules) based on the standard 1C directory structure.
*   **Summary Generation:** Provides a human-readable summary of the parsed metadata.

**Key Relationships:**

*   Depends on `metadata-types.ts` for defining the parsed metadata structure.

## `metadata-types.ts`

This file contains TypeScript type definitions for representing the structure of 1C:Enterprise metadata objects parsed from XML files.

**Key Functionality:**

*   **Type Definitions:** Defines interfaces for various metadata objects (Catalogs, Documents, DataProcessors, CommonModules) and their components (attributes, forms, commands, modules).
*   **Metadata Structure Representation:** Accurately models the schema of 1C metadata XML files.
*   **Analysis Result Interface:** Defines the structure for the overall metadata analysis result, including the parsed metadata and related file paths.

**Key Relationships:**

*   Used by `metadata-parser.ts` and `metadata-integration.ts` to define and work with metadata structures.