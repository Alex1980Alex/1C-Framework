/**
 * TypeScript types for 1C:Enterprise metadata structures
 *
 * These types represent the XML metadata schema used by 1C:Enterprise platform v8.3
 * for defining configuration objects (Catalogs, Documents, DataProcessors, etc.)
 */

/**
 * Base metadata object interface
 */
export interface IMetadataObject {
  uuid: string;
  name: string;
  synonym?: IMultiLanguageString;
  comment?: string;
}

/**
 * Multi-language string container (for Synonym fields)
 */
export interface IMultiLanguageString {
  items: Array<{
    lang: string;
    content: string;
  }>;
}

/**
 * 1C Generated type information
 */
export interface IGeneratedType {
  name: string;
  category: 'Object' | 'Ref' | 'Selection' | 'List' | 'Manager';
  typeId: string;
  valueId: string;
}

/**
 * Catalog metadata object
 */
export interface ICatalogMetadata extends IMetadataObject {
  type: 'Catalog';

  // Generated types
  generatedTypes: IGeneratedType[];

  // Properties
  hierarchical: boolean;
  hierarchyType: string;
  codeLength: number;
  descriptionLength: number;
  codeType: 'String' | 'Number';
  checkUnique: boolean;
  autonumbering: boolean;
  defaultPresentation: string;

  // Standard attributes
  standardAttributes: IStandardAttribute[];

  // Custom attributes
  attributes: ICustomAttribute[];

  // Forms
  forms: IFormReference[];

  // Commands
  commands: ICommandReference[];

  // Modules
  managerModule?: IModuleReference;
  objectModule?: IModuleReference;
}

/**
 * Document metadata object
 */
export interface IDocumentMetadata extends IMetadataObject {
  type: 'Document';

  // Generated types
  generatedTypes: IGeneratedType[];

  // Properties
  numberLength: number;
  numberType: 'String' | 'Number';
  checkUnique: boolean;
  autonumbering: boolean;

  // Standard attributes
  standardAttributes: IStandardAttribute[];

  // Custom attributes
  attributes: ICustomAttribute[];

  // Tabular sections
  tabularSections: ITabularSection[];

  // Forms
  forms: IFormReference[];

  // Commands
  commands: ICommandReference[];

  // Modules
  managerModule?: IModuleReference;
  objectModule?: IModuleReference;
}

/**
 * DataProcessor metadata object
 */
export interface IDataProcessorMetadata extends IMetadataObject {
  type: 'DataProcessor';

  // Generated types
  generatedTypes: IGeneratedType[];

  // Properties
  defaultForm?: string;

  // Attributes
  attributes: ICustomAttribute[];

  // Tabular sections
  tabularSections: ITabularSection[];

  // Forms
  forms: IFormReference[];

  // Commands
  commands: ICommandReference[];

  // Module
  objectModule?: IModuleReference;
}

/**
 * Standard attribute (predefined by platform)
 */
export interface IStandardAttribute {
  name: string;
  fillChecking?: 'DontCheck' | 'ShowError';
  dataHistory?: 'Use' | 'DontUse';
  fullTextSearch?: 'Use' | 'DontUse';
  multiLine?: boolean;
  format?: string;
  synonym?: IMultiLanguageString;
}

/**
 * Custom attribute (defined by developer)
 */
export interface ICustomAttribute {
  name: string;
  synonym?: IMultiLanguageString;
  comment?: string;
  type: IAttributeType;
  fillChecking?: 'DontCheck' | 'ShowError';
  fullTextSearch?: 'Use' | 'DontUse';
  minValue?: any;
  maxValue?: any;
  format?: string;
  choiceForm?: string;
  tooltip?: string;
}

/**
 * Attribute type definition
 */
export interface IAttributeType {
  types: string[]; // e.g., ["xs:string", "CatalogRef.Валюты"]
  stringQualifiers?: {
    length: number;
    allowedLength?: 'Variable' | 'Fixed';
  };
  numberQualifiers?: {
    precision: number;
    scale: number;
  };
  dateQualifiers?: {
    dateFractions: 'Date' | 'DateTime' | 'Time';
  };
}

/**
 * Tabular section (table part of document/dataprocessor)
 */
export interface ITabularSection {
  name: string;
  synonym?: IMultiLanguageString;
  comment?: string;
  standardAttributes: IStandardAttribute[];
  attributes: ICustomAttribute[];
}

/**
 * Form reference
 */
export interface IFormReference {
  name: string;
  synonym?: IMultiLanguageString;
  formType?: string;
  usePurposes?: string[];
  xmlPath?: string; // Path to Form.xml file
}

/**
 * Command reference
 */
export interface ICommandReference {
  name: string;
  synonym?: IMultiLanguageString;
  group?: string;
  commandParameterType?: string;
  modifiesData?: boolean;
  xmlPath?: string; // Path to command XML file
}

/**
 * Module reference
 */
export interface IModuleReference {
  moduleType: 'ManagerModule' | 'ObjectModule' | 'CommandModule' | 'FormModule';
  bslPath?: string; // Path to .bsl file
}

/**
 * Common module metadata
 */
export interface ICommonModuleMetadata extends IMetadataObject {
  type: 'CommonModule';

  // Properties
  global: boolean;
  clientManagedApplication: boolean;
  server: boolean;
  externalConnection: boolean;
  clientOrdinaryApplication: boolean;
  serverCall: boolean;
  privileged: boolean;
  returnValuesReuse: 'DontUse' | 'DuringRequest' | 'DuringSession';

  // Module
  module?: IModuleReference;
}

/**
 * Form metadata object
 */
export interface IFormMetadata extends IMetadataObject {
  type: 'Form';

  // Properties
  formType: 'Managed' | 'Ordinary';
  usePurposes: string[];
  includeHelpInContents?: boolean;
  extendedPresentation?: string;

  // Module
  formModule?: IModuleReference;
}

/**
 * Command metadata object
 */
export interface ICommandMetadata extends IMetadataObject {
  type: 'Command';

  // Properties
  group?: string;
  commandParameterType?: string;
  modifiesData?: boolean;
  representation?: string;

  // Module
  commandModule?: IModuleReference;
}

/**
 * Template metadata object
 */
export interface ITemplateMetadata extends IMetadataObject {
  type: 'Template';

  // Properties
  templateType?: string;
}

/**
 * Union type for all metadata objects
 */
export type MetadataObject =
  | ICatalogMetadata
  | IDocumentMetadata
  | IDataProcessorMetadata
  | ICommonModuleMetadata
  | IFormMetadata
  | ICommandMetadata
  | ITemplateMetadata;

/**
 * Metadata analysis result
 */
export interface IMetadataAnalysisResult {
  objectType: 'Catalog' | 'Document' | 'DataProcessor' | 'CommonModule' | 'Form' | 'Command' | 'Template';
  metadata: MetadataObject;
  relatedFiles: {
    xmlFile: string;
    managerModule?: string;
    objectModule?: string;
    commandModules?: string[];
    formModules?: string[];
  };
}
