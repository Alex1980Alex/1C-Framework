/**
 * BSL Lexer — Лексический анализатор для языка 1С/BSL
 *
 * Токенизирует исходный код BSL для последующего парсинга.
 * Поддерживает русские и английские ключевые слова.
 */
export declare enum TokenType {
    NUMBER = "NUMBER",
    STRING = "STRING",
    DATE = "DATE",
    BOOLEAN = "BOOLEAN",
    UNDEFINED = "UNDEFINED",
    NULL = "NULL",
    IDENTIFIER = "IDENTIFIER",
    KEYWORD = "KEYWORD",
    PLUS = "PLUS",// +
    MINUS = "MINUS",// -
    MULTIPLY = "MULTIPLY",// *
    DIVIDE = "DIVIDE",// /
    MODULO = "MODULO",// %
    ASSIGN = "ASSIGN",// =
    EQUALS = "EQUALS",// =
    NOT_EQUALS = "NOT_EQUALS",// <>
    LESS = "LESS",// <
    GREATER = "GREATER",// >
    LESS_EQ = "LESS_EQ",// <=
    GREATER_EQ = "GREATER_EQ",// >=
    LPAREN = "LPAREN",// (
    RPAREN = "RPAREN",// )
    LBRACKET = "LBRACKET",// [
    RBRACKET = "RBRACKET",// ]
    COMMA = "COMMA",// ,
    SEMICOLON = "SEMICOLON",// ;
    DOT = "DOT",// .
    QUESTION = "QUESTION",// ?
    COMMENT = "COMMENT",
    PREPROCESSOR = "PREPROCESSOR",
    ANNOTATION = "ANNOTATION",
    NEWLINE = "NEWLINE",
    EOF = "EOF"
}
export declare const KEYWORDS: Record<string, string>;
export interface Token {
    type: TokenType;
    value: string;
    keyword?: string;
    line: number;
    column: number;
    position: number;
}
export interface LexerError {
    message: string;
    line: number;
    column: number;
    position: number;
}
export declare class BSLLexer {
    private source;
    private position;
    private line;
    private column;
    private tokens;
    private errors;
    constructor(source: string);
    tokenize(): {
        tokens: Token[];
        errors: LexerError[];
    };
    private scanLineComment;
    private scanPreprocessor;
    private scanAnnotation;
    private scanString;
    private scanNumber;
    private scanDate;
    private scanIdentifier;
    private scanOperator;
    private peek;
    private peekNext;
    private advance;
    private match;
    private isAtEnd;
    private isDigit;
    private isAlpha;
    private isAlphaNumeric;
    private skipWhitespace;
    private addToken;
    private addError;
}
export declare function tokenize(source: string): {
    tokens: Token[];
    errors: LexerError[];
};
//# sourceMappingURL=lexer.d.ts.map