/**
 * BSL Parser — Синтаксический анализатор для языка 1С/BSL
 *
 * Преобразует последовательность токенов в AST.
 */
import { Token } from "./lexer.js";
import * as AST from "./ast.js";
export interface ParseError {
    message: string;
    line: number;
    column: number;
    token?: Token;
}
export declare class BSLParser {
    private tokens;
    private current;
    private errors;
    parse(source: string): {
        ast: AST.Module | null;
        errors: ParseError[];
    };
    private parseModule;
    private parseAnnotation;
    private parseUseDirective;
    private parseVariableDeclaration;
    private parseProcedure;
    private parseFunction;
    private parseParameters;
    private parseBody;
    private parseStatement;
    private parseIfStatement;
    private parseForStatement;
    private parseWhileStatement;
    private parseTryStatement;
    private parseReturnStatement;
    private parseBreakStatement;
    private parseContinueStatement;
    private parseRaiseStatement;
    private parseExecuteStatement;
    private parseAssignmentOrExpression;
    private parseExpression;
    private parseOr;
    private parseAnd;
    private parseNot;
    private parseComparison;
    private parseAddition;
    private parseMultiplication;
    private parseUnary;
    private parsePostfix;
    private parsePrimary;
    private parseNewExpression;
    private parseArguments;
    private peek;
    private previous;
    private isAtEnd;
    private advance;
    private check;
    private checkKeyword;
    private match;
    private matchSemicolon;
    private consume;
    private consumeKeyword;
    private error;
    private makeRange;
}
export declare function parse(source: string): {
    ast: AST.Module | null;
    errors: ParseError[];
};
//# sourceMappingURL=parser.d.ts.map