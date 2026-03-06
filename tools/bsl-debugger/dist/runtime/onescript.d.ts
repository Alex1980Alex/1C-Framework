/**
 * OneScript Runtime Backend
 *
 * Интеграция с OneScript для реального выполнения BSL-кода.
 * Поддерживает несколько режимов:
 * 1. CLI — запуск через oscript.exe
 * 2. Инструментированный — с инъекцией отладочного кода
 * 3. HTTP Debug — через HTTP API OneScript.Web
 */
import { EventEmitter } from "events";
export interface RuntimeConfig {
    oscriptPath?: string;
    workingDir?: string;
    env?: Record<string, string>;
    encoding?: string;
    timeout?: number;
}
export interface ExecutionResult {
    success: boolean;
    output: string;
    errors: string;
    exitCode: number;
    duration: number;
}
export interface RuntimeVariable {
    name: string;
    value: any;
    type: string;
    stringValue: string;
}
export interface RuntimeStackFrame {
    functionName: string;
    file: string;
    line: number;
    locals: RuntimeVariable[];
}
export interface IRuntime {
    execute(code: string, args?: string[]): Promise<ExecutionResult>;
    executeFile(file: string, args?: string[]): Promise<ExecutionResult>;
    getVariables(): Promise<RuntimeVariable[]>;
    evaluate(expression: string): Promise<RuntimeVariable>;
    dispose(): void;
}
export declare class OneScriptCLI extends EventEmitter implements IRuntime {
    private config;
    private process;
    constructor(config?: RuntimeConfig);
    private findOscript;
    execute(code: string, args?: string[]): Promise<ExecutionResult>;
    executeFile(file: string, args?: string[]): Promise<ExecutionResult>;
    getVariables(): Promise<RuntimeVariable[]>;
    evaluate(expression: string): Promise<RuntimeVariable>;
    dispose(): void;
}
/**
 * Инструментированный runtime — инъектирует отладочный код
 * в исходники для трассировки выполнения.
 */
export declare class InstrumentedRuntime extends EventEmitter implements IRuntime {
    private cli;
    private debugPort;
    private debugServer;
    private debugSocket;
    private currentVariables;
    private currentStack;
    constructor(config?: RuntimeConfig);
    execute(code: string, args?: string[]): Promise<ExecutionResult>;
    executeFile(file: string, args?: string[]): Promise<ExecutionResult>;
    private instrumentCode;
    private isExecutableLine;
    private startDebugServer;
    private stopDebugServer;
    private handleDebugMessage;
    getVariables(): Promise<RuntimeVariable[]>;
    evaluate(expression: string): Promise<RuntimeVariable>;
    dispose(): void;
}
export declare class HTTPDebugRuntime extends EventEmitter implements IRuntime {
    private baseUrl;
    constructor(baseUrl?: string);
    execute(code: string, args?: string[]): Promise<ExecutionResult>;
    executeFile(file: string, args?: string[]): Promise<ExecutionResult>;
    getVariables(): Promise<RuntimeVariable[]>;
    evaluate(expression: string): Promise<RuntimeVariable>;
    dispose(): void;
}
export type RuntimeType = "cli" | "instrumented" | "http";
export declare function createRuntime(type: RuntimeType, config?: RuntimeConfig | string): IRuntime;
export declare function serializeBSLValue(value: any): string;
export declare function deserializeBSLValue(str: string, type: string): any;
//# sourceMappingURL=onescript.d.ts.map