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
/**
 * Тип вызова
 */
export declare enum CallType {
    /** Вызов процедуры/функции в этом же модуле */
    INTERNAL = "internal",
    /** Вызов общего модуля (ОбщийМодуль.Функция()) */
    COMMON_MODULE = "common_module",
    /** Вызов менеджера объекта (Справочники.Товары.НайтиПоКоду()) */
    MANAGER = "manager",
    /** Вызов метода объекта (Объект.Метод()) */
    OBJECT_METHOD = "object_method",
    /** Вызов платформенной функции (Сообщить(), ТекущаяДата()) */
    PLATFORM = "platform",
    /** Конструктор (Новый Запрос, Новый Структура) */
    CONSTRUCTOR = "constructor",
    /** Неопределённый тип */
    UNKNOWN = "unknown"
}
/**
 * Категория объекта конфигурации
 */
export declare enum ConfigObjectCategory {
    CATALOG = "\u0421\u043F\u0440\u0430\u0432\u043E\u0447\u043D\u0438\u043A",
    DOCUMENT = "\u0414\u043E\u043A\u0443\u043C\u0435\u043D\u0442",
    REGISTER_ACCUMULATION = "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u041D\u0430\u043A\u043E\u043F\u043B\u0435\u043D\u0438\u044F",
    REGISTER_INFORMATION = "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0421\u0432\u0435\u0434\u0435\u043D\u0438\u0439",
    REGISTER_ACCOUNTING = "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0411\u0443\u0445\u0433\u0430\u043B\u0442\u0435\u0440\u0438\u0438",
    REGISTER_CALCULATION = "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0420\u0430\u0441\u0447\u0435\u0442\u0430",
    DATA_PROCESSOR = "\u041E\u0431\u0440\u0430\u0431\u043E\u0442\u043A\u0430",
    REPORT = "\u041E\u0442\u0447\u0435\u0442",
    COMMON_MODULE = "\u041E\u0431\u0449\u0438\u0439\u041C\u043E\u0434\u0443\u043B\u044C",
    ENUM = "\u041F\u0435\u0440\u0435\u0447\u0438\u0441\u043B\u0435\u043D\u0438\u0435",
    CHART_OF_ACCOUNTS = "\u041F\u043B\u0430\u043D\u0421\u0447\u0435\u0442\u043E\u0432",
    CHART_OF_CHARACTERISTIC_TYPES = "\u041F\u043B\u0430\u043D\u0412\u0438\u0434\u043E\u0432\u0425\u0430\u0440\u0430\u043A\u0442\u0435\u0440\u0438\u0441\u0442\u0438\u043A",
    CONSTANT = "\u041A\u043E\u043D\u0441\u0442\u0430\u043D\u0442\u0430",
    EXCHANGE_PLAN = "\u041F\u043B\u0430\u043D\u041E\u0431\u043C\u0435\u043D\u0430",
    BUSINESS_PROCESS = "\u0411\u0438\u0437\u043D\u0435\u0441\u041F\u0440\u043E\u0446\u0435\u0441\u0441",
    TASK = "\u0417\u0430\u0434\u0430\u0447\u0430",
    SEQUENCE = "\u041F\u043E\u0441\u043B\u0435\u0434\u043E\u0432\u0430\u0442\u0435\u043B\u044C\u043D\u043E\u0441\u0442\u044C",
    HTTP_SERVICE = "HTTP\u0421\u0435\u0440\u0432\u0438\u0441",
    WEB_SERVICE = "Web\u0421\u0435\u0440\u0432\u0438\u0441",
    UNKNOWN = "\u041D\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043D\u043E"
}
/**
 * Информация о вызове
 */
export interface CallInfo {
    /** Имя вызывающей процедуры/функции */
    caller: string;
    /** Полное имя вызываемого метода */
    callee: string;
    /** Тип вызова */
    callType: CallType;
    /** Имя модуля/объекта (для внешних вызовов) */
    moduleName?: string;
    /** Категория объекта конфигурации */
    objectCategory?: ConfigObjectCategory;
    /** Имя объекта конфигурации */
    objectName?: string;
    /** Номер строки */
    line: number;
    /** Параметры вызова (если удалось извлечь) */
    parameters?: string[];
}
/**
 * Информация о процедуре/функции с вызовами
 */
export interface ProcedureCallInfo {
    /** Имя процедуры/функции */
    name: string;
    /** Тип: процедура или функция */
    type: 'procedure' | 'function';
    /** Экспортируется? */
    isExport: boolean;
    /** Параметры */
    parameters: string[];
    /** Начальная строка */
    startLine: number;
    /** Конечная строка */
    endLine: number;
    /** Комментарий/описание */
    comment?: string;
    /** Вызовы внутри этой процедуры/функции */
    calls: CallInfo[];
    /** Внутренние вызовы (в этом же модуле) */
    internalCalls: string[];
    /** Внешние вызовы */
    externalCalls: CallInfo[];
    /** Вызовы объектов конфигурации */
    configObjectCalls: CallInfo[];
}
/**
 * Граф вызовов модуля
 */
export interface ModuleCallGraph {
    /** Путь к файлу */
    filePath?: string;
    /** Все процедуры и функции с информацией о вызовах */
    procedures: Map<string, ProcedureCallInfo>;
    /** Все вызовы в модуле */
    allCalls: CallInfo[];
    /** Внутренние вызовы (между процедурами модуля) */
    internalCalls: CallInfo[];
    /** Внешние вызовы (общие модули, менеджеры) */
    externalCalls: CallInfo[];
    /** Вызовы объектов конфигурации */
    configObjectCalls: CallInfo[];
    /** Точки входа (экспортируемые процедуры/функции) */
    entryPoints: string[];
    /** Используемые общие модули */
    usedCommonModules: Set<string>;
    /** Используемые объекты конфигурации */
    usedConfigObjects: Map<ConfigObjectCategory, Set<string>>;
}
/**
 * Анализатор графа вызовов BSL кода
 */
export declare class BSLCallGraphAnalyzer {
    private treesitterAnalyzer?;
    private initialized;
    /**
     * Инициализирует анализатор
     */
    initialize(): Promise<void>;
    /**
     * Анализирует граф вызовов BSL кода
     * @param code BSL исходный код
     * @param filePath Путь к файлу (опционально)
     * @returns Граф вызовов модуля
     */
    analyzeCallGraph(code: string, filePath?: string): Promise<ModuleCallGraph>;
    /**
     * Анализирует вызовы внутри процедуры/функции
     */
    private analyzeProcedure;
    /**
     * Извлекает все вызовы из тела процедуры/функции
     */
    private extractCalls;
    /**
     * Классифицирует вызов и возвращает информацию о нём
     */
    private classifyCall;
    /**
     * Определяет категорию объекта конфигурации по имени коллекции
     */
    private getConfigCategory;
    /**
     * Возвращает русское название категории
     */
    private getCategoryRussianName;
    /**
     * Удаляет строковые литералы из строки кода
     */
    private removeStringLiterals;
    /**
     * Добавляет вызовы в общие списки графа
     */
    private addCallsToGraph;
    /**
     * Генерирует текстовое представление графа вызовов для документации
     * @param graph Граф вызовов
     * @returns Markdown текст с деревом вызовов
     */
    generateCallGraphMarkdown(graph: ModuleCallGraph): string;
    /**
     * Генерирует дерево вызовов для одной процедуры
     */
    private generateCallTree;
    /**
     * Генерирует краткую сводку для промпта LLM
     */
    generateContextForLLM(graph: ModuleCallGraph): string;
    /**
     * Генерирует Mermaid диаграмму графа вызовов процедур/функций
     */
    generateCallGraphMermaid(graph: ModuleCallGraph, moduleName?: string): string;
}
/**
 * Получает или создаёт экземпляр анализатора графа вызовов
 */
export declare function getBSLCallGraphAnalyzer(): Promise<BSLCallGraphAnalyzer>;
