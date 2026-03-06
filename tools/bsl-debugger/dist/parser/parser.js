/**
 * BSL Parser — Синтаксический анализатор для языка 1С/BSL
 *
 * Преобразует последовательность токенов в AST.
 */
import { TokenType, BSLLexer } from "./lexer.js";
export class BSLParser {
    tokens = [];
    current = 0;
    errors = [];
    parse(source) {
        const lexer = new BSLLexer(source);
        const { tokens, errors: lexerErrors } = lexer.tokenize();
        if (lexerErrors.length > 0) {
            return {
                ast: null,
                errors: lexerErrors.map(e => ({
                    message: e.message,
                    line: e.line,
                    column: e.column
                }))
            };
        }
        // Фильтруем комментарии и переносы строк для парсинга
        this.tokens = tokens.filter(t => t.type !== TokenType.COMMENT &&
            t.type !== TokenType.NEWLINE);
        this.current = 0;
        this.errors = [];
        try {
            const ast = this.parseModule();
            return { ast, errors: this.errors };
        }
        catch (error) {
            return { ast: null, errors: this.errors };
        }
    }
    // === Module ===
    parseModule() {
        const statements = [];
        const procedures = [];
        const functions = [];
        const variables = [];
        const uses = [];
        const annotations = [];
        const startToken = this.peek();
        while (!this.isAtEnd()) {
            // Пропускаем препроцессор
            if (this.check(TokenType.PREPROCESSOR)) {
                this.advance();
                continue;
            }
            // Аннотации
            if (this.check(TokenType.ANNOTATION)) {
                annotations.push(this.parseAnnotation());
                continue;
            }
            // Директива Использовать
            if (this.checkKeyword("USE")) {
                uses.push(this.parseUseDirective());
                continue;
            }
            // Переменные модуля
            if (this.checkKeyword("VAR")) {
                variables.push(this.parseVariableDeclaration());
                continue;
            }
            // Процедуры
            if (this.checkKeyword("PROCEDURE") || this.checkKeyword("ASYNC")) {
                const isAsync = this.checkKeyword("ASYNC");
                if (isAsync)
                    this.advance();
                if (this.checkKeyword("PROCEDURE")) {
                    procedures.push(this.parseProcedure(isAsync, annotations.splice(0)));
                    continue;
                }
                if (this.checkKeyword("FUNCTION")) {
                    functions.push(this.parseFunction(isAsync, annotations.splice(0)));
                    continue;
                }
            }
            // Функции
            if (this.checkKeyword("FUNCTION")) {
                functions.push(this.parseFunction(false, annotations.splice(0)));
                continue;
            }
            // Statements модуля (код вне процедур)
            const stmt = this.parseStatement();
            if (stmt) {
                statements.push(stmt);
            }
        }
        return {
            type: "Module",
            statements,
            procedures,
            functions,
            variables,
            uses,
            annotations,
            location: this.makeRange(startToken, this.previous())
        };
    }
    // === Declarations ===
    parseAnnotation() {
        const token = this.advance(); // @annotation
        const name = token.value.substring(1); // Убираем &
        let parameters;
        // Параметры уже включены в токен аннотации
        // Для упрощения не парсим их отдельно
        return {
            type: "Annotation",
            name,
            parameters,
            location: this.makeRange(token, token)
        };
    }
    parseUseDirective() {
        const start = this.advance(); // USE / Использовать
        const library = this.advance(); // имя библиотеки
        return {
            type: "UseDirective",
            library: library.value,
            location: this.makeRange(start, library)
        };
    }
    parseVariableDeclaration() {
        const start = this.advance(); // VAR / Перем
        const nameToken = this.consume(TokenType.IDENTIFIER, "Ожидается имя переменной");
        let isExport = false;
        if (this.checkKeyword("EXPORT")) {
            this.advance();
            isExport = true;
        }
        let initializer;
        if (this.match(TokenType.EQUALS)) {
            initializer = this.parseExpression();
        }
        this.matchSemicolon();
        return {
            type: "VariableDeclaration",
            name: nameToken.value,
            isExport,
            initializer,
            location: this.makeRange(start, this.previous())
        };
    }
    parseProcedure(isAsync, annotations) {
        const start = this.advance(); // PROCEDURE
        const nameToken = this.consume(TokenType.IDENTIFIER, "Ожидается имя процедуры");
        this.consume(TokenType.LPAREN, "Ожидается '('");
        const parameters = this.parseParameters();
        this.consume(TokenType.RPAREN, "Ожидается ')'");
        let isExport = false;
        if (this.checkKeyword("EXPORT")) {
            this.advance();
            isExport = true;
        }
        const { body, localVariables } = this.parseBody("ENDPROCEDURE");
        return {
            type: "ProcedureDeclaration",
            name: nameToken.value,
            parameters,
            isExport,
            isAsync,
            body,
            annotations,
            localVariables,
            location: this.makeRange(start, this.previous())
        };
    }
    parseFunction(isAsync, annotations) {
        const start = this.advance(); // FUNCTION
        const nameToken = this.consume(TokenType.IDENTIFIER, "Ожидается имя функции");
        this.consume(TokenType.LPAREN, "Ожидается '('");
        const parameters = this.parseParameters();
        this.consume(TokenType.RPAREN, "Ожидается ')'");
        let isExport = false;
        if (this.checkKeyword("EXPORT")) {
            this.advance();
            isExport = true;
        }
        const { body, localVariables } = this.parseBody("ENDFUNCTION");
        return {
            type: "FunctionDeclaration",
            name: nameToken.value,
            parameters,
            isExport,
            isAsync,
            body,
            annotations,
            localVariables,
            location: this.makeRange(start, this.previous())
        };
    }
    parseParameters() {
        const params = [];
        if (this.check(TokenType.RPAREN)) {
            return params;
        }
        do {
            const start = this.peek();
            let isByValue = false;
            if (this.checkKeyword("VAL")) {
                this.advance();
                isByValue = true;
            }
            const nameToken = this.consume(TokenType.IDENTIFIER, "Ожидается имя параметра");
            let defaultValue;
            if (this.match(TokenType.EQUALS)) {
                defaultValue = this.parseExpression();
            }
            params.push({
                type: "ParameterDeclaration",
                name: nameToken.value,
                isByValue,
                defaultValue,
                location: this.makeRange(start, this.previous())
            });
        } while (this.match(TokenType.COMMA));
        return params;
    }
    parseBody(endKeyword) {
        const body = [];
        const localVariables = [];
        while (!this.isAtEnd() && !this.checkKeyword(endKeyword)) {
            // Локальные переменные
            if (this.checkKeyword("VAR")) {
                localVariables.push(this.parseVariableDeclaration());
                continue;
            }
            const stmt = this.parseStatement();
            if (stmt) {
                body.push(stmt);
            }
        }
        this.consumeKeyword(endKeyword, `Ожидается ${endKeyword}`);
        return { body, localVariables };
    }
    // === Statements ===
    parseStatement() {
        // Пропускаем точки с запятой
        if (this.match(TokenType.SEMICOLON)) {
            return null;
        }
        if (this.checkKeyword("IF")) {
            return this.parseIfStatement();
        }
        if (this.checkKeyword("FOR")) {
            return this.parseForStatement();
        }
        if (this.checkKeyword("WHILE")) {
            return this.parseWhileStatement();
        }
        if (this.checkKeyword("TRY")) {
            return this.parseTryStatement();
        }
        if (this.checkKeyword("RETURN")) {
            return this.parseReturnStatement();
        }
        if (this.checkKeyword("BREAK")) {
            return this.parseBreakStatement();
        }
        if (this.checkKeyword("CONTINUE")) {
            return this.parseContinueStatement();
        }
        if (this.checkKeyword("RAISE")) {
            return this.parseRaiseStatement();
        }
        if (this.checkKeyword("EXECUTE")) {
            return this.parseExecuteStatement();
        }
        // Assignment или Expression
        return this.parseAssignmentOrExpression();
    }
    parseIfStatement() {
        const start = this.advance(); // IF
        const condition = this.parseExpression();
        this.consumeKeyword("THEN", "Ожидается ТОГДА/THEN");
        const thenBranch = [];
        const elseIfBranches = [];
        let elseBranch;
        while (!this.isAtEnd() &&
            !this.checkKeyword("ELSEIF") &&
            !this.checkKeyword("ELSE") &&
            !this.checkKeyword("ENDIF")) {
            const stmt = this.parseStatement();
            if (stmt)
                thenBranch.push(stmt);
        }
        while (this.checkKeyword("ELSEIF")) {
            const elseIfStart = this.advance();
            const elseIfCondition = this.parseExpression();
            this.consumeKeyword("THEN", "Ожидается ТОГДА/THEN");
            const elseIfBody = [];
            while (!this.isAtEnd() &&
                !this.checkKeyword("ELSEIF") &&
                !this.checkKeyword("ELSE") &&
                !this.checkKeyword("ENDIF")) {
                const stmt = this.parseStatement();
                if (stmt)
                    elseIfBody.push(stmt);
            }
            elseIfBranches.push({
                type: "ElseIfBranch",
                condition: elseIfCondition,
                body: elseIfBody,
                location: this.makeRange(elseIfStart, this.previous())
            });
        }
        if (this.checkKeyword("ELSE")) {
            this.advance();
            elseBranch = [];
            while (!this.isAtEnd() && !this.checkKeyword("ENDIF")) {
                const stmt = this.parseStatement();
                if (stmt)
                    elseBranch.push(stmt);
            }
        }
        this.consumeKeyword("ENDIF", "Ожидается КОНЕЦЕСЛИ/ENDIF");
        return {
            type: "IfStatement",
            condition,
            thenBranch,
            elseIfBranches,
            elseBranch,
            location: this.makeRange(start, this.previous())
        };
    }
    parseForStatement() {
        const start = this.advance(); // FOR
        // Для Каждого / For Each
        if (this.checkKeyword("EACH")) {
            this.advance();
            const varToken = this.consume(TokenType.IDENTIFIER, "Ожидается имя переменной");
            this.consumeKeyword("FROM", "Ожидается ИЗ/FROM");
            const collection = this.parseExpression();
            this.consumeKeyword("DO", "Ожидается ЦИКЛ/DO");
            const body = [];
            while (!this.isAtEnd() && !this.checkKeyword("ENDDO")) {
                const stmt = this.parseStatement();
                if (stmt)
                    body.push(stmt);
            }
            this.consumeKeyword("ENDDO", "Ожидается КОНЕЦЦИКЛА/ENDDO");
            return {
                type: "ForEachStatement",
                variable: varToken.value,
                collection,
                body,
                location: this.makeRange(start, this.previous())
            };
        }
        // Обычный For
        const varToken = this.consume(TokenType.IDENTIFIER, "Ожидается имя переменной");
        this.consume(TokenType.EQUALS, "Ожидается '='");
        const startExpr = this.parseExpression();
        this.consumeKeyword("TO", "Ожидается ПО/TO");
        const endExpr = this.parseExpression();
        this.consumeKeyword("DO", "Ожидается ЦИКЛ/DO");
        const body = [];
        while (!this.isAtEnd() && !this.checkKeyword("ENDDO")) {
            const stmt = this.parseStatement();
            if (stmt)
                body.push(stmt);
        }
        this.consumeKeyword("ENDDO", "Ожидается КОНЕЦЦИКЛА/ENDDO");
        return {
            type: "ForStatement",
            variable: varToken.value,
            start: startExpr,
            end: endExpr,
            body,
            location: this.makeRange(start, this.previous())
        };
    }
    parseWhileStatement() {
        const start = this.advance(); // WHILE
        const condition = this.parseExpression();
        this.consumeKeyword("DO", "Ожидается ЦИКЛ/DO");
        const body = [];
        while (!this.isAtEnd() && !this.checkKeyword("ENDDO")) {
            const stmt = this.parseStatement();
            if (stmt)
                body.push(stmt);
        }
        this.consumeKeyword("ENDDO", "Ожидается КОНЕЦЦИКЛА/ENDDO");
        return {
            type: "WhileStatement",
            condition,
            body,
            location: this.makeRange(start, this.previous())
        };
    }
    parseTryStatement() {
        const start = this.advance(); // TRY
        const tryBlock = [];
        while (!this.isAtEnd() && !this.checkKeyword("EXCEPT")) {
            const stmt = this.parseStatement();
            if (stmt)
                tryBlock.push(stmt);
        }
        this.consumeKeyword("EXCEPT", "Ожидается ИСКЛЮЧЕНИЕ/EXCEPT");
        const exceptBlock = [];
        while (!this.isAtEnd() && !this.checkKeyword("ENDTRY")) {
            const stmt = this.parseStatement();
            if (stmt)
                exceptBlock.push(stmt);
        }
        this.consumeKeyword("ENDTRY", "Ожидается КОНЕЦПОПЫТКИ/ENDTRY");
        return {
            type: "TryStatement",
            tryBlock,
            exceptBlock,
            location: this.makeRange(start, this.previous())
        };
    }
    parseReturnStatement() {
        const start = this.advance(); // RETURN
        let value;
        if (!this.check(TokenType.SEMICOLON) && !this.checkKeyword("ENDPROCEDURE") && !this.checkKeyword("ENDFUNCTION")) {
            value = this.parseExpression();
        }
        this.matchSemicolon();
        return {
            type: "ReturnStatement",
            value,
            location: this.makeRange(start, this.previous())
        };
    }
    parseBreakStatement() {
        const token = this.advance();
        this.matchSemicolon();
        return {
            type: "BreakStatement",
            location: this.makeRange(token, this.previous())
        };
    }
    parseContinueStatement() {
        const token = this.advance();
        this.matchSemicolon();
        return {
            type: "ContinueStatement",
            location: this.makeRange(token, this.previous())
        };
    }
    parseRaiseStatement() {
        const start = this.advance(); // RAISE
        let expression;
        if (!this.check(TokenType.SEMICOLON)) {
            expression = this.parseExpression();
        }
        this.matchSemicolon();
        return {
            type: "RaiseStatement",
            expression,
            location: this.makeRange(start, this.previous())
        };
    }
    parseExecuteStatement() {
        const start = this.advance(); // EXECUTE
        this.consume(TokenType.LPAREN, "Ожидается '('");
        const expression = this.parseExpression();
        this.consume(TokenType.RPAREN, "Ожидается ')'");
        this.matchSemicolon();
        return {
            type: "ExecuteStatement",
            expression,
            location: this.makeRange(start, this.previous())
        };
    }
    parseAssignmentOrExpression() {
        const start = this.peek();
        const expr = this.parseExpression();
        if (this.match(TokenType.EQUALS)) {
            const value = this.parseExpression();
            this.matchSemicolon();
            return {
                type: "AssignmentStatement",
                target: expr,
                value,
                location: this.makeRange(start, this.previous())
            };
        }
        this.matchSemicolon();
        return {
            type: "ExpressionStatement",
            expression: expr,
            location: this.makeRange(start, this.previous())
        };
    }
    // === Expressions ===
    parseExpression() {
        return this.parseOr();
    }
    parseOr() {
        let left = this.parseAnd();
        while (this.checkKeyword("OR")) {
            this.advance();
            const right = this.parseAnd();
            left = {
                type: "BinaryExpression",
                operator: "OR",
                left,
                right,
                location: this.makeRange(left.location.start, right.location.end)
            };
        }
        return left;
    }
    parseAnd() {
        let left = this.parseNot();
        while (this.checkKeyword("AND")) {
            this.advance();
            const right = this.parseNot();
            left = {
                type: "BinaryExpression",
                operator: "AND",
                left,
                right,
                location: this.makeRange(left.location.start, right.location.end)
            };
        }
        return left;
    }
    parseNot() {
        if (this.checkKeyword("NOT")) {
            const op = this.advance();
            const operand = this.parseNot();
            return {
                type: "UnaryExpression",
                operator: "NOT",
                operand,
                location: this.makeRange(op, operand.location.end)
            };
        }
        return this.parseComparison();
    }
    parseComparison() {
        let left = this.parseAddition();
        while (this.match(TokenType.EQUALS) ||
            this.match(TokenType.NOT_EQUALS) ||
            this.match(TokenType.LESS) ||
            this.match(TokenType.GREATER) ||
            this.match(TokenType.LESS_EQ) ||
            this.match(TokenType.GREATER_EQ)) {
            const operator = this.previous().value;
            const right = this.parseAddition();
            left = {
                type: "BinaryExpression",
                operator,
                left,
                right,
                location: this.makeRange(left.location.start, right.location.end)
            };
        }
        return left;
    }
    parseAddition() {
        let left = this.parseMultiplication();
        while (this.match(TokenType.PLUS) || this.match(TokenType.MINUS)) {
            const operator = this.previous().value;
            const right = this.parseMultiplication();
            left = {
                type: "BinaryExpression",
                operator,
                left,
                right,
                location: this.makeRange(left.location.start, right.location.end)
            };
        }
        return left;
    }
    parseMultiplication() {
        let left = this.parseUnary();
        while (this.match(TokenType.MULTIPLY) ||
            this.match(TokenType.DIVIDE) ||
            this.match(TokenType.MODULO)) {
            const operator = this.previous().value;
            const right = this.parseUnary();
            left = {
                type: "BinaryExpression",
                operator,
                left,
                right,
                location: this.makeRange(left.location.start, right.location.end)
            };
        }
        return left;
    }
    parseUnary() {
        if (this.match(TokenType.MINUS)) {
            const op = this.previous();
            const operand = this.parseUnary();
            return {
                type: "UnaryExpression",
                operator: "-",
                operand,
                location: this.makeRange(op, operand.location.end)
            };
        }
        return this.parsePostfix();
    }
    parsePostfix() {
        let expr = this.parsePrimary();
        while (true) {
            if (this.match(TokenType.DOT)) {
                const property = this.consume(TokenType.IDENTIFIER, "Ожидается имя свойства");
                expr = {
                    type: "MemberExpression",
                    object: expr,
                    property: property.value,
                    location: this.makeRange(expr.location.start, property)
                };
            }
            else if (this.match(TokenType.LBRACKET)) {
                const index = this.parseExpression();
                const end = this.consume(TokenType.RBRACKET, "Ожидается ']'");
                expr = {
                    type: "IndexExpression",
                    object: expr,
                    index,
                    location: this.makeRange(expr.location.start, end)
                };
            }
            else if (this.match(TokenType.LPAREN)) {
                const args = this.parseArguments();
                const end = this.consume(TokenType.RPAREN, "Ожидается ')'");
                expr = {
                    type: "CallExpression",
                    callee: expr,
                    arguments: args,
                    location: this.makeRange(expr.location.start, end)
                };
            }
            else {
                break;
            }
        }
        return expr;
    }
    parsePrimary() {
        const token = this.peek();
        // Числа
        if (this.match(TokenType.NUMBER)) {
            return {
                type: "NumberLiteral",
                value: parseFloat(token.value),
                raw: token.value,
                location: this.makeRange(token, token)
            };
        }
        // Строки
        if (this.match(TokenType.STRING)) {
            const raw = token.value;
            // Убираем кавычки и обрабатываем экранирование
            const value = raw.slice(1, -1).replace(/""/g, '"');
            return {
                type: "StringLiteral",
                value,
                raw,
                location: this.makeRange(token, token)
            };
        }
        // Даты
        if (this.match(TokenType.DATE)) {
            const raw = token.value;
            const dateStr = raw.slice(1, -1); // Убираем кавычки
            return {
                type: "DateLiteral",
                value: new Date(dateStr),
                raw,
                location: this.makeRange(token, token)
            };
        }
        // Булевы значения
        if (this.match(TokenType.BOOLEAN)) {
            return {
                type: "BooleanLiteral",
                value: token.keyword === "TRUE",
                location: this.makeRange(token, token)
            };
        }
        // Неопределено
        if (this.match(TokenType.UNDEFINED)) {
            return {
                type: "UndefinedLiteral",
                location: this.makeRange(token, token)
            };
        }
        // Null
        if (this.match(TokenType.NULL)) {
            return {
                type: "NullLiteral",
                location: this.makeRange(token, token)
            };
        }
        // Новый
        if (this.checkKeyword("NEW")) {
            return this.parseNewExpression();
        }
        // Ждать (await)
        if (this.checkKeyword("AWAIT")) {
            this.advance();
            const expr = this.parseExpression();
            return {
                type: "AwaitExpression",
                expression: expr,
                location: this.makeRange(token, expr.location.end)
            };
        }
        // Тернарный оператор: ?(condition, then, else)
        if (this.match(TokenType.QUESTION)) {
            this.consume(TokenType.LPAREN, "Ожидается '('");
            const condition = this.parseExpression();
            this.consume(TokenType.COMMA, "Ожидается ','");
            const consequent = this.parseExpression();
            this.consume(TokenType.COMMA, "Ожидается ','");
            const alternate = this.parseExpression();
            const end = this.consume(TokenType.RPAREN, "Ожидается ')'");
            return {
                type: "TernaryExpression",
                condition,
                consequent,
                alternate,
                location: this.makeRange(token, end)
            };
        }
        // Скобки
        if (this.match(TokenType.LPAREN)) {
            const expr = this.parseExpression();
            this.consume(TokenType.RPAREN, "Ожидается ')'");
            return expr;
        }
        // Идентификаторы
        if (this.match(TokenType.IDENTIFIER)) {
            return {
                type: "Identifier",
                name: token.value,
                location: this.makeRange(token, token)
            };
        }
        throw this.error("Неожиданный токен: " + token.value);
    }
    parseNewExpression() {
        const start = this.advance(); // NEW
        const typeName = this.consume(TokenType.IDENTIFIER, "Ожидается имя типа");
        let args = [];
        if (this.match(TokenType.LPAREN)) {
            args = this.parseArguments();
            this.consume(TokenType.RPAREN, "Ожидается ')'");
        }
        return {
            type: "NewExpression",
            typeName: typeName.value,
            arguments: args,
            location: this.makeRange(start, this.previous())
        };
    }
    parseArguments() {
        const args = [];
        if (this.check(TokenType.RPAREN)) {
            return args;
        }
        do {
            args.push(this.parseExpression());
        } while (this.match(TokenType.COMMA));
        return args;
    }
    // === Helper methods ===
    peek() {
        return this.tokens[this.current];
    }
    previous() {
        return this.tokens[this.current - 1];
    }
    isAtEnd() {
        return this.peek().type === TokenType.EOF;
    }
    advance() {
        if (!this.isAtEnd())
            this.current++;
        return this.previous();
    }
    check(type) {
        if (this.isAtEnd())
            return false;
        return this.peek().type === type;
    }
    checkKeyword(keyword) {
        if (this.isAtEnd())
            return false;
        const token = this.peek();
        return token.type === TokenType.KEYWORD && token.keyword === keyword;
    }
    match(type) {
        if (this.check(type)) {
            this.advance();
            return true;
        }
        return false;
    }
    matchSemicolon() {
        this.match(TokenType.SEMICOLON);
    }
    consume(type, message) {
        if (this.check(type))
            return this.advance();
        throw this.error(message);
    }
    consumeKeyword(keyword, message) {
        if (this.checkKeyword(keyword))
            return this.advance();
        throw this.error(message);
    }
    error(message) {
        const token = this.peek();
        this.errors.push({
            message,
            line: token.line,
            column: token.column,
            token
        });
        return new Error(message);
    }
    makeRange(start, end) {
        const startLoc = "type" in start
            ? { line: start.line, column: start.column, position: start.position }
            : start;
        const endLoc = "type" in end
            ? { line: end.line, column: end.column + end.value.length, position: end.position + end.value.length }
            : end;
        return { start: startLoc, end: endLoc };
    }
}
// === Export ===
export function parse(source) {
    const parser = new BSLParser();
    return parser.parse(source);
}
//# sourceMappingURL=parser.js.map