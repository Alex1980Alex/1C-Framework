/**
 * BSL AST — Abstract Syntax Tree типы для языка 1С/BSL
 *
 * Представление структуры BSL-кода в виде дерева.
 */
export interface SourceLocation {
    line: number;
    column: number;
    position: number;
}
export interface SourceRange {
    start: SourceLocation;
    end: SourceLocation;
}
export interface ASTNode {
    type: string;
    location: SourceRange;
}
export interface Module extends ASTNode {
    type: "Module";
    statements: Statement[];
    procedures: ProcedureDeclaration[];
    functions: FunctionDeclaration[];
    variables: VariableDeclaration[];
    uses: UseDirective[];
    annotations: Annotation[];
}
export interface UseDirective extends ASTNode {
    type: "UseDirective";
    library: string;
}
export interface Annotation extends ASTNode {
    type: "Annotation";
    name: string;
    parameters?: Expression[];
}
export interface VariableDeclaration extends ASTNode {
    type: "VariableDeclaration";
    name: string;
    isExport: boolean;
    initializer?: Expression;
}
export interface ParameterDeclaration extends ASTNode {
    type: "ParameterDeclaration";
    name: string;
    isByValue: boolean;
    defaultValue?: Expression;
}
export interface ProcedureDeclaration extends ASTNode {
    type: "ProcedureDeclaration";
    name: string;
    parameters: ParameterDeclaration[];
    isExport: boolean;
    isAsync: boolean;
    body: Statement[];
    annotations: Annotation[];
    localVariables: VariableDeclaration[];
}
export interface FunctionDeclaration extends ASTNode {
    type: "FunctionDeclaration";
    name: string;
    parameters: ParameterDeclaration[];
    isExport: boolean;
    isAsync: boolean;
    body: Statement[];
    annotations: Annotation[];
    localVariables: VariableDeclaration[];
}
export type Statement = AssignmentStatement | ExpressionStatement | IfStatement | ForStatement | ForEachStatement | WhileStatement | TryStatement | ReturnStatement | BreakStatement | ContinueStatement | RaiseStatement | ExecuteStatement | VariableDeclaration | EmptyStatement;
export interface AssignmentStatement extends ASTNode {
    type: "AssignmentStatement";
    target: Expression;
    value: Expression;
}
export interface ExpressionStatement extends ASTNode {
    type: "ExpressionStatement";
    expression: Expression;
}
export interface IfStatement extends ASTNode {
    type: "IfStatement";
    condition: Expression;
    thenBranch: Statement[];
    elseIfBranches: ElseIfBranch[];
    elseBranch?: Statement[];
}
export interface ElseIfBranch extends ASTNode {
    type: "ElseIfBranch";
    condition: Expression;
    body: Statement[];
}
export interface ForStatement extends ASTNode {
    type: "ForStatement";
    variable: string;
    start: Expression;
    end: Expression;
    body: Statement[];
}
export interface ForEachStatement extends ASTNode {
    type: "ForEachStatement";
    variable: string;
    collection: Expression;
    body: Statement[];
}
export interface WhileStatement extends ASTNode {
    type: "WhileStatement";
    condition: Expression;
    body: Statement[];
}
export interface TryStatement extends ASTNode {
    type: "TryStatement";
    tryBlock: Statement[];
    exceptBlock: Statement[];
}
export interface ReturnStatement extends ASTNode {
    type: "ReturnStatement";
    value?: Expression;
}
export interface BreakStatement extends ASTNode {
    type: "BreakStatement";
}
export interface ContinueStatement extends ASTNode {
    type: "ContinueStatement";
}
export interface RaiseStatement extends ASTNode {
    type: "RaiseStatement";
    expression?: Expression;
}
export interface ExecuteStatement extends ASTNode {
    type: "ExecuteStatement";
    expression: Expression;
}
export interface EmptyStatement extends ASTNode {
    type: "EmptyStatement";
}
export type Expression = BinaryExpression | UnaryExpression | TernaryExpression | CallExpression | NewExpression | MemberExpression | IndexExpression | AwaitExpression | Identifier | NumberLiteral | StringLiteral | BooleanLiteral | DateLiteral | UndefinedLiteral | NullLiteral;
export interface BinaryExpression extends ASTNode {
    type: "BinaryExpression";
    operator: BinaryOperator;
    left: Expression;
    right: Expression;
}
export type BinaryOperator = "+" | "-" | "*" | "/" | "%" | "=" | "<>" | "<" | ">" | "<=" | ">=" | "AND" | "OR";
export interface UnaryExpression extends ASTNode {
    type: "UnaryExpression";
    operator: UnaryOperator;
    operand: Expression;
}
export type UnaryOperator = "-" | "NOT";
export interface TernaryExpression extends ASTNode {
    type: "TernaryExpression";
    condition: Expression;
    consequent: Expression;
    alternate: Expression;
}
export interface CallExpression extends ASTNode {
    type: "CallExpression";
    callee: Expression;
    arguments: Expression[];
}
export interface NewExpression extends ASTNode {
    type: "NewExpression";
    typeName: string;
    arguments: Expression[];
}
export interface MemberExpression extends ASTNode {
    type: "MemberExpression";
    object: Expression;
    property: string;
}
export interface IndexExpression extends ASTNode {
    type: "IndexExpression";
    object: Expression;
    index: Expression;
}
export interface AwaitExpression extends ASTNode {
    type: "AwaitExpression";
    expression: Expression;
}
export interface Identifier extends ASTNode {
    type: "Identifier";
    name: string;
}
export interface NumberLiteral extends ASTNode {
    type: "NumberLiteral";
    value: number;
    raw: string;
}
export interface StringLiteral extends ASTNode {
    type: "StringLiteral";
    value: string;
    raw: string;
}
export interface BooleanLiteral extends ASTNode {
    type: "BooleanLiteral";
    value: boolean;
}
export interface DateLiteral extends ASTNode {
    type: "DateLiteral";
    value: Date;
    raw: string;
}
export interface UndefinedLiteral extends ASTNode {
    type: "UndefinedLiteral";
}
export interface NullLiteral extends ASTNode {
    type: "NullLiteral";
}
export interface DebugInfo {
    lineToNodes: Map<number, ASTNode[]>;
    callableRanges: Map<string, {
        start: number;
        end: number;
    }>;
    breakpointCandidates: number[];
    scopes: ScopeInfo[];
}
export interface ScopeInfo {
    name: string;
    type: "module" | "procedure" | "function" | "block";
    range: SourceRange;
    variables: string[];
    parent?: ScopeInfo;
}
export interface ASTVisitor<T> {
    visitModule?(node: Module): T;
    visitProcedureDeclaration?(node: ProcedureDeclaration): T;
    visitFunctionDeclaration?(node: FunctionDeclaration): T;
    visitVariableDeclaration?(node: VariableDeclaration): T;
    visitAssignmentStatement?(node: AssignmentStatement): T;
    visitExpressionStatement?(node: ExpressionStatement): T;
    visitIfStatement?(node: IfStatement): T;
    visitForStatement?(node: ForStatement): T;
    visitForEachStatement?(node: ForEachStatement): T;
    visitWhileStatement?(node: WhileStatement): T;
    visitTryStatement?(node: TryStatement): T;
    visitReturnStatement?(node: ReturnStatement): T;
    visitBreakStatement?(node: BreakStatement): T;
    visitContinueStatement?(node: ContinueStatement): T;
    visitRaiseStatement?(node: RaiseStatement): T;
    visitBinaryExpression?(node: BinaryExpression): T;
    visitUnaryExpression?(node: UnaryExpression): T;
    visitCallExpression?(node: CallExpression): T;
    visitNewExpression?(node: NewExpression): T;
    visitMemberExpression?(node: MemberExpression): T;
    visitIndexExpression?(node: IndexExpression): T;
    visitIdentifier?(node: Identifier): T;
    visitNumberLiteral?(node: NumberLiteral): T;
    visitStringLiteral?(node: StringLiteral): T;
    visitBooleanLiteral?(node: BooleanLiteral): T;
    visitDateLiteral?(node: DateLiteral): T;
    visitUndefinedLiteral?(node: UndefinedLiteral): T;
}
export declare function walkAST(node: ASTNode, visitor: ASTVisitor<void>): void;
//# sourceMappingURL=ast.d.ts.map