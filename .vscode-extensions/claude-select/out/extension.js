"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
function activate(context) {
    const disposable = vscode.commands.registerCommand('claudeSelect.sendToTerminal', () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active editor');
            return;
        }
        const terminal = vscode.window.activeTerminal;
        if (!terminal) {
            vscode.window.showWarningMessage('No active terminal');
            return;
        }
        const document = editor.document;
        const selection = editor.selection;
        // Get relative path
        const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
        const relativePath = workspaceFolder
            ? path.relative(workspaceFolder.uri.fsPath, document.uri.fsPath).replace(/\\/g, '/')
            : path.basename(document.uri.fsPath);
        // Lines are 0-indexed in VS Code API, +1 for display
        const startLine = selection.start.line + 1;
        const endLine = selection.end.line + 1;
        // If selection ends at column 0 of a line, the user likely selected up to end of previous line
        const adjustedEndLine = (selection.end.character === 0 && endLine > startLine)
            ? endLine - 1
            : endLine;
        const ref = (startLine === adjustedEndLine)
            ? `@${relativePath}#${startLine}`
            : `@${relativePath}#${startLine}-${adjustedEndLine}`;
        // false = do not press Enter, let the user append their question
        terminal.sendText(ref, false);
    });
    context.subscriptions.push(disposable);
}
function deactivate() { }
//# sourceMappingURL=extension.js.map