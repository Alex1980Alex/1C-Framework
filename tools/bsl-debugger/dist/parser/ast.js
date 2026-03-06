/**
 * BSL AST — Abstract Syntax Tree типы для языка 1С/BSL
 *
 * Представление структуры BSL-кода в виде дерева.
 */
// === AST Walker ===
export function walkAST(node, visitor) {
    const method = `visit${node.type}`;
    if (visitor[method]) {
        visitor[method](node);
    }
    // Рекурсивный обход детей
    switch (node.type) {
        case "Module": {
            const mod = node;
            mod.statements.forEach(s => walkAST(s, visitor));
            mod.procedures.forEach(p => walkAST(p, visitor));
            mod.functions.forEach(f => walkAST(f, visitor));
            break;
        }
        case "ProcedureDeclaration":
        case "FunctionDeclaration": {
            const decl = node;
            decl.body.forEach(s => walkAST(s, visitor));
            break;
        }
        case "IfStatement": {
            const ifStmt = node;
            walkAST(ifStmt.condition, visitor);
            ifStmt.thenBranch.forEach(s => walkAST(s, visitor));
            ifStmt.elseIfBranches.forEach(branch => {
                walkAST(branch.condition, visitor);
                branch.body.forEach(s => walkAST(s, visitor));
            });
            ifStmt.elseBranch?.forEach(s => walkAST(s, visitor));
            break;
        }
        case "ForStatement": {
            const forStmt = node;
            walkAST(forStmt.start, visitor);
            walkAST(forStmt.end, visitor);
            forStmt.body.forEach(s => walkAST(s, visitor));
            break;
        }
        case "ForEachStatement": {
            const forEach = node;
            walkAST(forEach.collection, visitor);
            forEach.body.forEach(s => walkAST(s, visitor));
            break;
        }
        case "WhileStatement": {
            const whileStmt = node;
            walkAST(whileStmt.condition, visitor);
            whileStmt.body.forEach(s => walkAST(s, visitor));
            break;
        }
        case "TryStatement": {
            const tryStmt = node;
            tryStmt.tryBlock.forEach(s => walkAST(s, visitor));
            tryStmt.exceptBlock.forEach(s => walkAST(s, visitor));
            break;
        }
        case "AssignmentStatement": {
            const assign = node;
            walkAST(assign.target, visitor);
            walkAST(assign.value, visitor);
            break;
        }
        case "ExpressionStatement": {
            walkAST(node.expression, visitor);
            break;
        }
        case "ReturnStatement": {
            const ret = node;
            if (ret.value)
                walkAST(ret.value, visitor);
            break;
        }
        case "BinaryExpression": {
            const binary = node;
            walkAST(binary.left, visitor);
            walkAST(binary.right, visitor);
            break;
        }
        case "UnaryExpression": {
            walkAST(node.operand, visitor);
            break;
        }
        case "CallExpression": {
            const call = node;
            walkAST(call.callee, visitor);
            call.arguments.forEach(a => walkAST(a, visitor));
            break;
        }
        case "NewExpression": {
            node.arguments.forEach(a => walkAST(a, visitor));
            break;
        }
        case "MemberExpression": {
            walkAST(node.object, visitor);
            break;
        }
        case "IndexExpression": {
            const idx = node;
            walkAST(idx.object, visitor);
            walkAST(idx.index, visitor);
            break;
        }
    }
}
//# sourceMappingURL=ast.js.map