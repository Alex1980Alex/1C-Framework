/**
 * BSL Lexer — Лексический анализатор для языка 1С/BSL
 *
 * Токенизирует исходный код BSL для последующего парсинга.
 * Поддерживает русские и английские ключевые слова.
 */
export var TokenType;
(function (TokenType) {
    // Литералы
    TokenType["NUMBER"] = "NUMBER";
    TokenType["STRING"] = "STRING";
    TokenType["DATE"] = "DATE";
    TokenType["BOOLEAN"] = "BOOLEAN";
    TokenType["UNDEFINED"] = "UNDEFINED";
    TokenType["NULL"] = "NULL";
    // Идентификаторы и ключевые слова
    TokenType["IDENTIFIER"] = "IDENTIFIER";
    TokenType["KEYWORD"] = "KEYWORD";
    // Операторы
    TokenType["PLUS"] = "PLUS";
    TokenType["MINUS"] = "MINUS";
    TokenType["MULTIPLY"] = "MULTIPLY";
    TokenType["DIVIDE"] = "DIVIDE";
    TokenType["MODULO"] = "MODULO";
    TokenType["ASSIGN"] = "ASSIGN";
    TokenType["EQUALS"] = "EQUALS";
    TokenType["NOT_EQUALS"] = "NOT_EQUALS";
    TokenType["LESS"] = "LESS";
    TokenType["GREATER"] = "GREATER";
    TokenType["LESS_EQ"] = "LESS_EQ";
    TokenType["GREATER_EQ"] = "GREATER_EQ";
    // Пунктуация
    TokenType["LPAREN"] = "LPAREN";
    TokenType["RPAREN"] = "RPAREN";
    TokenType["LBRACKET"] = "LBRACKET";
    TokenType["RBRACKET"] = "RBRACKET";
    TokenType["COMMA"] = "COMMA";
    TokenType["SEMICOLON"] = "SEMICOLON";
    TokenType["DOT"] = "DOT";
    TokenType["QUESTION"] = "QUESTION";
    // Специальные
    TokenType["COMMENT"] = "COMMENT";
    TokenType["PREPROCESSOR"] = "PREPROCESSOR";
    TokenType["ANNOTATION"] = "ANNOTATION";
    TokenType["NEWLINE"] = "NEWLINE";
    TokenType["EOF"] = "EOF";
})(TokenType || (TokenType = {}));
// Ключевые слова BSL (русские и английские)
export const KEYWORDS = {
    // Процедуры и функции
    "процедура": "PROCEDURE", "procedure": "PROCEDURE",
    "функция": "FUNCTION", "function": "FUNCTION",
    "конецпроцедуры": "ENDPROCEDURE", "endprocedure": "ENDPROCEDURE",
    "конецфункции": "ENDFUNCTION", "endfunction": "ENDFUNCTION",
    "возврат": "RETURN", "return": "RETURN",
    "знач": "VAL", "val": "VAL",
    "экспорт": "EXPORT", "export": "EXPORT",
    // Переменные
    "перем": "VAR", "var": "VAR",
    // Условия
    "если": "IF", "if": "IF",
    "тогда": "THEN", "then": "THEN",
    "иначеесли": "ELSEIF", "elseif": "ELSEIF", "elsif": "ELSEIF",
    "иначе": "ELSE", "else": "ELSE",
    "конецесли": "ENDIF", "endif": "ENDIF",
    // Циклы
    "для": "FOR", "for": "FOR",
    "каждого": "EACH", "each": "EACH",
    "из": "FROM", "from": "FROM",
    "по": "TO", "to": "TO",
    "пока": "WHILE", "while": "WHILE",
    "цикл": "DO", "do": "DO",
    "конеццикла": "ENDDO", "enddo": "ENDDO",
    "прервать": "BREAK", "break": "BREAK",
    "продолжить": "CONTINUE", "continue": "CONTINUE",
    // Исключения
    "попытка": "TRY", "try": "TRY",
    "исключение": "EXCEPT", "except": "EXCEPT",
    "конецпопытки": "ENDTRY", "endtry": "ENDTRY",
    "вызватьисключение": "RAISE", "raise": "RAISE",
    // Логические
    "и": "AND", "and": "AND",
    "или": "OR", "or": "OR",
    "не": "NOT", "not": "NOT",
    // Значения
    "истина": "TRUE", "true": "TRUE",
    "ложь": "FALSE", "false": "FALSE",
    "неопределено": "UNDEFINED", "undefined": "UNDEFINED",
    "null": "NULL",
    // Новый/Выполнить
    "новый": "NEW", "new": "NEW",
    "выполнить": "EXECUTE", "execute": "EXECUTE",
    // Асинхронность (OneScript 2.0+)
    "асинх": "ASYNC", "async": "ASYNC",
    "ждать": "AWAIT", "await": "AWAIT",
    // Директивы
    "использовать": "USE", "#использовать": "USE"
};
export class BSLLexer {
    source;
    position = 0;
    line = 1;
    column = 1;
    tokens = [];
    errors = [];
    constructor(source) {
        this.source = source;
    }
    tokenize() {
        while (!this.isAtEnd()) {
            this.skipWhitespace();
            if (this.isAtEnd())
                break;
            const char = this.peek();
            // Комментарии
            if (char === "/" && this.peekNext() === "/") {
                this.scanLineComment();
                continue;
            }
            // Препроцессор
            if (char === "#") {
                this.scanPreprocessor();
                continue;
            }
            // Аннотации
            if (char === "&") {
                this.scanAnnotation();
                continue;
            }
            // Строки
            if (char === '"') {
                this.scanString();
                continue;
            }
            // Числа
            if (this.isDigit(char)) {
                this.scanNumber();
                continue;
            }
            // Даты
            if (char === "'") {
                this.scanDate();
                continue;
            }
            // Идентификаторы и ключевые слова
            if (this.isAlpha(char) || char === "_") {
                this.scanIdentifier();
                continue;
            }
            // Операторы и пунктуация
            this.scanOperator();
        }
        this.addToken(TokenType.EOF, "");
        return { tokens: this.tokens, errors: this.errors };
    }
    scanLineComment() {
        const start = this.position;
        this.advance(); // /
        this.advance(); // /
        while (!this.isAtEnd() && this.peek() !== "\n") {
            this.advance();
        }
        const value = this.source.substring(start, this.position);
        this.addToken(TokenType.COMMENT, value);
    }
    scanPreprocessor() {
        const start = this.position;
        this.advance(); // #
        // Читаем директиву
        while (!this.isAtEnd() && this.isAlphaNumeric(this.peek())) {
            this.advance();
        }
        // Для многострочных директив (#Если ... #КонецЕсли)
        const directive = this.source.substring(start, this.position).toLowerCase();
        // Читаем до конца строки для простых директив
        if (!directive.includes("если") && !directive.includes("if")) {
            while (!this.isAtEnd() && this.peek() !== "\n") {
                this.advance();
            }
        }
        const value = this.source.substring(start, this.position);
        this.addToken(TokenType.PREPROCESSOR, value);
    }
    scanAnnotation() {
        const start = this.position;
        this.advance(); // &
        while (!this.isAtEnd() && this.isAlphaNumeric(this.peek())) {
            this.advance();
        }
        // Аннотация может иметь параметры в скобках
        if (this.peek() === "(") {
            let depth = 1;
            this.advance();
            while (!this.isAtEnd() && depth > 0) {
                if (this.peek() === "(")
                    depth++;
                if (this.peek() === ")")
                    depth--;
                this.advance();
            }
        }
        const value = this.source.substring(start, this.position);
        this.addToken(TokenType.ANNOTATION, value);
    }
    scanString() {
        const startLine = this.line;
        const startColumn = this.column;
        const start = this.position;
        this.advance(); // Открывающая "
        while (!this.isAtEnd()) {
            if (this.peek() === '"') {
                if (this.peekNext() === '"') {
                    // Экранированная кавычка ""
                    this.advance();
                    this.advance();
                }
                else {
                    // Конец строки
                    break;
                }
            }
            else if (this.peek() === "\n") {
                // Многострочная строка
                this.line++;
                this.column = 0;
                this.advance();
            }
            else {
                this.advance();
            }
        }
        if (this.isAtEnd()) {
            this.addError("Незакрытая строка", startLine, startColumn, start);
            return;
        }
        this.advance(); // Закрывающая "
        const value = this.source.substring(start, this.position);
        this.addToken(TokenType.STRING, value);
    }
    scanNumber() {
        const start = this.position;
        while (this.isDigit(this.peek())) {
            this.advance();
        }
        // Десятичная часть
        if (this.peek() === "." && this.isDigit(this.peekNext())) {
            this.advance(); // .
            while (this.isDigit(this.peek())) {
                this.advance();
            }
        }
        const value = this.source.substring(start, this.position);
        this.addToken(TokenType.NUMBER, value);
    }
    scanDate() {
        const startLine = this.line;
        const startColumn = this.column;
        const start = this.position;
        this.advance(); // Открывающая '
        while (!this.isAtEnd() && this.peek() !== "'") {
            this.advance();
        }
        if (this.isAtEnd()) {
            this.addError("Незакрытый литерал даты", startLine, startColumn, start);
            return;
        }
        this.advance(); // Закрывающая '
        const value = this.source.substring(start, this.position);
        this.addToken(TokenType.DATE, value);
    }
    scanIdentifier() {
        const start = this.position;
        while (this.isAlphaNumeric(this.peek())) {
            this.advance();
        }
        const value = this.source.substring(start, this.position);
        const lowerValue = value.toLowerCase();
        // Проверяем на ключевое слово
        if (KEYWORDS[lowerValue]) {
            const keyword = KEYWORDS[lowerValue];
            // Специальные случаи: булевы значения
            if (keyword === "TRUE" || keyword === "FALSE") {
                this.addToken(TokenType.BOOLEAN, value, keyword);
            }
            else if (keyword === "UNDEFINED") {
                this.addToken(TokenType.UNDEFINED, value, keyword);
            }
            else if (keyword === "NULL") {
                this.addToken(TokenType.NULL, value, keyword);
            }
            else {
                this.addToken(TokenType.KEYWORD, value, keyword);
            }
        }
        else {
            this.addToken(TokenType.IDENTIFIER, value);
        }
    }
    scanOperator() {
        const char = this.advance();
        switch (char) {
            case "+":
                this.addToken(TokenType.PLUS, "+");
                break;
            case "-":
                this.addToken(TokenType.MINUS, "-");
                break;
            case "*":
                this.addToken(TokenType.MULTIPLY, "*");
                break;
            case "/":
                this.addToken(TokenType.DIVIDE, "/");
                break;
            case "%":
                this.addToken(TokenType.MODULO, "%");
                break;
            case "(":
                this.addToken(TokenType.LPAREN, "(");
                break;
            case ")":
                this.addToken(TokenType.RPAREN, ")");
                break;
            case "[":
                this.addToken(TokenType.LBRACKET, "[");
                break;
            case "]":
                this.addToken(TokenType.RBRACKET, "]");
                break;
            case ",":
                this.addToken(TokenType.COMMA, ",");
                break;
            case ";":
                this.addToken(TokenType.SEMICOLON, ";");
                break;
            case ".":
                this.addToken(TokenType.DOT, ".");
                break;
            case "?":
                this.addToken(TokenType.QUESTION, "?");
                break;
            case "=":
                this.addToken(TokenType.EQUALS, "=");
                break;
            case "<":
                if (this.match(">")) {
                    this.addToken(TokenType.NOT_EQUALS, "<>");
                }
                else if (this.match("=")) {
                    this.addToken(TokenType.LESS_EQ, "<=");
                }
                else {
                    this.addToken(TokenType.LESS, "<");
                }
                break;
            case ">":
                if (this.match("=")) {
                    this.addToken(TokenType.GREATER_EQ, ">=");
                }
                else {
                    this.addToken(TokenType.GREATER, ">");
                }
                break;
            case "\n":
                this.addToken(TokenType.NEWLINE, "\n");
                this.line++;
                this.column = 1;
                break;
            case "\r":
                // Игнорируем \r (Windows line endings)
                break;
            default:
                this.addError(`Неожиданный символ: ${char}`, this.line, this.column - 1, this.position - 1);
        }
    }
    // === Вспомогательные методы ===
    peek() {
        if (this.isAtEnd())
            return "\0";
        return this.source[this.position];
    }
    peekNext() {
        if (this.position + 1 >= this.source.length)
            return "\0";
        return this.source[this.position + 1];
    }
    advance() {
        const char = this.source[this.position++];
        this.column++;
        return char;
    }
    match(expected) {
        if (this.isAtEnd())
            return false;
        if (this.source[this.position] !== expected)
            return false;
        this.position++;
        this.column++;
        return true;
    }
    isAtEnd() {
        return this.position >= this.source.length;
    }
    isDigit(char) {
        return char >= "0" && char <= "9";
    }
    isAlpha(char) {
        return ((char >= "a" && char <= "z") ||
            (char >= "A" && char <= "Z") ||
            (char >= "а" && char <= "я") ||
            (char >= "А" && char <= "Я") ||
            char === "ё" || char === "Ё" ||
            char === "_");
    }
    isAlphaNumeric(char) {
        return this.isAlpha(char) || this.isDigit(char);
    }
    skipWhitespace() {
        while (!this.isAtEnd()) {
            const char = this.peek();
            if (char === " " || char === "\t") {
                this.advance();
            }
            else {
                break;
            }
        }
    }
    addToken(type, value, keyword) {
        this.tokens.push({
            type,
            value,
            keyword,
            line: this.line,
            column: this.column - value.length,
            position: this.position - value.length
        });
    }
    addError(message, line, column, position) {
        this.errors.push({ message, line, column, position });
    }
}
// === Экспорт для тестирования ===
export function tokenize(source) {
    const lexer = new BSLLexer(source);
    return lexer.tokenize();
}
//# sourceMappingURL=lexer.js.map