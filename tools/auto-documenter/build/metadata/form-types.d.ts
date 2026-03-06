/**
 * TypeScript type definitions for 1C:Enterprise Form.xml structure
 *
 * Represents the parsed structure of Form.xml files including:
 * - Form attributes and properties
 * - Control hierarchy (groups, input fields, buttons, tables)
 * - Event bindings between controls and BSL handlers
 * - Data paths linking controls to object attributes
 */
/**
 * Type of form control element
 */
export type FormControlType = 'InputField' | 'Button' | 'Label' | 'LabelDecoration' | 'CheckBox' | 'RadioButton' | 'RadioButtonField' | 'Table' | 'UsualGroup' | 'CommandBarButton' | 'Popup' | 'Unknown';
/**
 * Form event type (mapped from 1C event names to semantic types)
 */
export type FormEventType = 'OnCreateAtServer' | 'OnOpen' | 'BeforeClose' | 'OnClose' | 'NotificationProcessing' | 'OnChange' | 'StartChoice' | 'Click' | 'EditTextChange' | 'AutoPick' | 'ChoiceProcessing' | 'OnActivateRow' | 'OnRowOutput' | 'OnGetDataAtServer' | 'BeforeAddRow' | 'BeforeDeleteRow' | 'BeforeRowChange' | 'OnStartEdit' | 'OnEditEnd' | 'Unknown';
/**
 * Event binding between form control and BSL handler
 */
export interface IFormEvent {
    /** 1C event name from XML (e.g., "OnChange", "OnCreateAtServer") */
    xmlEventName: string;
    /** Semantic event type */
    eventType: FormEventType;
    /** BSL handler procedure name (e.g., "КодПриИзменении") */
    handlerName: string;
    /** Whether handler procedure exists in Module.bsl */
    handlerExists?: boolean;
}
/**
 * Localized title (from Synonym fields)
 */
export interface ILocalizedTitle {
    lang: string;
    content: string;
}
/**
 * Form control element
 */
export interface IFormControl {
    /** Control ID from Form.xml */
    id: string;
    /** Control name (identifier) */
    name: string;
    /** Control type */
    type: FormControlType;
    /** Data path (e.g., "Объект.Код", "Объект.Товары.Количество") */
    dataPath?: string;
    /** Title/caption */
    title?: ILocalizedTitle[];
    /** Event handlers bound to this control */
    events: IFormEvent[];
    /** Parent control/group name (for hierarchy) */
    parent?: string;
    /** Child controls (for groups, tables) */
    children?: IFormControl[];
    /** Width setting */
    width?: number;
    /** Whether control stretches horizontally */
    horizontalStretch?: boolean;
    /** Whether control is read-only */
    readOnly?: boolean;
    /** For tables: column definitions */
    columns?: IFormTableColumn[];
}
/**
 * Table column definition
 */
export interface IFormTableColumn {
    /** Column name */
    name: string;
    /** Data path within table row */
    dataPath: string;
    /** Column title */
    title?: ILocalizedTitle[];
    /** Width */
    width?: number;
}
/**
 * Form attribute (реквизит формы)
 */
export interface IFormAttribute {
    /** Attribute name */
    name: string;
    /** Data type (e.g., "String", "Number", "CatalogRef.Контрагенты") */
    type?: string;
    /** Whether it's a table attribute */
    isTable?: boolean;
    /** For tables: nested attributes */
    tableAttributes?: IFormAttribute[];
}
/**
 * Form command (команда формы)
 */
export interface IFormCommand {
    /** Command name (identifier) */
    name: string;
    /** Command ID */
    id: string;
    /** Title/caption */
    title?: ILocalizedTitle[];
    /** Tooltip */
    toolTip?: ILocalizedTitle[];
    /** Action - handler procedure name */
    action?: string;
    /** Whether handler exists in Module.bsl */
    handlerExists?: boolean;
    /** Keyboard shortcut */
    shortcut?: string;
    /** Picture/icon */
    picture?: string;
    /** Representation (Auto, Picture, Text, PictureAndText) */
    representation?: string;
}
/**
 * Conditional appearance condition (условие оформления)
 */
export interface IConditionalAppearanceCondition {
    /** Left operand (usually DataPath) */
    left: string;
    /** Comparison type (Equal, NotEqual, Greater, Less, etc.) */
    comparisonType: string;
    /** Right operand (value or DataPath) */
    right?: string;
    /** Data path type indicator */
    rightIsDataPath?: boolean;
}
/**
 * Conditional appearance item (элемент условного оформления)
 */
export interface IConditionalAppearanceItem {
    /** Item ID */
    id: string;
    /** Event type (OnActivateRow, etc.) */
    eventName?: string;
    /** Target fields - controls affected by appearance */
    fields: string[];
    /** Appearance properties to apply (e.g., TextColor, BackColor, Font) */
    appearance: IConditionalAppearanceProperties;
    /** Conditions that trigger this appearance */
    conditions: IConditionalAppearanceCondition[];
    /** Whether conditions are properly structured */
    isValid?: boolean;
    /** Validation issues */
    issues?: string[];
}
/**
 * Conditional appearance properties
 */
export interface IConditionalAppearanceProperties {
    /** Text color */
    textColor?: string;
    /** Background color */
    backColor?: string;
    /** Font properties */
    font?: string;
    /** Enabled state */
    enabled?: boolean;
    /** Visible state */
    visible?: boolean;
    /** Read-only state */
    readOnly?: boolean;
}
/**
 * Complete form structure parsed from Form.xml
 */
export interface IFormStructure {
    /** Form name (extracted from file path) */
    formName: string;
    /** Path to Form.xml file */
    xmlFilePath: string;
    /** Form-level events */
    formEvents: IFormEvent[];
    /** Form attributes (реквизиты) */
    attributes: IFormAttribute[];
    /** All controls (flat list) */
    controls: IFormControl[];
    /** Root-level controls (top of hierarchy) */
    rootControls: IFormControl[];
    /** All event bindings (form + controls) */
    allEvents: IFormEvent[];
    /** Form commands (команды формы) */
    commands: IFormCommand[];
    /** Conditional appearance items (условное оформление) */
    conditionalAppearance: IConditionalAppearanceItem[];
}
/**
 * Form validation result - checks integrity between Form.xml and Module.bsl
 */
export interface IFormValidationResult {
    /** Form structure being validated */
    formStructure: IFormStructure;
    /** Total controls count */
    totalControls: number;
    /** Controls with event handlers */
    controlsWithHandlers: number;
    /** Total events defined in Form.xml */
    totalEvents: number;
    /** Events with existing handlers in Module.bsl */
    eventsWithHandlers: number;
    /** Missing handlers (defined in Form.xml but not in Module.bsl) */
    missingHandlers: IMissingHandler[];
    /** Orphaned handlers (exist in Module.bsl but not referenced in Form.xml) */
    orphanedHandlers: IOrphanedHandler[];
    /** Controls without any events */
    unusedControls: IFormControl[];
    /** Coverage metrics */
    coverage: {
        controlCoverage: number;
        eventCoverage: number;
    };
    /** Overall validation status */
    isValid: boolean;
    /** Validation errors */
    errors: string[];
    /** Validation warnings */
    warnings: string[];
}
/**
 * Missing handler (referenced in Form.xml but not found in Module.bsl)
 */
export interface IMissingHandler {
    /** Control name that references the handler */
    controlName: string;
    /** Control type */
    controlType: FormControlType;
    /** Event type */
    eventType: FormEventType;
    /** Expected handler procedure name */
    handlerName: string;
    /** Control data path (if any) */
    dataPath?: string;
}
/**
 * Orphaned handler (exists in Module.bsl but not referenced in Form.xml)
 */
export interface IOrphanedHandler {
    /** Handler procedure name from Module.bsl */
    handlerName: string;
    /** Detected handler type from EventHandlerDetector */
    handlerType: string;
    /** Control name (guessed from procedure name) */
    guessedControlName?: string;
    /** Event type (guessed from procedure name suffix) */
    guessedEventType?: string;
    /** Line number in Module.bsl */
    lineNumber: number;
    /** Whether it's exported */
    isExported: boolean;
}
/**
 * Missing command handler
 */
export interface IMissingCommandHandler {
    /** Command name */
    commandName: string;
    /** Expected handler procedure name from <Action> */
    handlerName: string;
    /** Command title */
    title?: string;
}
/**
 * Orphaned command handler (procedure exists but no command references it)
 */
export interface IOrphanedCommandHandler {
    /** Handler procedure name */
    handlerName: string;
    /** Line number in Module.bsl */
    lineNumber: number;
    /** Whether it's exported */
    isExported: boolean;
}
/**
 * Conditional appearance validation issue
 */
export interface IConditionalAppearanceIssue {
    /** Item ID with issue */
    itemId: string;
    /** Issue type */
    issueType: 'invalid_field' | 'invalid_datapath' | 'missing_condition' | 'invalid_condition';
    /** Description */
    description: string;
    /** Affected field names */
    affectedFields?: string[];
    /** Suggestion for fix */
    suggestion?: string;
}
/**
 * Event name mapping from 1C XML names to semantic types
 */
export declare const EVENT_NAME_MAP: Record<string, FormEventType>;
/**
 * Control type mapping from XML element names
 */
export declare const CONTROL_TYPE_MAP: Record<string, FormControlType>;
/**
 * Extended validation - DataPath integrity issues
 */
export interface IDataPathIssue {
    /** Control with invalid DataPath */
    controlName: string;
    /** Control type */
    controlType: FormControlType;
    /** Invalid DataPath */
    dataPath: string;
    /** Issue type */
    issueType: 'missing_attribute' | 'invalid_format' | 'missing_table_attribute';
    /** Expected attribute name */
    expectedAttribute?: string;
    /** Suggestion for fix */
    suggestion?: string;
}
/**
 * Extended validation - Form hierarchy issues
 */
export interface IHierarchyIssue {
    /** Control with hierarchy issue */
    controlName: string;
    /** Control type */
    controlType: FormControlType;
    /** Parent control name */
    parentName?: string;
    /** Issue type */
    issueType: 'invalid_nesting' | 'orphaned_control' | 'circular_reference';
    /** Description */
    description: string;
}
/**
 * Extended validation - Required event handlers
 */
export interface IRequiredHandlerIssue {
    /** Event type that should be present */
    eventType: FormEventType;
    /** Why this handler is recommended */
    reason: string;
    /** Severity level */
    severity: 'critical' | 'warning' | 'info';
    /** Suggested handler name */
    suggestedHandlerName?: string;
}
/**
 * Extended validation - Form best practices
 */
export interface IBestPracticeRecommendation {
    /** Category */
    category: 'performance' | 'usability' | 'maintainability' | 'security';
    /** Recommendation title */
    title: string;
    /** Detailed description */
    description: string;
    /** Affected controls or events */
    affectedItems?: string[];
    /** Priority */
    priority: 'high' | 'medium' | 'low';
}
/**
 * Extended form validation result
 */
export interface IExtendedFormValidationResult extends IFormValidationResult {
    /** DataPath integrity issues */
    dataPathIssues: IDataPathIssue[];
    /** Hierarchy issues */
    hierarchyIssues: IHierarchyIssue[];
    /** Missing required handlers */
    requiredHandlerIssues: IRequiredHandlerIssue[];
    /** Best practice recommendations */
    recommendations: IBestPracticeRecommendation[];
    /** Overall quality score (0-100) */
    qualityScore: number;
    /** Total commands count */
    totalCommands: number;
    /** Commands with handlers */
    commandsWithHandlers: number;
    /** Missing command handlers */
    missingCommandHandlers: IMissingCommandHandler[];
    /** Orphaned command handlers */
    orphanedCommandHandlers: IOrphanedCommandHandler[];
    /** Total conditional appearance items */
    totalConditionalAppearance: number;
    /** Conditional appearance issues */
    conditionalAppearanceIssues: IConditionalAppearanceIssue[];
}
