/**
 * Event Handler Detection for 1C:Enterprise Forms
 *
 * Analyzes form module BSL code to detect and categorize event handlers.
 * Event handlers are procedures that respond to form and control events.
 */
/**
 * Type of event handler
 */
export type EventHandlerType = 'FormEvent' | 'ControlEvent' | 'CommandHandler' | 'NotificationHandler' | 'Unknown';
/**
 * Context where event handler runs
 */
export type EventContext = 'Server' | 'Client' | 'ServerNoContext' | 'Unknown';
/**
 * Detected event handler information
 */
export interface IEventHandler {
    /** Procedure name */
    name: string;
    /** Type of event handler */
    type: EventHandlerType;
    /** Execution context (client/server) */
    context: EventContext;
    /** Control name (for control events) */
    controlName?: string;
    /** Event type (for control events, e.g., "ПриИзменении", "Нажатие") */
    eventType?: string;
    /** Parameters */
    parameters: string[];
    /** Whether procedure is exported */
    isExported: boolean;
    /** Line number in file */
    lineNumber: number;
    /** JSDoc-style comment if present */
    comment?: string;
}
/**
 * Event handler detection result
 */
export interface IEventHandlerAnalysis {
    /** Total event handlers found */
    totalHandlers: number;
    /** Handlers by type */
    handlersByType: {
        formEvents: IEventHandler[];
        controlEvents: IEventHandler[];
        commandHandlers: IEventHandler[];
        notificationHandlers: IEventHandler[];
        unknown: IEventHandler[];
    };
    /** Handlers by context */
    handlersByContext: {
        server: IEventHandler[];
        client: IEventHandler[];
        serverNoContext: IEventHandler[];
        unknown: IEventHandler[];
    };
}
/**
 * Event Handler Detector
 */
export declare class EventHandlerDetector {
    /**
     * Analyze form module BSL file for event handlers
     * @param bslFilePath Path to form Module.bsl file
     * @returns Event handler analysis result
     */
    analyzeFormModule(bslFilePath: string): Promise<IEventHandlerAnalysis>;
    /**
     * Detect handler type and extract metadata
     */
    private detectHandlerType;
    /**
     * Categorize handlers by type and context
     */
    private categorizeHandlers;
    /**
     * Generate human-readable summary of event handlers
     */
    generateSummary(analysis: IEventHandlerAnalysis): string;
    /**
     * Generate context prompt for LLM with event handler information
     */
    generateContextPrompt(analysis: IEventHandlerAnalysis, formName?: string): string;
    /**
     * Convert context to Russian description
     */
    private contextToRussian;
}
