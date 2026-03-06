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
 * Event name mapping from 1C XML names to semantic types
 */
export const EVENT_NAME_MAP = {
    // Form-level
    'OnCreateAtServer': 'OnCreateAtServer',
    'OnOpen': 'OnOpen',
    'BeforeClose': 'BeforeClose',
    'OnClose': 'OnClose',
    'NotificationProcessing': 'NotificationProcessing',
    // Control-level
    'OnChange': 'OnChange',
    'StartChoice': 'StartChoice',
    'Click': 'Click',
    'EditTextChange': 'EditTextChange',
    'AutoPick': 'AutoPick',
    'ChoiceProcessing': 'ChoiceProcessing',
    // Table events
    'OnActivateRow': 'OnActivateRow',
    'OnRowOutput': 'OnRowOutput',
    'OnGetDataAtServer': 'OnGetDataAtServer',
    'BeforeAddRow': 'BeforeAddRow',
    'BeforeDeleteRow': 'BeforeDeleteRow',
    'BeforeRowChange': 'BeforeRowChange',
    'OnStartEdit': 'OnStartEdit',
    'OnEditEnd': 'OnEditEnd'
};
/**
 * Control type mapping from XML element names
 */
export const CONTROL_TYPE_MAP = {
    'InputField': 'InputField',
    'Button': 'Button',
    'Label': 'Label',
    'LabelDecoration': 'LabelDecoration',
    'CheckBoxField': 'CheckBox',
    'RadioButtonField': 'RadioButton',
    'Table': 'Table',
    'UsualGroup': 'UsualGroup',
    'CommandBarButton': 'CommandBarButton',
    'CommandBar': 'CommandBarButton', // Альтернативное имя
    'Popup': 'Popup'
};
//# sourceMappingURL=form-types.js.map