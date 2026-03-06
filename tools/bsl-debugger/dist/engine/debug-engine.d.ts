/**
 * Debug Engine — Ядро отладчика BSL
 *
 * Управляет процессом отладки:
 * - Breakpoints
 * - Stepping (step in/over/out)
 * - Стек вызовов
 * - Переменные
 * - Состояние выполнения
 */
import * as AST from "../parser/ast.js";
import { EventEmitter } from "events";
export type DebugState = "idle" | "running" | "paused" | "terminated";
export type StopReason = "breakpoint" | "step" | "exception" | "pause" | "entry";
export interface Breakpoint {
    id: number;
    file: string;
    line: number;
    condition?: string;
    hitCondition?: string;
    logMessage?: string;
    hitCount: number;
    verified: boolean;
    enabled: boolean;
}
export interface StackFrame {
    id: number;
    name: string;
    file: string;
    line: number;
    column: number;
    scopes: Scope[];
}
export interface Scope {
    name: string;
    type: "local" | "global" | "closure" | "module";
    variablesReference: number;
}
export interface Variable {
    name: string;
    value: string;
    type: string;
    variablesReference: number;
    evaluateName?: string;
}
export interface ExecutionContext {
    file: string;
    line: number;
    column: number;
    functionName?: string;
    ast?: AST.Module;
    currentNode?: AST.ASTNode;
}
export interface DebugEvents {
    "stopped": (reason: StopReason, context: ExecutionContext) => void;
    "continued": () => void;
    "terminated": (exitCode: number) => void;
    "output": (category: "stdout" | "stderr" | "console", text: string) => void;
    "breakpoint": (breakpoint: Breakpoint, reason: "new" | "changed" | "removed") => void;
}
export declare class DebugEngine extends EventEmitter {
    private state;
    private breakpoints;
    private breakpointIdCounter;
    private callStack;
    private frameIdCounter;
    private variables;
    private variablesRefCounter;
    private moduleCache;
    private currentContext;
    private stepMode;
    private stepTargetDepth;
    getState(): DebugState;
    getCurrentContext(): ExecutionContext | null;
    setBreakpoints(file: string, breakpoints: Partial<Breakpoint>[]): Breakpoint[];
    getBreakpoints(file?: string): Breakpoint[];
    removeBreakpoint(id: number): boolean;
    private verifyBreakpoint;
    private findNearestBreakpointLine;
    private findBreakpointCandidates;
    launch(file: string, args?: string[], stopOnEntry?: boolean): Promise<void>;
    continue(): Promise<void>;
    stepOver(): Promise<void>;
    stepIn(): Promise<void>;
    stepOut(): Promise<void>;
    pause(reason?: StopReason): Promise<void>;
    terminate(): Promise<void>;
    getCallStack(): StackFrame[];
    private pushFrame;
    private popFrame;
    private createScopes;
    getVariables(reference: number): Variable[];
    setVariables(reference: number, variables: Variable[]): void;
    evaluate(expression: string, frameId?: number): Promise<Variable>;
    private getOrParseModule;
    parseSource(file: string, source: string): AST.Module | null;
    private runUntilBreakpoint;
    private executeNextStatement;
    private runUntilDepth;
    private shouldStop;
    private checkBreakpoint;
    private findFirstExecutableLine;
    private cleanup;
}
export declare function createDebugEngine(): DebugEngine;
//# sourceMappingURL=debug-engine.d.ts.map