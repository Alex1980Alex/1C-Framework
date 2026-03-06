/**
 * BSL Call Graph Analyzer
 * Анализирует граф вызовов процедур и функций в BSL коде
 *
 * Функционал:
 * - Извлечение всех вызовов внутри каждой процедуры/функции
 * - Определение типа вызова (внутренний, общий модуль, менеджер, объект)
 * - Построение дерева вызовов
 * - Выявление связей с объектами конфигурации
 */
import { getBSLAnalyzer } from './bsl-treesitter-analyzer.js';
/**
 * Тип вызова
 */
export var CallType;
(function (CallType) {
    /** Вызов процедуры/функции в этом же модуле */
    CallType["INTERNAL"] = "internal";
    /** Вызов общего модуля (ОбщийМодуль.Функция()) */
    CallType["COMMON_MODULE"] = "common_module";
    /** Вызов менеджера объекта (Справочники.Товары.НайтиПоКоду()) */
    CallType["MANAGER"] = "manager";
    /** Вызов метода объекта (Объект.Метод()) */
    CallType["OBJECT_METHOD"] = "object_method";
    /** Вызов платформенной функции (Сообщить(), ТекущаяДата()) */
    CallType["PLATFORM"] = "platform";
    /** Конструктор (Новый Запрос, Новый Структура) */
    CallType["CONSTRUCTOR"] = "constructor";
    /** Неопределённый тип */
    CallType["UNKNOWN"] = "unknown";
})(CallType || (CallType = {}));
/**
 * Категория объекта конфигурации
 */
export var ConfigObjectCategory;
(function (ConfigObjectCategory) {
    ConfigObjectCategory["CATALOG"] = "\u0421\u043F\u0440\u0430\u0432\u043E\u0447\u043D\u0438\u043A";
    ConfigObjectCategory["DOCUMENT"] = "\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442";
    ConfigObjectCategory["REGISTER_ACCUMULATION"] = "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u041D\u0430\u043A\u043E\u043F\u043B\u0435\u043D\u0438\u044F";
    ConfigObjectCategory["REGISTER_INFORMATION"] = "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0421\u0432\u0435\u0434\u0435\u043D\u0438\u0439";
    ConfigObjectCategory["REGISTER_ACCOUNTING"] = "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0411\u0443\u0445\u0433\u0430\u043B\u0442\u0435\u0440\u0438\u0438";
    ConfigObjectCategory["REGISTER_CALCULATION"] = "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0420\u0430\u0441\u0447\u0435\u0442\u0430";
    ConfigObjectCategory["DATA_PROCESSOR"] = "\u041E\u0431\u0440\u0430\u0431\u043E\u0442\u043A\u0430";
    ConfigObjectCategory["REPORT"] = "\u041E\u0442\u0447\u0435\u0442";
    ConfigObjectCategory["COMMON_MODULE"] = "\u041E\u0431\u0449\u0438\u0439\u041C\u043E\u0434\u0443\u043B\u044C";
    ConfigObjectCategory["ENUM"] = "\u041F\u0435\u0440\u0435\u0447\u0438\u0441\u043B\u0435\u043D\u0438\u0435";
    ConfigObjectCategory["CHART_OF_ACCOUNTS"] = "\u041F\u043B\u0430\u043D\u0421\u0447\u0435\u0442\u043E\u0432";
    ConfigObjectCategory["CHART_OF_CHARACTERISTIC_TYPES"] = "\u041F\u043B\u0430\u043D\u0412\u0438\u0434\u043E\u0432\u0425\u0430\u0440\u0430\u043A\u0442\u0435\u0440\u0438\u0441\u0442\u0438\u043A";
    ConfigObjectCategory["CONSTANT"] = "\u041A\u043E\u043D\u0441\u0442\u0430\u043D\u0442\u0430";
    ConfigObjectCategory["EXCHANGE_PLAN"] = "\u041F\u043B\u0430\u043D\u041E\u0431\u043C\u0435\u043D\u0430";
    ConfigObjectCategory["BUSINESS_PROCESS"] = "\u0411\u0438\u0437\u043D\u0435\u0441\u041F\u0440\u043E\u0446\u0435\u0441\u0441";
    ConfigObjectCategory["TASK"] = "\u0417\u0430\u0434\u0430\u0447\u0430";
    ConfigObjectCategory["SEQUENCE"] = "\u041F\u043E\u0441\u043B\u0435\u0434\u043E\u0432\u0430\u0442\u0435\u043B\u044C\u043D\u043E\u0441\u0442\u044C";
    ConfigObjectCategory["HTTP_SERVICE"] = "HTTP\u0421\u0435\u0440\u0432\u0438\u0441";
    ConfigObjectCategory["WEB_SERVICE"] = "Web\u0421\u0435\u0440\u0432\u0438\u0441";
    ConfigObjectCategory["UNKNOWN"] = "\u041D\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043D\u043E";
})(ConfigObjectCategory || (ConfigObjectCategory = {}));
/**
 * Паттерны для определения типов вызовов
 */
const CONFIG_OBJECT_PATTERNS = [
    // Справочники
    { pattern: /Справочники\.(\w+)/gi, category: ConfigObjectCategory.CATALOG, nameGroup: 1 },
    { pattern: /Catalogs\.(\w+)/gi, category: ConfigObjectCategory.CATALOG, nameGroup: 1 },
    // Документы
    { pattern: /Документы\.(\w+)/gi, category: ConfigObjectCategory.DOCUMENT, nameGroup: 1 },
    { pattern: /Documents\.(\w+)/gi, category: ConfigObjectCategory.DOCUMENT, nameGroup: 1 },
    // Регистры накопления
    { pattern: /РегистрыНакопления\.(\w+)/gi, category: ConfigObjectCategory.REGISTER_ACCUMULATION, nameGroup: 1 },
    { pattern: /AccumulationRegisters\.(\w+)/gi, category: ConfigObjectCategory.REGISTER_ACCUMULATION, nameGroup: 1 },
    // Регистры сведений
    { pattern: /РегистрыСведений\.(\w+)/gi, category: ConfigObjectCategory.REGISTER_INFORMATION, nameGroup: 1 },
    { pattern: /InformationRegisters\.(\w+)/gi, category: ConfigObjectCategory.REGISTER_INFORMATION, nameGroup: 1 },
    // Регистры бухгалтерии
    { pattern: /РегистрыБухгалтерии\.(\w+)/gi, category: ConfigObjectCategory.REGISTER_ACCOUNTING, nameGroup: 1 },
    { pattern: /AccountingRegisters\.(\w+)/gi, category: ConfigObjectCategory.REGISTER_ACCOUNTING, nameGroup: 1 },
    // Обработки
    { pattern: /Обработки\.(\w+)/gi, category: ConfigObjectCategory.DATA_PROCESSOR, nameGroup: 1 },
    { pattern: /DataProcessors\.(\w+)/gi, category: ConfigObjectCategory.DATA_PROCESSOR, nameGroup: 1 },
    // Отчеты
    { pattern: /Отчеты\.(\w+)/gi, category: ConfigObjectCategory.REPORT, nameGroup: 1 },
    { pattern: /Reports\.(\w+)/gi, category: ConfigObjectCategory.REPORT, nameGroup: 1 },
    // Перечисления
    { pattern: /Перечисления\.(\w+)/gi, category: ConfigObjectCategory.ENUM, nameGroup: 1 },
    { pattern: /Enums\.(\w+)/gi, category: ConfigObjectCategory.ENUM, nameGroup: 1 },
    // Планы счетов
    { pattern: /ПланыСчетов\.(\w+)/gi, category: ConfigObjectCategory.CHART_OF_ACCOUNTS, nameGroup: 1 },
    { pattern: /ChartsOfAccounts\.(\w+)/gi, category: ConfigObjectCategory.CHART_OF_ACCOUNTS, nameGroup: 1 },
    // Планы видов характеристик
    { pattern: /ПланыВидовХарактеристик\.(\w+)/gi, category: ConfigObjectCategory.CHART_OF_CHARACTERISTIC_TYPES, nameGroup: 1 },
    { pattern: /ChartsOfCharacteristicTypes\.(\w+)/gi, category: ConfigObjectCategory.CHART_OF_CHARACTERISTIC_TYPES, nameGroup: 1 },
    // Константы
    { pattern: /Константы\.(\w+)/gi, category: ConfigObjectCategory.CONSTANT, nameGroup: 1 },
    { pattern: /Constants\.(\w+)/gi, category: ConfigObjectCategory.CONSTANT, nameGroup: 1 },
    // Планы обмена
    { pattern: /ПланыОбмена\.(\w+)/gi, category: ConfigObjectCategory.EXCHANGE_PLAN, nameGroup: 1 },
    { pattern: /ExchangePlans\.(\w+)/gi, category: ConfigObjectCategory.EXCHANGE_PLAN, nameGroup: 1 },
    // Бизнес-процессы
    { pattern: /БизнесПроцессы\.(\w+)/gi, category: ConfigObjectCategory.BUSINESS_PROCESS, nameGroup: 1 },
    { pattern: /BusinessProcesses\.(\w+)/gi, category: ConfigObjectCategory.BUSINESS_PROCESS, nameGroup: 1 },
    // Задачи
    { pattern: /Задачи\.(\w+)/gi, category: ConfigObjectCategory.TASK, nameGroup: 1 },
    { pattern: /Tasks\.(\w+)/gi, category: ConfigObjectCategory.TASK, nameGroup: 1 },
];
/**
 * Платформенные функции 1С (часть из них)
 */
const PLATFORM_FUNCTIONS = new Set([
    // Общие функции
    'сообщить', 'message', 'предупреждение', 'warning', 'вопрос', 'question',
    'текущаядата', 'currentdate', 'началодня', 'begofday', 'конецдня', 'endofday',
    'началомесяца', 'begofmonth', 'конецмесяца', 'endofmonth', 'началогода', 'begofyear',
    'конецгода', 'endofyear', 'началоквартала', 'begofquarter', 'конецквартала', 'endofquarter',
    // Строковые функции
    'строка', 'string', 'стрдлина', 'strlen', 'стрнайти', 'strfind', 'стрзаменить', 'strreplace',
    'врег', 'upper', 'нрег', 'lower', 'сокрл', 'triml', 'сокрп', 'trimr', 'сокрлп', 'trimall',
    'лев', 'left', 'прав', 'right', 'сред', 'mid', 'стрразделить', 'strsplit',
    // Числовые функции
    'число', 'number', 'цел', 'int', 'окр', 'round', 'формат', 'format',
    // Функции типов
    'тип', 'type', 'типзнч', 'typeof', 'значениезаполнено', 'valuefilled',
    // Функции работы с объектами
    'новый', 'new', 'копироватьданныеформы', 'copyformdata',
    // Транзакции
    'началотранзакции', 'begintransaction', 'зафиксироватьтранзакцию', 'committransaction',
    'отменитьтранзакцию', 'rollbacktransaction', 'транзакцияактивна', 'transactionactive',
    // Работа с коллекциями
    'врег', 'ucase', 'нрег', 'lcase',
    // Файловые операции
    'файл', 'file', 'каталогвременныхфайлов', 'tempfilesdir',
]);
/**
 * Анализатор графа вызовов BSL кода
 */
export class BSLCallGraphAnalyzer {
    constructor() {
        this.initialized = false;
    }
    /**
     * Инициализирует анализатор
     */
    async initialize() {
        if (!this.initialized) {
            this.treesitterAnalyzer = await getBSLAnalyzer();
            this.initialized = true;
        }
    }
    /**
     * Анализирует граф вызовов BSL кода
     * @param code BSL исходный код
     * @param filePath Путь к файлу (опционально)
     * @returns Граф вызовов модуля
     */
    async analyzeCallGraph(code, filePath) {
        await this.initialize();
        // Получаем базовый анализ через tree-sitter
        const baseAnalysis = this.treesitterAnalyzer.analyze(code, filePath);
        // Создаём граф вызовов
        const callGraph = {
            filePath,
            procedures: new Map(),
            allCalls: [],
            internalCalls: [],
            externalCalls: [],
            configObjectCalls: [],
            entryPoints: [],
            usedCommonModules: new Set(),
            usedConfigObjects: new Map()
        };
        // Собираем имена всех процедур/функций в модуле
        const localProcedureNames = new Set();
        [...baseAnalysis.procedures, ...baseAnalysis.functions].forEach(elem => {
            localProcedureNames.add(elem.name.toLowerCase());
        });
        // Анализируем каждую процедуру/функцию
        for (const proc of baseAnalysis.procedures) {
            const procInfo = this.analyzeProcedure(proc, 'procedure', code, localProcedureNames);
            callGraph.procedures.set(proc.name, procInfo);
            if (proc.isExport) {
                callGraph.entryPoints.push(proc.name);
            }
            // Добавляем вызовы в общие списки
            this.addCallsToGraph(procInfo.calls, callGraph);
        }
        for (const func of baseAnalysis.functions) {
            const funcInfo = this.analyzeProcedure(func, 'function', code, localProcedureNames);
            callGraph.procedures.set(func.name, funcInfo);
            if (func.isExport) {
                callGraph.entryPoints.push(func.name);
            }
            // Добавляем вызовы в общие списки
            this.addCallsToGraph(funcInfo.calls, callGraph);
        }
        return callGraph;
    }
    /**
     * Анализирует вызовы внутри процедуры/функции
     */
    analyzeProcedure(element, type, fullCode, localProcedureNames) {
        const body = element.body || '';
        const calls = this.extractCalls(body, element.name, element.startLine, localProcedureNames);
        const procInfo = {
            name: element.name,
            type,
            isExport: element.isExport || false,
            parameters: element.parameters || [],
            startLine: element.startLine,
            endLine: element.endLine,
            comment: element.comment,
            calls,
            internalCalls: calls.filter(c => c.callType === CallType.INTERNAL).map(c => c.callee),
            externalCalls: calls.filter(c => c.callType !== CallType.INTERNAL && c.callType !== CallType.PLATFORM),
            configObjectCalls: calls.filter(c => c.objectCategory !== undefined)
        };
        return procInfo;
    }
    /**
     * Извлекает все вызовы из тела процедуры/функции
     */
    extractCalls(body, callerName, startLine, localProcedureNames) {
        const calls = [];
        const lines = body.split('\n');
        lines.forEach((line, lineIndex) => {
            const actualLine = startLine + lineIndex;
            // Пропускаем комментарии
            const trimmedLine = line.trim();
            if (trimmedLine.startsWith('//'))
                return;
            // Удаляем строковые литералы чтобы не ловить ложные вызовы
            const cleanLine = this.removeStringLiterals(line);
            // Ищем вызовы функций/процедур
            // Паттерн: ИмяМетода( или Объект.Метод(
            // Note: \w doesn't match Cyrillic, so we use explicit character class
            const cyrillicIdPattern = '[А-Яа-яЁёA-Za-z_][А-Яа-яЁёA-Za-z0-9_]*';
            const callPattern = new RegExp(`(${cyrillicIdPattern}(?:\\.${cyrillicIdPattern})*)\\s*\\(`, 'g');
            let match;
            while ((match = callPattern.exec(cleanLine)) !== null) {
                const fullCall = match[1];
                const parts = fullCall.split('.');
                const callInfo = this.classifyCall(fullCall, parts, callerName, actualLine, localProcedureNames);
                if (callInfo) {
                    calls.push(callInfo);
                }
            }
            // Отдельно ищем конструкторы (Новый Тип)
            const constructorPattern = new RegExp(`(?:Новый|New)\\s+(${cyrillicIdPattern})`, 'gi');
            while ((match = constructorPattern.exec(cleanLine)) !== null) {
                calls.push({
                    caller: callerName,
                    callee: `Новый ${match[1]}`,
                    callType: CallType.CONSTRUCTOR,
                    line: actualLine
                });
            }
            // Ищем обращения к объектам конфигурации
            for (const { pattern, category, nameGroup } of CONFIG_OBJECT_PATTERNS) {
                pattern.lastIndex = 0; // Reset regex
                while ((match = pattern.exec(cleanLine)) !== null) {
                    const objectName = match[nameGroup];
                    // Проверяем что это не уже добавленный вызов метода
                    const existingCall = calls.find(c => c.objectCategory === category &&
                        c.objectName === objectName &&
                        c.line === actualLine);
                    if (!existingCall) {
                        calls.push({
                            caller: callerName,
                            callee: `${this.getCategoryRussianName(category)}.${objectName}`,
                            callType: CallType.MANAGER,
                            objectCategory: category,
                            objectName: objectName,
                            line: actualLine
                        });
                    }
                }
            }
        });
        return calls;
    }
    /**
     * Классифицирует вызов и возвращает информацию о нём
     */
    classifyCall(fullCall, parts, callerName, line, localProcedureNames) {
        const lowerFullCall = fullCall.toLowerCase();
        const lowerFirstPart = parts[0].toLowerCase();
        // Пропускаем ключевые слова языка
        const keywords = ['если', 'if', 'тогда', 'then', 'иначе', 'else', 'пока', 'while',
            'для', 'for', 'каждого', 'each', 'цикл', 'do', 'возврат', 'return',
            'попытка', 'try', 'исключение', 'except', 'вызватьисключение', 'raise',
            'и', 'and', 'или', 'or', 'не', 'not', 'истина', 'true', 'ложь', 'false'];
        if (keywords.includes(lowerFirstPart)) {
            return null;
        }
        // Проверяем платформенные функции
        if (parts.length === 1 && PLATFORM_FUNCTIONS.has(lowerFirstPart)) {
            return {
                caller: callerName,
                callee: fullCall,
                callType: CallType.PLATFORM,
                line
            };
        }
        // Проверяем внутренние вызовы (исключаем self-call - вызов самой себя)
        if (parts.length === 1 && localProcedureNames.has(lowerFirstPart)) {
            // Пропускаем если это объявление процедуры (caller == callee)
            if (lowerFirstPart === callerName.toLowerCase()) {
                return null;
            }
            return {
                caller: callerName,
                callee: fullCall,
                callType: CallType.INTERNAL,
                line
            };
        }
        // Проверяем вызовы объектов конфигурации
        if (parts.length >= 2) {
            const configCategory = this.getConfigCategory(parts[0]);
            if (configCategory) {
                return {
                    caller: callerName,
                    callee: fullCall,
                    callType: CallType.MANAGER,
                    moduleName: parts[0],
                    objectCategory: configCategory,
                    objectName: parts[1],
                    line
                };
            }
            // Проверяем вызов общего модуля (предполагаем что это общий модуль если не распознали как объект)
            // Паттерн: ИмяМодуля.ИмяМетода
            if (parts.length === 2) {
                return {
                    caller: callerName,
                    callee: fullCall,
                    callType: CallType.COMMON_MODULE,
                    moduleName: parts[0],
                    line
                };
            }
        }
        // Если одна часть и это не локальная процедура - возможно вызов функции без точки
        if (parts.length === 1 && !localProcedureNames.has(lowerFirstPart)) {
            return {
                caller: callerName,
                callee: fullCall,
                callType: CallType.UNKNOWN,
                line
            };
        }
        return null;
    }
    /**
     * Определяет категорию объекта конфигурации по имени коллекции
     */
    getConfigCategory(collectionName) {
        const lower = collectionName.toLowerCase();
        const mapping = {
            'справочники': ConfigObjectCategory.CATALOG,
            'catalogs': ConfigObjectCategory.CATALOG,
            'документы': ConfigObjectCategory.DOCUMENT,
            'documents': ConfigObjectCategory.DOCUMENT,
            'регистрынакопления': ConfigObjectCategory.REGISTER_ACCUMULATION,
            'accumulationregisters': ConfigObjectCategory.REGISTER_ACCUMULATION,
            'регистрысведений': ConfigObjectCategory.REGISTER_INFORMATION,
            'informationregisters': ConfigObjectCategory.REGISTER_INFORMATION,
            'регистрыбухгалтерии': ConfigObjectCategory.REGISTER_ACCOUNTING,
            'accountingregisters': ConfigObjectCategory.REGISTER_ACCOUNTING,
            'обработки': ConfigObjectCategory.DATA_PROCESSOR,
            'dataprocessors': ConfigObjectCategory.DATA_PROCESSOR,
            'отчеты': ConfigObjectCategory.REPORT,
            'reports': ConfigObjectCategory.REPORT,
            'перечисления': ConfigObjectCategory.ENUM,
            'enums': ConfigObjectCategory.ENUM,
            'планысчетов': ConfigObjectCategory.CHART_OF_ACCOUNTS,
            'chartsofaccounts': ConfigObjectCategory.CHART_OF_ACCOUNTS,
            'планывидовхарактеристик': ConfigObjectCategory.CHART_OF_CHARACTERISTIC_TYPES,
            'chartsofcharacteristictypes': ConfigObjectCategory.CHART_OF_CHARACTERISTIC_TYPES,
            'константы': ConfigObjectCategory.CONSTANT,
            'constants': ConfigObjectCategory.CONSTANT,
            'планыобмена': ConfigObjectCategory.EXCHANGE_PLAN,
            'exchangeplans': ConfigObjectCategory.EXCHANGE_PLAN,
            'бизнеспроцессы': ConfigObjectCategory.BUSINESS_PROCESS,
            'businessprocesses': ConfigObjectCategory.BUSINESS_PROCESS,
            'задачи': ConfigObjectCategory.TASK,
            'tasks': ConfigObjectCategory.TASK,
        };
        return mapping[lower];
    }
    /**
     * Возвращает русское название категории
     */
    getCategoryRussianName(category) {
        return category;
    }
    /**
     * Удаляет строковые литералы из строки кода
     */
    removeStringLiterals(line) {
        // Удаляем строки в двойных кавычках
        return line.replace(/"[^"]*"/g, '""').replace(/'[^']*'/g, "''");
    }
    /**
     * Добавляет вызовы в общие списки графа
     */
    addCallsToGraph(calls, graph) {
        for (const call of calls) {
            graph.allCalls.push(call);
            if (call.callType === CallType.INTERNAL) {
                graph.internalCalls.push(call);
            }
            else if (call.callType === CallType.COMMON_MODULE) {
                graph.externalCalls.push(call);
                if (call.moduleName) {
                    graph.usedCommonModules.add(call.moduleName);
                }
            }
            else if (call.objectCategory) {
                graph.configObjectCalls.push(call);
                if (!graph.usedConfigObjects.has(call.objectCategory)) {
                    graph.usedConfigObjects.set(call.objectCategory, new Set());
                }
                if (call.objectName) {
                    graph.usedConfigObjects.get(call.objectCategory).add(call.objectName);
                }
            }
            else if (call.callType !== CallType.PLATFORM && call.callType !== CallType.CONSTRUCTOR) {
                graph.externalCalls.push(call);
            }
        }
    }
    /**
     * Генерирует текстовое представление графа вызовов для документации
     * @param graph Граф вызовов
     * @returns Markdown текст с деревом вызовов
     */
    generateCallGraphMarkdown(graph) {
        let markdown = '';
        // Точки входа (экспортируемые)
        if (graph.entryPoints.length > 0) {
            markdown += '## Точки входа (экспортируемые)\n\n';
            for (const entryPoint of graph.entryPoints) {
                const proc = graph.procedures.get(entryPoint);
                if (proc) {
                    markdown += `### ${proc.type === 'function' ? 'Функция' : 'Процедура'} ${proc.name}`;
                    if (proc.parameters.length > 0) {
                        markdown += `(${proc.parameters.join(', ')})`;
                    }
                    markdown += '\n';
                    if (proc.comment) {
                        markdown += `> ${proc.comment.replace(/\n/g, '\n> ')}\n`;
                    }
                    markdown += '\n';
                    // Дерево вызовов
                    if (proc.calls.length > 0) {
                        markdown += this.generateCallTree(proc.name, graph, 0, new Set());
                    }
                    markdown += '\n';
                }
            }
        }
        // Используемые общие модули
        if (graph.usedCommonModules.size > 0) {
            markdown += '## Используемые общие модули\n\n';
            for (const moduleName of Array.from(graph.usedCommonModules).sort()) {
                markdown += `- ${moduleName}\n`;
            }
            markdown += '\n';
        }
        // Используемые объекты конфигурации
        if (graph.usedConfigObjects.size > 0) {
            markdown += '## Связи с объектами конфигурации\n\n';
            for (const [category, objects] of graph.usedConfigObjects) {
                if (objects.size > 0) {
                    markdown += `### ${category}\n`;
                    for (const objName of Array.from(objects).sort()) {
                        markdown += `- ${objName}\n`;
                    }
                    markdown += '\n';
                }
            }
        }
        // Внутренние зависимости
        const internalDeps = new Map();
        for (const call of graph.internalCalls) {
            if (!internalDeps.has(call.caller)) {
                internalDeps.set(call.caller, new Set());
            }
            internalDeps.get(call.caller).add(call.callee);
        }
        if (internalDeps.size > 0) {
            markdown += '## Внутренние зависимости\n\n';
            markdown += '```\n';
            for (const [caller, callees] of internalDeps) {
                markdown += `${caller}\n`;
                const calleesArray = Array.from(callees);
                for (let i = 0; i < calleesArray.length; i++) {
                    const isLast = i === calleesArray.length - 1;
                    markdown += `${isLast ? '└── ' : '├── '}${calleesArray[i]}\n`;
                }
            }
            markdown += '```\n\n';
        }
        return markdown;
    }
    /**
     * Генерирует дерево вызовов для одной процедуры
     */
    generateCallTree(procName, graph, depth, visited) {
        if (depth > 5 || visited.has(procName)) {
            return '';
        }
        visited.add(procName);
        const proc = graph.procedures.get(procName);
        if (!proc || proc.calls.length === 0) {
            return '';
        }
        let tree = '';
        const indent = '    '.repeat(depth);
        // Группируем вызовы по типу
        const internalCalls = proc.calls.filter(c => c.callType === CallType.INTERNAL);
        const externalCalls = proc.calls.filter(c => c.callType === CallType.COMMON_MODULE ||
            c.callType === CallType.MANAGER);
        if (internalCalls.length > 0) {
            tree += `${indent}├── Внутренние вызовы:\n`;
            const uniqueCalls = [...new Set(internalCalls.map(c => c.callee))];
            for (const callee of uniqueCalls) {
                tree += `${indent}│   ├── ${callee}\n`;
                tree += this.generateCallTree(callee, graph, depth + 1, new Set(visited));
            }
        }
        if (externalCalls.length > 0) {
            tree += `${indent}├── Внешние вызовы:\n`;
            const uniqueCalls = [...new Set(externalCalls.map(c => c.callee))];
            for (const callee of uniqueCalls) {
                tree += `${indent}│   └── ${callee}\n`;
            }
        }
        return tree;
    }
    /**
     * Генерирует краткую сводку для промпта LLM
     */
    generateContextForLLM(graph) {
        let context = '=== ГРАФ ВЫЗОВОВ МОДУЛЯ ===\n\n';
        // Статистика
        context += `Процедур: ${Array.from(graph.procedures.values()).filter(p => p.type === 'procedure').length}\n`;
        context += `Функций: ${Array.from(graph.procedures.values()).filter(p => p.type === 'function').length}\n`;
        context += `Экспортируемых: ${graph.entryPoints.length}\n`;
        context += `Внутренних вызовов: ${graph.internalCalls.length}\n`;
        context += `Внешних вызовов: ${graph.externalCalls.length}\n`;
        context += `Вызовов объектов конфигурации: ${graph.configObjectCalls.length}\n\n`;
        // Точки входа
        if (graph.entryPoints.length > 0) {
            context += '### Экспортируемые процедуры/функции (API модуля):\n';
            for (const name of graph.entryPoints) {
                const proc = graph.procedures.get(name);
                if (proc) {
                    context += `- ${proc.type === 'function' ? 'Функция' : 'Процедура'} ${name}`;
                    if (proc.parameters.length > 0) {
                        context += `(${proc.parameters.join(', ')})`;
                    }
                    context += '\n';
                }
            }
            context += '\n';
        }
        // Используемые общие модули
        if (graph.usedCommonModules.size > 0) {
            context += '### Зависимости от общих модулей:\n';
            for (const mod of graph.usedCommonModules) {
                context += `- ${mod}\n`;
            }
            context += '\n';
        }
        // Используемые объекты конфигурации
        if (graph.usedConfigObjects.size > 0) {
            context += '### Связи с объектами конфигурации:\n';
            for (const [category, objects] of graph.usedConfigObjects) {
                context += `\n#### ${category}:\n`;
                for (const obj of objects) {
                    context += `- ${obj}\n`;
                }
            }
            context += '\n';
        }
        // Цепочки вызовов для каждой экспортируемой процедуры
        if (graph.entryPoints.length > 0) {
            context += '### Цепочки вызовов:\n\n';
            for (const entryPoint of graph.entryPoints) {
                const proc = graph.procedures.get(entryPoint);
                if (proc && proc.calls.length > 0) {
                    context += `${entryPoint}():\n`;
                    const uniqueInternalCalls = [...new Set(proc.internalCalls)];
                    const uniqueExternalCalls = [...new Set(proc.externalCalls.map(c => c.callee))];
                    for (const call of uniqueInternalCalls) {
                        context += `  → ${call}() [внутренний]\n`;
                    }
                    for (const call of uniqueExternalCalls) {
                        context += `  → ${call} [внешний]\n`;
                    }
                    context += '\n';
                }
            }
        }
        return context;
    }
    /**
     * Генерирует Mermaid диаграмму графа вызовов процедур/функций
     */
    generateCallGraphMermaid(graph, moduleName) {
        const lines = ['graph TD'];
        const name = moduleName || graph.filePath?.split(/[/\\]/).pop()?.replace('.bsl', '') || 'Module';
        // Helper to create full ID from label (replace spaces with underscores)
        const makeId = (label) => label.replace(/[^a-zA-Zа-яА-ЯёЁ0-9]/g, '_').replace(/_+/g, '_');
        // Map to store procName -> id for connections
        const procIdMap = new Map();
        // Собираем все процедуры
        const procedures = Array.from(graph.procedures.entries());
        if (procedures.length === 0) {
            const emptyLabel = `Модуль ${name}`;
            const emptyId = makeId(emptyLabel);
            return `graph TD\n    ${emptyId}["${emptyLabel}"]\n    ${emptyId} -->|нет процедур| ${emptyId}`;
        }
        // Группируем: экспортные и внутренние
        const exportProcs = procedures.filter(([_, info]) => info.isExport);
        const internalProcs = procedures.filter(([_, info]) => !info.isExport);
        // Subgraph для экспортных (точки входа)
        if (exportProcs.length > 0) {
            lines.push(`    subgraph export["Экспортные (точки входа)"]`);
            for (const [procName, info] of exportProcs) {
                const typeLabel = info.type === 'function' ? 'Функция' : 'Процедура';
                const label = `${typeLabel} ${procName} Экспорт`;
                const id = makeId(label);
                procIdMap.set(procName, id);
                const shape = info.type === 'function' ? `(["${label}"])` : `["${label}"]`;
                lines.push(`        ${id}${shape}`);
            }
            lines.push('    end');
        }
        // Subgraph для внутренних
        if (internalProcs.length > 0) {
            lines.push(`    subgraph internal["Внутренние"]`);
            for (const [procName, info] of internalProcs) {
                const typeLabel = info.type === 'function' ? 'Функция' : 'Процедура';
                const label = `${typeLabel} ${procName}`;
                const id = makeId(label);
                procIdMap.set(procName, id);
                const shape = info.type === 'function' ? `(["${label}"])` : `["${label}"]`;
                lines.push(`        ${id}${shape}`);
            }
            lines.push('    end');
        }
        // Добавляем связи (кто кого вызывает)
        const addedEdges = new Set();
        for (const [procName, info] of procedures) {
            const fromId = procIdMap.get(procName);
            if (!fromId)
                continue;
            // Внутренние вызовы
            for (const callName of info.internalCalls) {
                const toId = procIdMap.get(callName);
                // Проверяем что вызываемая процедура существует в графе
                if (toId && graph.procedures.has(callName)) {
                    const edgeKey = `${fromId}->${toId}`;
                    if (!addedEdges.has(edgeKey)) {
                        lines.push(`    ${fromId} --> ${toId}`);
                        addedEdges.add(edgeKey);
                    }
                }
            }
        }
        // Если нет связей - добавим пояснение
        if (addedEdges.size === 0 && procedures.length > 1) {
            lines.push(`    note["Процедуры не вызывают друг друга"]`);
        }
        return lines.join('\n');
    }
}
/**
 * Singleton instance
 */
let callGraphAnalyzerInstance = null;
/**
 * Получает или создаёт экземпляр анализатора графа вызовов
 */
export async function getBSLCallGraphAnalyzer() {
    if (!callGraphAnalyzerInstance) {
        callGraphAnalyzerInstance = new BSLCallGraphAnalyzer();
        await callGraphAnalyzerInstance.initialize();
    }
    return callGraphAnalyzerInstance;
}
//# sourceMappingURL=bsl-call-graph-analyzer.js.map