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
import { parse } from "../parser/parser.js";
import { EventEmitter } from "events";
// === Debug Engine ===
export class DebugEngine extends EventEmitter {
    state = "idle";
    breakpoints = new Map(); // file -> breakpoints
    breakpointIdCounter = 1;
    callStack = [];
    frameIdCounter = 1;
    variables = new Map(); // variablesReference -> variables
    variablesRefCounter = 1;
    moduleCache = new Map(); // file -> AST
    currentContext = null;
    stepMode = "none";
    stepTargetDepth = 0;
    // === State Management ===
    getState() {
        return this.state;
    }
    getCurrentContext() {
        return this.currentContext;
    }
    // === Breakpoint Management ===
    setBreakpoints(file, breakpoints) {
        const result = [];
        const ast = this.getOrParseModule(file);
        for (const bp of breakpoints) {
            const breakpoint = {
                id: this.breakpointIdCounter++,
                file,
                line: bp.line || 1,
                condition: bp.condition,
                hitCondition: bp.hitCondition,
                logMessage: bp.logMessage,
                hitCount: 0,
                verified: false,
                enabled: true
            };
            // Верификация: проверяем, что на этой строке есть код
            if (ast) {
                breakpoint.verified = this.verifyBreakpoint(ast, breakpoint.line);
                // Корректируем строку если нужно
                if (!breakpoint.verified) {
                    const adjustedLine = this.findNearestBreakpointLine(ast, breakpoint.line);
                    if (adjustedLine) {
                        breakpoint.line = adjustedLine;
                        breakpoint.verified = true;
                    }
                }
            }
            result.push(breakpoint);
            this.emit("breakpoint", breakpoint, "new");
        }
        this.breakpoints.set(file, result);
        return result;
    }
    getBreakpoints(file) {
        if (file) {
            return this.breakpoints.get(file) || [];
        }
        const all = [];
        for (const bps of this.breakpoints.values()) {
            all.push(...bps);
        }
        return all;
    }
    removeBreakpoint(id) {
        for (const [file, bps] of this.breakpoints) {
            const index = bps.findIndex(bp => bp.id === id);
            if (index !== -1) {
                const [removed] = bps.splice(index, 1);
                this.emit("breakpoint", removed, "removed");
                return true;
            }
        }
        return false;
    }
    verifyBreakpoint(ast, line) {
        // Проверяем есть ли исполняемый код на этой строке
        const candidates = this.findBreakpointCandidates(ast);
        return candidates.includes(line);
    }
    findNearestBreakpointLine(ast, targetLine) {
        const candidates = this.findBreakpointCandidates(ast);
        if (candidates.length === 0)
            return null;
        // Ищем ближайшую строку >= targetLine
        for (const line of candidates.sort((a, b) => a - b)) {
            if (line >= targetLine)
                return line;
        }
        return null;
    }
    findBreakpointCandidates(ast) {
        const lines = new Set();
        const collectLines = (nodes) => {
            for (const node of nodes) {
                // Добавляем строку начала statement'а
                lines.add(node.location.start.line);
                // Рекурсивно обрабатываем вложенные блоки
                if (node.type === "IfStatement") {
                    collectLines(node.thenBranch);
                    for (const elseIf of node.elseIfBranches) {
                        collectLines(elseIf.body);
                    }
                    if (node.elseBranch)
                        collectLines(node.elseBranch);
                }
                else if (node.type === "ForStatement" || node.type === "ForEachStatement" || node.type === "WhileStatement") {
                    collectLines(node.body);
                }
                else if (node.type === "TryStatement") {
                    collectLines(node.tryBlock);
                    collectLines(node.exceptBlock);
                }
            }
        };
        // Собираем строки из всех процедур/функций
        for (const proc of ast.procedures) {
            lines.add(proc.location.start.line);
            collectLines(proc.body);
        }
        for (const func of ast.functions) {
            lines.add(func.location.start.line);
            collectLines(func.body);
        }
        // И из кода модуля
        collectLines(ast.statements);
        return Array.from(lines);
    }
    // === Execution Control ===
    async launch(file, args = [], stopOnEntry = true) {
        this.state = "running";
        // Парсим модуль
        const ast = this.getOrParseModule(file);
        if (!ast) {
            throw new Error(`Failed to parse ${file}`);
        }
        this.currentContext = {
            file,
            line: 1,
            column: 1,
            ast
        };
        if (stopOnEntry) {
            // Находим первую строку с кодом
            const firstLine = this.findFirstExecutableLine(ast);
            this.currentContext.line = firstLine;
            await this.pause("entry");
        }
    }
    async continue() {
        if (this.state !== "paused")
            return;
        this.state = "running";
        this.stepMode = "none";
        this.emit("continued");
        // Продолжаем выполнение до следующего breakpoint
        await this.runUntilBreakpoint();
    }
    async stepOver() {
        if (this.state !== "paused")
            return;
        this.stepMode = "over";
        this.stepTargetDepth = this.callStack.length;
        this.state = "running";
        this.emit("continued");
        await this.executeNextStatement();
    }
    async stepIn() {
        if (this.state !== "paused")
            return;
        this.stepMode = "in";
        this.state = "running";
        this.emit("continued");
        await this.executeNextStatement();
    }
    async stepOut() {
        if (this.state !== "paused")
            return;
        this.stepMode = "out";
        this.stepTargetDepth = this.callStack.length - 1;
        this.state = "running";
        this.emit("continued");
        await this.runUntilDepth(this.stepTargetDepth);
    }
    async pause(reason = "pause") {
        this.state = "paused";
        if (this.currentContext) {
            this.emit("stopped", reason, this.currentContext);
        }
    }
    async terminate() {
        this.state = "terminated";
        this.emit("terminated", 0);
        this.cleanup();
    }
    // === Call Stack ===
    getCallStack() {
        return [...this.callStack];
    }
    pushFrame(name, file, line, column) {
        const frame = {
            id: this.frameIdCounter++,
            name,
            file,
            line,
            column,
            scopes: this.createScopes()
        };
        this.callStack.push(frame);
        return frame;
    }
    popFrame() {
        return this.callStack.pop();
    }
    createScopes() {
        const scopes = [];
        // Локальные переменные
        scopes.push({
            name: "Локальные",
            type: "local",
            variablesReference: this.variablesRefCounter++
        });
        // Модульные переменные
        scopes.push({
            name: "Модуль",
            type: "module",
            variablesReference: this.variablesRefCounter++
        });
        // Глобальные
        scopes.push({
            name: "Глобальные",
            type: "global",
            variablesReference: this.variablesRefCounter++
        });
        return scopes;
    }
    // === Variables ===
    getVariables(reference) {
        return this.variables.get(reference) || [];
    }
    setVariables(reference, variables) {
        this.variables.set(reference, variables);
    }
    async evaluate(expression, frameId) {
        // В реальной реализации здесь будет вызов runtime
        // Для демонстрации возвращаем заглушку
        return {
            name: expression,
            value: "<evaluation result>",
            type: "String",
            variablesReference: 0
        };
    }
    // === Module Management ===
    getOrParseModule(file) {
        if (this.moduleCache.has(file)) {
            return this.moduleCache.get(file);
        }
        // В реальной реализации здесь чтение файла
        // const source = fs.readFileSync(file, 'utf-8');
        // const { ast, errors } = parse(source);
        // Заглушка
        return null;
    }
    parseSource(file, source) {
        const { ast, errors } = parse(source);
        if (errors.length > 0) {
            for (const error of errors) {
                this.emit("output", "stderr", `${file}:${error.line}:${error.column}: ${error.message}\n`);
            }
        }
        if (ast) {
            this.moduleCache.set(file, ast);
        }
        return ast;
    }
    // === Internal Execution ===
    async runUntilBreakpoint() {
        // В реальной реализации здесь цикл выполнения
        // с проверкой breakpoints после каждой строки
        // Симуляция для демонстрации
        if (this.currentContext) {
            const bp = this.checkBreakpoint(this.currentContext.file, this.currentContext.line);
            if (bp) {
                bp.hitCount++;
                await this.pause("breakpoint");
            }
        }
    }
    async executeNextStatement() {
        // В реальной реализации здесь выполнение одного statement'а
        if (this.currentContext) {
            // Переходим к следующей строке
            this.currentContext.line++;
            // Проверяем условие остановки
            if (this.shouldStop()) {
                await this.pause("step");
            }
            else {
                // Проверяем breakpoints
                const bp = this.checkBreakpoint(this.currentContext.file, this.currentContext.line);
                if (bp) {
                    bp.hitCount++;
                    await this.pause("breakpoint");
                }
            }
        }
    }
    async runUntilDepth(targetDepth) {
        while (this.callStack.length > targetDepth && this.state === "running") {
            await this.executeNextStatement();
        }
        if (this.state === "running") {
            await this.pause("step");
        }
    }
    shouldStop() {
        switch (this.stepMode) {
            case "in":
                return true; // Всегда останавливаемся
            case "over":
                return this.callStack.length <= this.stepTargetDepth;
            case "out":
                return this.callStack.length < this.stepTargetDepth;
            default:
                return false;
        }
    }
    checkBreakpoint(file, line) {
        const bps = this.breakpoints.get(file) || [];
        for (const bp of bps) {
            if (bp.line === line && bp.enabled && bp.verified) {
                // Проверяем условие
                if (bp.condition) {
                    // В реальной реализации вычисляем условие
                    // const result = await this.evaluate(bp.condition);
                    // if (!result) continue;
                }
                // Проверяем hit condition
                if (bp.hitCondition) {
                    const targetHits = parseInt(bp.hitCondition, 10);
                    if (bp.hitCount + 1 < targetHits) {
                        continue;
                    }
                }
                // Logpoint
                if (bp.logMessage) {
                    // В реальной реализации интерполируем переменные в сообщении
                    this.emit("output", "console", bp.logMessage + "\n");
                    continue; // Не останавливаемся на logpoint
                }
                return bp;
            }
        }
        return null;
    }
    findFirstExecutableLine(ast) {
        // Ищем первую строку с исполняемым кодом
        const candidates = this.findBreakpointCandidates(ast);
        return candidates.length > 0 ? Math.min(...candidates) : 1;
    }
    cleanup() {
        this.breakpoints.clear();
        this.callStack = [];
        this.variables.clear();
        this.moduleCache.clear();
        this.currentContext = null;
    }
}
// === Вспомогательные функции ===
export function createDebugEngine() {
    return new DebugEngine();
}
//# sourceMappingURL=debug-engine.js.map