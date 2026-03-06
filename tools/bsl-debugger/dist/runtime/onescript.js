/**
 * OneScript Runtime Backend
 *
 * Интеграция с OneScript для реального выполнения BSL-кода.
 * Поддерживает несколько режимов:
 * 1. CLI — запуск через oscript.exe
 * 2. Инструментированный — с инъекцией отладочного кода
 * 3. HTTP Debug — через HTTP API OneScript.Web
 */
import { spawn, exec } from "child_process";
import { promisify } from "util";
import { EventEmitter } from "events";
import * as fs from "fs";
import * as path from "path";
import * as net from "net";
const execAsync = promisify(exec);
// === OneScript CLI Runtime ===
export class OneScriptCLI extends EventEmitter {
    config;
    process = null;
    constructor(config = {}) {
        super();
        this.config = {
            oscriptPath: config.oscriptPath || this.findOscript(),
            workingDir: config.workingDir || process.cwd(),
            env: { ...process.env, ...config.env },
            encoding: config.encoding || "utf-8",
            timeout: config.timeout || 30000
        };
    }
    findOscript() {
        // Пытаемся найти oscript в PATH
        const candidates = [
            "oscript",
            "/usr/local/bin/oscript",
            "/usr/bin/oscript",
            "C:\\Program Files\\OneScript\\bin\\oscript.exe",
            "C:\\Program Files (x86)\\OneScript\\bin\\oscript.exe"
        ];
        // В Windows проверяем переменную окружения
        if (process.env.OSCRIPT_HOME) {
            candidates.unshift(path.join(process.env.OSCRIPT_HOME, "bin", "oscript.exe"));
        }
        return candidates[0]; // В реальной реализации проверяем существование
    }
    async execute(code, args = []) {
        // Создаём временный файл
        const tempFile = path.join(this.config.workingDir, `_debug_${Date.now()}.os`);
        try {
            fs.writeFileSync(tempFile, code, { encoding: this.config.encoding });
            return await this.executeFile(tempFile, args);
        }
        finally {
            // Удаляем временный файл
            try {
                fs.unlinkSync(tempFile);
            }
            catch { }
        }
    }
    async executeFile(file, args = []) {
        const startTime = Date.now();
        return new Promise((resolve) => {
            const cmdArgs = ["-encoding=utf-8", file, ...args];
            this.process = spawn(this.config.oscriptPath, cmdArgs, {
                cwd: this.config.workingDir,
                env: this.config.env,
                stdio: ["pipe", "pipe", "pipe"]
            });
            let stdout = "";
            let stderr = "";
            this.process.stdout?.on("data", (data) => {
                const text = data.toString();
                stdout += text;
                this.emit("output", "stdout", text);
            });
            this.process.stderr?.on("data", (data) => {
                const text = data.toString();
                stderr += text;
                this.emit("output", "stderr", text);
            });
            const timeout = setTimeout(() => {
                this.process?.kill("SIGKILL");
            }, this.config.timeout);
            this.process.on("close", (exitCode) => {
                clearTimeout(timeout);
                resolve({
                    success: exitCode === 0,
                    output: stdout,
                    errors: stderr,
                    exitCode: exitCode || 0,
                    duration: Date.now() - startTime
                });
            });
            this.process.on("error", (error) => {
                clearTimeout(timeout);
                resolve({
                    success: false,
                    output: stdout,
                    errors: error.message,
                    exitCode: -1,
                    duration: Date.now() - startTime
                });
            });
        });
    }
    async getVariables() {
        // CLI режим не поддерживает получение переменных во время выполнения
        // Используем инструментированный режим для этого
        return [];
    }
    async evaluate(expression) {
        // Выполняем выражение через временный скрипт
        const code = `
      Результат = ${expression};
      Сообщить(ТипЗнч(Результат));
      Сообщить(Результат);
    `;
        const result = await this.execute(code);
        const lines = result.output.trim().split("\n");
        return {
            name: expression,
            value: lines[1] || "",
            type: lines[0] || "Unknown",
            stringValue: lines[1] || ""
        };
    }
    dispose() {
        this.process?.kill();
        this.process = null;
    }
}
// === Instrumented Runtime ===
/**
 * Инструментированный runtime — инъектирует отладочный код
 * в исходники для трассировки выполнения.
 */
export class InstrumentedRuntime extends EventEmitter {
    cli;
    debugPort;
    debugServer = null;
    debugSocket = null;
    currentVariables = [];
    currentStack = [];
    constructor(config = {}) {
        super();
        this.cli = new OneScriptCLI(config);
        this.debugPort = 0; // Будет назначен при запуске сервера
    }
    async execute(code, args = []) {
        // Инструментируем код
        const instrumented = this.instrumentCode(code);
        // Запускаем debug сервер
        await this.startDebugServer();
        // Выполняем инструментированный код
        const result = await this.cli.execute(instrumented, args);
        // Останавливаем сервер
        this.stopDebugServer();
        return result;
    }
    async executeFile(file, args = []) {
        const code = fs.readFileSync(file, "utf-8");
        return this.execute(code, args);
    }
    instrumentCode(code) {
        // Разбиваем код на строки
        const lines = code.split("\n");
        const instrumented = [];
        // Добавляем хелпер для отладки
        instrumented.push(`
// === DEBUG INSTRUMENTATION ===
Перем _ОтладчикПодключение;
Перем _ОтладчикПорт;

Процедура _ОтладкаСообщить(Сообщение)
  Попытка
    Если _ОтладчикПодключение = Неопределено Тогда
      _ОтладчикПодключение = Новый TCPКлиент();
      _ОтладчикПодключение.Подключиться("127.0.0.1", ${this.debugPort});
    КонецЕсли;
    _ОтладчикПодключение.Отправить(Сообщение + Символы.ПС);
  Исключение
  КонецПопытки;
КонецПроцедуры

Процедура _ОтладкаТочка(Строка, ИмяФайла, Переменные = "")
  _ОтладкаСообщить("BREAK:" + Строка + ":" + ИмяФайла + ":" + Переменные);
КонецПроцедуры

Процедура _ОтладкаПеременная(Имя, Значение, Тип)
  _ОтладкаСообщить("VAR:" + Имя + ":" + Тип + ":" + Значение);
КонецПроцедуры
// === END DEBUG INSTRUMENTATION ===
`);
        // Инструментируем каждую строку
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const lineNum = i + 1;
            // Пропускаем пустые строки и комментарии
            if (this.isExecutableLine(line)) {
                // Добавляем точку трассировки перед строкой
                instrumented.push(`_ОтладкаТочка(${lineNum}, "source.os");`);
            }
            instrumented.push(line);
        }
        return instrumented.join("\n");
    }
    isExecutableLine(line) {
        const trimmed = line.trim();
        if (trimmed === "")
            return false;
        if (trimmed.startsWith("//"))
            return false;
        if (trimmed.toLowerCase().startsWith("процедура"))
            return false;
        if (trimmed.toLowerCase().startsWith("функция"))
            return false;
        if (trimmed.toLowerCase().startsWith("конецпроцедуры"))
            return false;
        if (trimmed.toLowerCase().startsWith("конецфункции"))
            return false;
        return true;
    }
    async startDebugServer() {
        return new Promise((resolve, reject) => {
            this.debugServer = net.createServer((socket) => {
                this.debugSocket = socket;
                socket.on("data", (data) => {
                    const messages = data.toString().split("\n").filter(m => m);
                    for (const msg of messages) {
                        this.handleDebugMessage(msg);
                    }
                });
                socket.on("close", () => {
                    this.debugSocket = null;
                });
            });
            this.debugServer.listen(0, "127.0.0.1", () => {
                const addr = this.debugServer.address();
                this.debugPort = addr.port;
                resolve();
            });
            this.debugServer.on("error", reject);
        });
    }
    stopDebugServer() {
        this.debugSocket?.destroy();
        this.debugServer?.close();
        this.debugSocket = null;
        this.debugServer = null;
    }
    handleDebugMessage(message) {
        const parts = message.split(":");
        const type = parts[0];
        switch (type) {
            case "BREAK":
                const line = parseInt(parts[1], 10);
                const file = parts[2];
                this.emit("breakpoint", { line, file });
                break;
            case "VAR":
                const name = parts[1];
                const varType = parts[2];
                const value = parts.slice(3).join(":"); // Значение может содержать ':'
                this.currentVariables.push({
                    name,
                    value,
                    type: varType,
                    stringValue: value
                });
                this.emit("variable", { name, type: varType, value });
                break;
        }
    }
    async getVariables() {
        return [...this.currentVariables];
    }
    async evaluate(expression) {
        return this.cli.evaluate(expression);
    }
    dispose() {
        this.stopDebugServer();
        this.cli.dispose();
    }
}
// === HTTP Debug Runtime (для OneScript.Web) ===
export class HTTPDebugRuntime extends EventEmitter {
    baseUrl;
    constructor(baseUrl = "http://localhost:5000") {
        super();
        this.baseUrl = baseUrl;
    }
    async execute(code, args = []) {
        const startTime = Date.now();
        try {
            const response = await fetch(`${this.baseUrl}/debug/execute`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code, args })
            });
            const result = await response.json();
            return {
                success: result.success,
                output: result.output || "",
                errors: result.errors || "",
                exitCode: result.exitCode || 0,
                duration: Date.now() - startTime
            };
        }
        catch (error) {
            return {
                success: false,
                output: "",
                errors: error instanceof Error ? error.message : String(error),
                exitCode: -1,
                duration: Date.now() - startTime
            };
        }
    }
    async executeFile(file, args = []) {
        const code = fs.readFileSync(file, "utf-8");
        return this.execute(code, args);
    }
    async getVariables() {
        try {
            const response = await fetch(`${this.baseUrl}/debug/variables`);
            return await response.json();
        }
        catch {
            return [];
        }
    }
    async evaluate(expression) {
        try {
            const response = await fetch(`${this.baseUrl}/debug/evaluate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ expression })
            });
            return await response.json();
        }
        catch (error) {
            return {
                name: expression,
                value: null,
                type: "Error",
                stringValue: error instanceof Error ? error.message : String(error)
            };
        }
    }
    dispose() {
        // HTTP клиент не требует очистки
    }
}
export function createRuntime(type, config) {
    switch (type) {
        case "cli":
            return new OneScriptCLI(config);
        case "instrumented":
            return new InstrumentedRuntime(config);
        case "http":
            return new HTTPDebugRuntime(config);
        default:
            throw new Error(`Unknown runtime type: ${type}`);
    }
}
// === Вспомогательные функции для работы с переменными BSL ===
export function serializeBSLValue(value) {
    if (value === null || value === undefined) {
        return "Неопределено";
    }
    const type = typeof value;
    switch (type) {
        case "boolean":
            return value ? "Истина" : "Ложь";
        case "number":
            return value.toString();
        case "string":
            return `"${value.replace(/"/g, '""')}"`;
        case "object":
            if (Array.isArray(value)) {
                return `Массив (${value.length})`;
            }
            if (value instanceof Date) {
                return `'${value.toISOString().replace("T", " ").substring(0, 19)}'`;
            }
            return `Структура (${Object.keys(value).length})`;
        default:
            return String(value);
    }
}
export function deserializeBSLValue(str, type) {
    const normalizedType = type.toLowerCase();
    switch (normalizedType) {
        case "число":
        case "number":
            return parseFloat(str);
        case "строка":
        case "string":
            // Убираем кавычки
            if (str.startsWith('"') && str.endsWith('"')) {
                return str.slice(1, -1).replace(/""/g, '"');
            }
            return str;
        case "булево":
        case "boolean":
            return str.toLowerCase() === "истина" || str.toLowerCase() === "true";
        case "дата":
        case "date":
            // Парсим BSL формат даты
            if (str.startsWith("'") && str.endsWith("'")) {
                return new Date(str.slice(1, -1));
            }
            return new Date(str);
        case "неопределено":
        case "undefined":
            return undefined;
        case "null":
            return null;
        default:
            return str;
    }
}
//# sourceMappingURL=onescript.js.map