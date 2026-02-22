import * as vscode from 'vscode';
import * as path from 'path';

export function activate(context: vscode.ExtensionContext) {
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

    // Code Action provider — shows in Ctrl+. lightbulb menu
    const codeActionProvider = vscode.languages.registerCodeActionsProvider(
        { scheme: 'file' },
        {
            provideCodeActions(document, range): vscode.CodeAction[] | undefined {
                if (range.isEmpty) {
                    return undefined;
                }

                const action = new vscode.CodeAction(
                    'Claude: Send @file#lines to Terminal',
                    vscode.CodeActionKind.Refactor
                );
                action.command = {
                    command: 'claudeSelect.sendToTerminal',
                    title: 'Claude: Send @file#lines to Terminal',
                };
                return [action];
            }
        },
        { providedCodeActionKinds: [vscode.CodeActionKind.Refactor] }
    );

    context.subscriptions.push(disposable, codeActionProvider);
}

export function deactivate() {}
