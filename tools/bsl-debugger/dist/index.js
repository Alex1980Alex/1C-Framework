/**
 * MCP BSL Debugger — Главный файл сервера
 *
 * Полнофункциональный отладчик BSL-кода для Claude Code.
 * Не зависит от VS Code и DAP — собственная реализация.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import * as fs from "fs";
import * as path from "path";
import { DebugEngine } from "./engine/debug-engine.js";
import { createRuntime } from "./runtime/onescript.js";
import { parse } from "./parser/parser.js";
const sessions = new Map();
let sessionCounter = 0;
function createSession(runtimeType = "instrumented") {
    const id = `session_${++sessionCounter}_${Date.now()}`;
    const engine = new DebugEngine();
    const runtime = createRuntime(runtimeType);
    const session = {
        id,
        engine,
        runtime,
        files: new Map(),
        state: "idle"
    };
    // Подписываемся на события движка
    engine.on("stopped", (reason, context) => {
        session.state = "paused";
        session.lastStopReason = reason;
    });
    engine.on("continued", () => {
        session.state = "running";
    });
    engine.on("terminated", () => {
        session.state = "terminated";
    });
    sessions.set(id, session);
    return session;
}
function getSession(id) {
    return sessions.get(id);
}
function terminateSession(id) {
    const session = sessions.get(id);
    if (session) {
        session.engine.terminate();
        session.runtime.dispose();
        sessions.delete(id);
    }
}
// === MCP Server Setup ===
const server = new McpServer({
    name: "bsl-debugger-full",
    version: "1.0.0"
});
// ============================================================
// TOOL: bsl_debug_start — Запуск сессии отладки
// ============================================================
server.tool("bsl_debug_start", `Создаёт и запускает новую сессию отладки BSL-кода.
   
   Поддерживаемые runtime:
   - cli: Простое выполнение через oscript.exe
   - instrumented: С инструментированием кода для трассировки
   - http: Подключение к OneScript.Web для удалённой отладки
   
   Возвращает ID сессии для дальнейшей работы.`, {
    file: z.string().optional().describe("Путь к .os файлу для отладки"),
    source: z.string().optional().describe("Исходный код BSL (альтернатива file)"),
    args: z.array(z.string()).optional().describe("Аргументы командной строки"),
    runtime: z.enum(["cli", "instrumented", "http"]).default("instrumented")
        .describe("Тип runtime для выполнения"),
    stopOnEntry: z.boolean().default(true)
        .describe("Остановиться на первой строке"),
    httpUrl: z.string().optional()
        .describe("URL для http runtime (например http://localhost:5000)")
}, async (args) => {
    try {
        // Создаём сессию
        const session = createSession(args.runtime);
        // Загружаем исходный код
        let source;
        let filePath;
        if (args.file) {
            filePath = path.resolve(args.file);
            source = fs.readFileSync(filePath, "utf-8");
        }
        else if (args.source) {
            filePath = "/virtual/debug.os";
            source = args.source;
        }
        else {
            throw new Error("Требуется указать file или source");
        }
        session.files.set(filePath, source);
        // Парсим для получения информации о структуре
        const { ast, errors } = parse(source);
        if (errors.length > 0) {
            return {
                content: [{
                        type: "text",
                        text: JSON.stringify({
                            success: false,
                            sessionId: session.id,
                            parseErrors: errors.map(e => ({
                                line: e.line,
                                column: e.column,
                                message: e.message
                            }))
                        }, null, 2)
                    }]
            };
        }
        // Запускаем отладку
        if (ast) {
            session.engine.parseSource(filePath, source);
            await session.engine.launch(filePath, args.args || [], args.stopOnEntry);
        }
        session.state = args.stopOnEntry ? "paused" : "running";
        // Собираем информацию о модуле
        const moduleInfo = ast ? {
            procedures: ast.procedures.map(p => ({
                name: p.name,
                line: p.location.start.line,
                isExport: p.isExport,
                isAsync: p.isAsync,
                parameters: p.parameters.map(param => param.name)
            })),
            functions: ast.functions.map(f => ({
                name: f.name,
                line: f.location.start.line,
                isExport: f.isExport,
                isAsync: f.isAsync,
                parameters: f.parameters.map(param => param.name)
            })),
            moduleVariables: ast.variables.map(v => v.name)
        } : null;
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: true,
                        sessionId: session.id,
                        state: session.state,
                        file: filePath,
                        moduleInfo,
                        message: args.stopOnEntry
                            ? "Отладка запущена, остановлено на точке входа"
                            : "Отладка запущена"
                    }, null, 2)
                }]
        };
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: false,
                        error: error instanceof Error ? error.message : String(error)
                    }, null, 2)
                }]
        };
    }
});
// ============================================================
// TOOL: bsl_debug_breakpoints — Управление точками останова
// ============================================================
server.tool("bsl_debug_breakpoints", `Устанавливает точки останова в BSL-файле.
   
   Поддерживает:
   - Обычные breakpoints
   - Условные breakpoints (condition)
   - Hit count breakpoints (hitCondition) 
   - Logpoints (logMessage) — не останавливают выполнение, только логируют
   
   Автоматически верифицирует и корректирует позиции breakpoints.`, {
    sessionId: z.string().describe("ID сессии отладки"),
    file: z.string().describe("Путь к файлу"),
    breakpoints: z.array(z.object({
        line: z.number().describe("Номер строки"),
        condition: z.string().optional().describe("Условие остановки (BSL выражение)"),
        hitCondition: z.string().optional().describe("Остановиться после N срабатываний"),
        logMessage: z.string().optional().describe("Сообщение для logpoint")
    })).describe("Список точек останова"),
    clearExisting: z.boolean().default(true)
        .describe("Удалить существующие breakpoints в файле")
}, async (args) => {
    const session = getSession(args.sessionId);
    if (!session) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({ success: false, error: "Сессия не найдена" })
                }]
        };
    }
    try {
        const result = session.engine.setBreakpoints(args.file, args.breakpoints);
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: true,
                        breakpoints: result.map(bp => ({
                            id: bp.id,
                            line: bp.line,
                            verified: bp.verified,
                            condition: bp.condition,
                            hitCondition: bp.hitCondition,
                            logMessage: bp.logMessage
                        }))
                    }, null, 2)
                }]
        };
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: false,
                        error: error instanceof Error ? error.message : String(error)
                    })
                }]
        };
    }
});
// ============================================================
// TOOL: bsl_debug_step — Пошаговое выполнение
// ============================================================
server.tool("bsl_debug_step", `Выполняет шаг отладки.
   
   Действия:
   - continue: Продолжить до следующего breakpoint
   - stepOver: Шаг через (не входить в процедуры/функции)
   - stepIn: Шаг с входом (войти в процедуру/функцию)
   - stepOut: Шаг с выходом (выйти из текущей процедуры/функции)
   - pause: Приостановить выполнение
   
   Возвращает текущую позицию и причину остановки.`, {
    sessionId: z.string().describe("ID сессии"),
    action: z.enum(["continue", "stepOver", "stepIn", "stepOut", "pause"])
        .describe("Действие")
}, async (args) => {
    const session = getSession(args.sessionId);
    if (!session) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({ success: false, error: "Сессия не найдена" })
                }]
        };
    }
    try {
        switch (args.action) {
            case "continue":
                await session.engine.continue();
                break;
            case "stepOver":
                await session.engine.stepOver();
                break;
            case "stepIn":
                await session.engine.stepIn();
                break;
            case "stepOut":
                await session.engine.stepOut();
                break;
            case "pause":
                await session.engine.pause();
                break;
        }
        const context = session.engine.getCurrentContext();
        const stack = session.engine.getCallStack();
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: true,
                        state: session.state,
                        stopReason: session.lastStopReason,
                        currentPosition: context ? {
                            file: context.file,
                            line: context.line,
                            column: context.column,
                            function: context.functionName
                        } : null,
                        stackDepth: stack.length
                    }, null, 2)
                }]
        };
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: false,
                        error: error instanceof Error ? error.message : String(error)
                    })
                }]
        };
    }
});
// ============================================================
// TOOL: bsl_debug_variables — Просмотр переменных
// ============================================================
server.tool("bsl_debug_variables", `Получает значения переменных в текущей области видимости.
   
   Области видимости:
   - local: Локальные переменные процедуры/функции
   - module: Переменные модуля
   - global: Глобальные переменные
   - all: Все области
   
   Поддерживает раскрытие вложенных объектов (структуры, массивы).`, {
    sessionId: z.string().describe("ID сессии"),
    scope: z.enum(["local", "module", "global", "all"]).default("all")
        .describe("Область видимости"),
    filter: z.string().optional()
        .describe("Фильтр по имени (regex)"),
    expand: z.string().optional()
        .describe("Имя переменной для раскрытия"),
    maxDepth: z.number().default(2)
        .describe("Максимальная глубина раскрытия")
}, async (args) => {
    const session = getSession(args.sessionId);
    if (!session) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({ success: false, error: "Сессия не найдена" })
                }]
        };
    }
    try {
        // Получаем переменные из runtime
        const runtimeVars = await session.runtime.getVariables();
        // Фильтруем и форматируем
        let variables = runtimeVars;
        if (args.filter) {
            const regex = new RegExp(args.filter, "i");
            variables = variables.filter(v => regex.test(v.name));
        }
        // Группируем по scope (упрощённая логика)
        const result = {};
        if (args.scope === "all" || args.scope === "local") {
            result["Локальные"] = variables.filter(v => !v.name.startsWith("_"));
        }
        if (args.scope === "all" || args.scope === "module") {
            result["Модуль"] = variables.filter(v => v.name.startsWith("_"));
        }
        if (args.scope === "all" || args.scope === "global") {
            result["Глобальные"] = [];
        }
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: true,
                        variables: result
                    }, null, 2)
                }]
        };
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: false,
                        error: error instanceof Error ? error.message : String(error)
                    })
                }]
        };
    }
});
// ============================================================
// TOOL: bsl_debug_evaluate — Вычисление выражений
// ============================================================
server.tool("bsl_debug_evaluate", `Вычисляет BSL-выражение в контексте текущего стека.
   
   Примеры:
   - Простые выражения: "Переменная + 1"
   - Вызов функций: "СтрДлина(Строка)"
   - Доступ к свойствам: "Объект.Свойство"
   - Создание объектов: "Новый Массив"
   
   Может модифицировать переменные: "Переменная = НовоеЗначение"`, {
    sessionId: z.string().describe("ID сессии"),
    expression: z.string().describe("BSL выражение"),
    frameId: z.number().optional().describe("ID фрейма стека (по умолчанию текущий)")
}, async (args) => {
    const session = getSession(args.sessionId);
    if (!session) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({ success: false, error: "Сессия не найдена" })
                }]
        };
    }
    try {
        const result = await session.runtime.evaluate(args.expression);
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: true,
                        expression: args.expression,
                        result: result.stringValue,
                        type: result.type,
                        value: result.value
                    }, null, 2)
                }]
        };
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: false,
                        expression: args.expression,
                        error: error instanceof Error ? error.message : String(error)
                    })
                }]
        };
    }
});
// ============================================================
// TOOL: bsl_debug_stack — Стек вызовов
// ============================================================
server.tool("bsl_debug_stack", `Получает стек вызовов.
   
   Показывает цепочку вызовов от текущей позиции до точки входа.
   Для каждого фрейма доступны: имя функции, файл, строка, колонка.`, {
    sessionId: z.string().describe("ID сессии"),
    startFrame: z.number().default(0).describe("Начальный фрейм"),
    levels: z.number().default(20).describe("Количество уровней")
}, async (args) => {
    const session = getSession(args.sessionId);
    if (!session) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({ success: false, error: "Сессия не найдена" })
                }]
        };
    }
    try {
        const stack = session.engine.getCallStack();
        const frames = stack.slice(args.startFrame, args.startFrame + args.levels);
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: true,
                        totalFrames: stack.length,
                        stackFrames: frames.map((frame, index) => ({
                            level: args.startFrame + index,
                            id: frame.id,
                            name: frame.name,
                            file: frame.file,
                            line: frame.line,
                            column: frame.column
                        }))
                    }, null, 2)
                }]
        };
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: false,
                        error: error instanceof Error ? error.message : String(error)
                    })
                }]
        };
    }
});
// ============================================================
// TOOL: bsl_execute — Выполнение кода без отладки
// ============================================================
server.tool("bsl_execute", `Выполняет BSL-код без отладки.
   
   Быстрый способ выполнить скрипт и получить результат.
   Поддерживает передачу аргументов командной строки.`, {
    file: z.string().optional().describe("Путь к .os файлу"),
    source: z.string().optional().describe("Исходный код BSL"),
    args: z.array(z.string()).optional().describe("Аргументы"),
    timeout: z.number().default(30000).describe("Таймаут (мс)")
}, async (args) => {
    try {
        const runtime = createRuntime("cli", { timeout: args.timeout });
        let result;
        if (args.file) {
            result = await runtime.executeFile(args.file, args.args);
        }
        else if (args.source) {
            result = await runtime.execute(args.source, args.args);
        }
        else {
            throw new Error("Требуется file или source");
        }
        runtime.dispose();
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: result.success,
                        output: result.output,
                        errors: result.errors,
                        exitCode: result.exitCode,
                        duration: result.duration
                    }, null, 2)
                }]
        };
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: false,
                        error: error instanceof Error ? error.message : String(error)
                    })
                }]
        };
    }
});
// ============================================================
// TOOL: bsl_analyze — Статический анализ кода
// ============================================================
server.tool("bsl_analyze", `Выполняет статический анализ BSL-кода.
   
   Анализирует:
   - Синтаксические ошибки
   - Структуру модуля (процедуры, функции, переменные)
   - Точки для установки breakpoints
   - Области видимости`, {
    file: z.string().optional().describe("Путь к файлу"),
    source: z.string().optional().describe("Исходный код")
}, async (args) => {
    try {
        let source;
        let filePath;
        if (args.file) {
            filePath = path.resolve(args.file);
            source = fs.readFileSync(filePath, "utf-8");
        }
        else if (args.source) {
            filePath = "inline";
            source = args.source;
        }
        else {
            throw new Error("Требуется file или source");
        }
        const { ast, errors } = parse(source);
        if (errors.length > 0 || !ast) {
            return {
                content: [{
                        type: "text",
                        text: JSON.stringify({
                            success: false,
                            errors: errors.map(e => ({
                                line: e.line,
                                column: e.column,
                                message: e.message
                            }))
                        }, null, 2)
                    }]
            };
        }
        // Собираем информацию о структуре
        const analysis = {
            procedures: ast.procedures.map(p => ({
                name: p.name,
                startLine: p.location.start.line,
                endLine: p.location.end.line,
                isExport: p.isExport,
                isAsync: p.isAsync,
                parameters: p.parameters.map(param => ({
                    name: param.name,
                    isByValue: param.isByValue,
                    hasDefault: !!param.defaultValue
                })),
                localVariables: p.localVariables.map(v => v.name),
                annotations: p.annotations.map(a => a.name)
            })),
            functions: ast.functions.map(f => ({
                name: f.name,
                startLine: f.location.start.line,
                endLine: f.location.end.line,
                isExport: f.isExport,
                isAsync: f.isAsync,
                parameters: f.parameters.map(param => ({
                    name: param.name,
                    isByValue: param.isByValue,
                    hasDefault: !!param.defaultValue
                })),
                localVariables: f.localVariables.map(v => v.name),
                annotations: f.annotations.map(a => a.name)
            })),
            moduleVariables: ast.variables.map(v => ({
                name: v.name,
                isExport: v.isExport,
                line: v.location.start.line
            })),
            uses: ast.uses.map(u => u.library),
            // Строки, на которых можно ставить breakpoints
            breakpointLines: collectBreakpointLines(ast),
            // Общая статистика
            statistics: {
                totalLines: source.split("\n").length,
                procedureCount: ast.procedures.length,
                functionCount: ast.functions.length,
                moduleVariableCount: ast.variables.length,
                exportCount: ast.procedures.filter(p => p.isExport).length +
                    ast.functions.filter(f => f.isExport).length
            }
        };
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: true,
                        file: filePath,
                        analysis
                    }, null, 2)
                }]
        };
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: false,
                        error: error instanceof Error ? error.message : String(error)
                    })
                }]
        };
    }
});
// ============================================================
// TOOL: bsl_debug_stop — Завершение сессии
// ============================================================
server.tool("bsl_debug_stop", "Завершает сессию отладки и освобождает ресурсы", {
    sessionId: z.string().describe("ID сессии")
}, async (args) => {
    try {
        terminateSession(args.sessionId);
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: true,
                        message: "Сессия завершена"
                    })
                }]
        };
    }
    catch (error) {
        return {
            content: [{
                    type: "text",
                    text: JSON.stringify({
                        success: false,
                        error: error instanceof Error ? error.message : String(error)
                    })
                }]
        };
    }
});
// ============================================================
// TOOL: bsl_debug_sessions — Список активных сессий
// ============================================================
server.tool("bsl_debug_sessions", "Возвращает список всех активных сессий отладки", {}, async () => {
    const list = Array.from(sessions.entries()).map(([id, session]) => ({
        id,
        state: session.state,
        files: Array.from(session.files.keys())
    }));
    return {
        content: [{
                type: "text",
                text: JSON.stringify({
                    success: true,
                    sessions: list,
                    count: list.length
                }, null, 2)
            }]
    };
});
// === Вспомогательные функции ===
function collectBreakpointLines(ast) {
    const lines = new Set();
    const processStatements = (statements) => {
        for (const stmt of statements) {
            lines.add(stmt.location.start.line);
            switch (stmt.type) {
                case "IfStatement":
                    processStatements(stmt.thenBranch);
                    for (const elseIf of stmt.elseIfBranches) {
                        processStatements(elseIf.body);
                    }
                    if (stmt.elseBranch) {
                        processStatements(stmt.elseBranch);
                    }
                    break;
                case "ForStatement":
                case "ForEachStatement":
                case "WhileStatement":
                    processStatements(stmt.body);
                    break;
                case "TryStatement":
                    processStatements(stmt.tryBlock);
                    processStatements(stmt.exceptBlock);
                    break;
            }
        }
    };
    for (const proc of ast.procedures) {
        lines.add(proc.location.start.line);
        processStatements(proc.body);
    }
    for (const func of ast.functions) {
        lines.add(func.location.start.line);
        processStatements(func.body);
    }
    processStatements(ast.statements);
    return Array.from(lines).sort((a, b) => a - b);
}
// === Запуск сервера ===
const transport = new StdioServerTransport();
await server.connect(transport);
console.error("BSL Debugger MCP Server started (Full Implementation)");
console.error("Available tools: bsl_debug_start, bsl_debug_breakpoints, bsl_debug_step,");
console.error("  bsl_debug_variables, bsl_debug_evaluate, bsl_debug_stack,");
console.error("  bsl_execute, bsl_analyze, bsl_debug_stop, bsl_debug_sessions");
//# sourceMappingURL=index.js.map