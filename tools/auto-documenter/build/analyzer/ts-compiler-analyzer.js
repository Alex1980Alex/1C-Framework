/**
 * TypeScript Compiler API-based code analyzer
 * Provides accurate AST-based symbol extraction replacing regex patterns
 * @module analyzer/ts-compiler-analyzer
 */
import * as ts from 'typescript';
/**
 * TypeScript Compiler API-based analyzer
 * More accurate than regex for parsing TypeScript/JavaScript code
 */
export class TSCompilerAnalyzer {
    constructor() {
        this.sourceFile = null;
        this.content = '';
    }
    /**
     * Analyze TypeScript/JavaScript source code
     * @param content Source code content
     * @param fileName Virtual filename for parsing (determines language features)
     * @returns Array of extracted symbols
     */
    analyze(content, fileName = 'file.ts') {
        this.content = content;
        this.sourceFile = ts.createSourceFile(fileName, content, ts.ScriptTarget.Latest, true, // setParentNodes
        this.getScriptKind(fileName));
        const symbols = [];
        this.visitNode(this.sourceFile, symbols);
        return symbols;
    }
    /**
     * Get script kind based on file extension
     */
    getScriptKind(fileName) {
        const ext = fileName.toLowerCase().split('.').pop();
        switch (ext) {
            case 'tsx': return ts.ScriptKind.TSX;
            case 'jsx': return ts.ScriptKind.JSX;
            case 'js': return ts.ScriptKind.JS;
            case 'ts':
            default: return ts.ScriptKind.TS;
        }
    }
    /**
     * Visit AST nodes recursively
     */
    visitNode(node, symbols) {
        if (!this.sourceFile)
            return;
        // Function declarations
        if (ts.isFunctionDeclaration(node) && node.name) {
            symbols.push(this.extractFunctionSymbol(node));
        }
        // Class declarations
        if (ts.isClassDeclaration(node) && node.name) {
            symbols.push(this.extractClassSymbol(node));
        }
        // Interface declarations
        if (ts.isInterfaceDeclaration(node)) {
            symbols.push(this.extractInterfaceSymbol(node));
        }
        // Type alias declarations
        if (ts.isTypeAliasDeclaration(node)) {
            symbols.push(this.extractTypeSymbol(node));
        }
        // Arrow functions assigned to const/let
        if (ts.isVariableStatement(node)) {
            const arrowSymbols = this.extractArrowFunctions(node);
            symbols.push(...arrowSymbols);
        }
        // Recursively visit children
        ts.forEachChild(node, child => this.visitNode(child, symbols));
    }
    /**
     * Extract function declaration information
     */
    extractFunctionSymbol(node) {
        const name = node.name?.getText(this.sourceFile) || 'anonymous';
        const { line: startLine, character: endLine } = this.getLineNumbers(node);
        return {
            name,
            type: 'function',
            code: this.getNodeText(node),
            lineNumber: startLine,
            endLineNumber: endLine,
            isExported: this.hasExportModifier(node),
            isAsync: this.hasAsyncModifier(node),
            hasJSDoc: this.hasJSDocComment(node),
            parameters: this.extractParameters(node.parameters),
            returnType: node.type ? node.type.getText(this.sourceFile) : undefined,
            modifiers: this.getModifiers(node),
        };
    }
    /**
     * Extract class declaration information
     */
    extractClassSymbol(node) {
        const name = node.name?.getText(this.sourceFile) || 'anonymous';
        const { line: startLine, character: endLine } = this.getLineNumbers(node);
        return {
            name,
            type: 'class',
            code: this.getNodeText(node),
            lineNumber: startLine,
            endLineNumber: endLine,
            isExported: this.hasExportModifier(node),
            isAsync: false,
            hasJSDoc: this.hasJSDocComment(node),
            modifiers: this.getModifiers(node),
        };
    }
    /**
     * Extract interface declaration information
     */
    extractInterfaceSymbol(node) {
        const name = node.name.getText(this.sourceFile);
        const { line: startLine, character: endLine } = this.getLineNumbers(node);
        return {
            name,
            type: 'interface',
            code: this.getNodeText(node),
            lineNumber: startLine,
            endLineNumber: endLine,
            isExported: this.hasExportModifier(node),
            isAsync: false,
            hasJSDoc: this.hasJSDocComment(node),
            modifiers: this.getModifiers(node),
        };
    }
    /**
     * Extract type alias declaration information
     */
    extractTypeSymbol(node) {
        const name = node.name.getText(this.sourceFile);
        const { line: startLine, character: endLine } = this.getLineNumbers(node);
        return {
            name,
            type: 'type',
            code: this.getNodeText(node),
            lineNumber: startLine,
            endLineNumber: endLine,
            isExported: this.hasExportModifier(node),
            isAsync: false,
            hasJSDoc: this.hasJSDocComment(node),
            modifiers: this.getModifiers(node),
        };
    }
    /**
     * Extract arrow functions from variable statements
     */
    extractArrowFunctions(node) {
        const symbols = [];
        for (const declaration of node.declarationList.declarations) {
            if (ts.isIdentifier(declaration.name) &&
                declaration.initializer &&
                ts.isArrowFunction(declaration.initializer)) {
                const arrow = declaration.initializer;
                const name = declaration.name.getText(this.sourceFile);
                const { line: startLine, character: endLine } = this.getLineNumbers(node);
                symbols.push({
                    name,
                    type: 'function',
                    code: this.getNodeText(node),
                    lineNumber: startLine,
                    endLineNumber: endLine,
                    isExported: this.hasExportModifier(node),
                    isAsync: this.hasAsyncModifier(arrow),
                    hasJSDoc: this.hasJSDocComment(node),
                    parameters: this.extractParameters(arrow.parameters),
                    returnType: arrow.type ? arrow.type.getText(this.sourceFile) : undefined,
                    modifiers: this.getModifiers(node),
                });
            }
        }
        return symbols;
    }
    /**
     * Extract parameter information
     */
    extractParameters(params) {
        return params.map(param => ({
            name: param.name.getText(this.sourceFile),
            type: param.type ? param.type.getText(this.sourceFile) : undefined,
            isOptional: !!param.questionToken,
            hasDefault: !!param.initializer,
        }));
    }
    /**
     * Get line numbers for a node
     */
    getLineNumbers(node) {
        const start = this.sourceFile.getLineAndCharacterOfPosition(node.getStart(this.sourceFile));
        const end = this.sourceFile.getLineAndCharacterOfPosition(node.getEnd());
        return {
            line: start.line + 1, // 1-indexed
            character: end.line + 1
        };
    }
    /**
     * Get node text including leading trivia (comments)
     */
    getNodeText(node) {
        const fullStart = node.getFullStart();
        const start = node.getStart(this.sourceFile);
        const end = node.getEnd();
        // Include leading comments
        const leadingTrivia = this.content.substring(fullStart, start);
        const hasJSDoc = leadingTrivia.includes('/**');
        if (hasJSDoc) {
            return this.content.substring(fullStart, end);
        }
        return this.content.substring(start, end);
    }
    /**
     * Check if node has export modifier
     */
    hasExportModifier(node) {
        const modifiers = ts.canHaveModifiers(node) ? ts.getModifiers(node) : undefined;
        return modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword) ?? false;
    }
    /**
     * Check if node has async modifier
     */
    hasAsyncModifier(node) {
        const modifiers = ts.canHaveModifiers(node) ? ts.getModifiers(node) : undefined;
        return modifiers?.some(m => m.kind === ts.SyntaxKind.AsyncKeyword) ?? false;
    }
    /**
     * Check if node has JSDoc comment
     */
    hasJSDocComment(node) {
        const fullStart = node.getFullStart();
        const start = node.getStart(this.sourceFile);
        const leadingTrivia = this.content.substring(fullStart, start);
        return leadingTrivia.includes('/**');
    }
    /**
     * Get all modifiers as strings
     */
    getModifiers(node) {
        const modifiers = ts.canHaveModifiers(node) ? ts.getModifiers(node) : undefined;
        if (!modifiers)
            return [];
        return modifiers.map(m => {
            switch (m.kind) {
                case ts.SyntaxKind.ExportKeyword: return 'export';
                case ts.SyntaxKind.DefaultKeyword: return 'default';
                case ts.SyntaxKind.AsyncKeyword: return 'async';
                case ts.SyntaxKind.PublicKeyword: return 'public';
                case ts.SyntaxKind.PrivateKeyword: return 'private';
                case ts.SyntaxKind.ProtectedKeyword: return 'protected';
                case ts.SyntaxKind.StaticKeyword: return 'static';
                case ts.SyntaxKind.ReadonlyKeyword: return 'readonly';
                case ts.SyntaxKind.AbstractKeyword: return 'abstract';
                default: return m.getText(this.sourceFile);
            }
        });
    }
    /**
     * Get only exported symbols
     */
    getExportedSymbols(content, fileName = 'file.ts') {
        return this.analyze(content, fileName).filter(s => s.isExported);
    }
    /**
     * Get symbols without existing JSDoc
     */
    getUndocumentedSymbols(content, fileName = 'file.ts') {
        return this.analyze(content, fileName).filter(s => !s.hasJSDoc);
    }
    /**
     * Get exported symbols without JSDoc (main use case for inline docs)
     */
    getExportedUndocumentedSymbols(content, fileName = 'file.ts') {
        return this.analyze(content, fileName).filter(s => s.isExported && !s.hasJSDoc);
    }
}
/**
 * Singleton instance for convenience
 */
export const tsAnalyzer = new TSCompilerAnalyzer();
/**
 * Quick analysis function
 * @param content Source code
 * @param fileName File name for language detection
 * @returns Array of symbols
 */
export function analyzeTypeScript(content, fileName = 'file.ts') {
    return tsAnalyzer.analyze(content, fileName);
}
/**
 * Quick function to get only exported symbols
 */
export function getExportedSymbols(content, fileName = 'file.ts') {
    return tsAnalyzer.getExportedSymbols(content, fileName);
}
//# sourceMappingURL=ts-compiler-analyzer.js.map