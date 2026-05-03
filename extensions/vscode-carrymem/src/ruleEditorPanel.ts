import * as vscode from 'vscode';
import { CarryMemClient, Rule } from './carrymemClient';

const RULE_TYPES = ['avoid', 'always', 'prefer', 'forbid', 'format'];
const RULE_SCOPES = ['personal', 'company', 'negotiated'];

export class RuleEditorPanel {
    public static currentPanel: RuleEditorPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private _disposables: vscode.Disposable[] = [];

    private constructor(
        panel: vscode.WebviewPanel,
        private client: CarryMemClient,
        private rule?: Rule,
    ) {
        this._panel = panel;
        this._panel.webview.html = this._getWebviewContent();
        this._panel.webview.onDidReceiveMessage(async (msg) => {
            await this._handleMessage(msg);
        });
        this._panel.onDidDispose(() => this.dispose());
    }

    public static createOrShow(client: CarryMemClient, rule?: Rule) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (RuleEditorPanel.currentPanel) {
            RuleEditorPanel.currentPanel._panel.reveal(column);
            if (rule !== RuleEditorPanel.currentPanel.rule) {
                RuleEditorPanel.currentPanel.rule = rule;
                RuleEditorPanel.currentPanel._panel.webview.html = RuleEditorPanel.currentPanel._getWebviewContent();
            }
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'carrymemRuleEditor',
            rule ? `Edit Rule: ${rule.trigger}` : 'Add Rule',
            column || vscode.ViewColumn.One,
            { enableScripts: true },
        );

        RuleEditorPanel.currentPanel = new RuleEditorPanel(panel, client, rule);
    }

    private async _handleMessage(msg: any) {
        switch (msg.command) {
            case 'save': {
                try {
                    if (this.rule) {
                        await this.client.editRule(this.rule.id, {
                            trigger: msg.trigger,
                            action: msg.action,
                            rule_type: msg.rule_type,
                            scope: msg.scope,
                            override: msg.override,
                        });
                        vscode.window.showInformationMessage(`Rule updated: ${msg.trigger}`);
                    } else {
                        await this.client.addRule(
                            msg.trigger,
                            msg.action,
                            msg.rule_type,
                            msg.scope,
                            msg.override,
                        );
                        vscode.window.showInformationMessage(`Rule added: ${msg.trigger}`);
                    }
                    this._panel.dispose();
                } catch (e: any) {
                    vscode.window.showErrorMessage(`Failed to save rule: ${e.message}`);
                }
                break;
            }
            case 'cancel': {
                this._panel.dispose();
                break;
            }
        }
    }

    private _getWebviewContent(): string {
        const r = this.rule;
        const trigger = r ? this._escapeHtml(r.trigger) : '';
        const action = r ? this._escapeHtml(r.action) : '';
        const ruleType = r ? r.rule_type : 'avoid';
        const scope = r ? r.scope : 'personal';
        const override = r ? r.override : true;

        const typeOptions = RULE_TYPES.map(t =>
            `<option value="${t}" ${t === ruleType ? 'selected' : ''}>${t.toUpperCase()}</option>`
        ).join('\n');

        const scopeOptions = RULE_SCOPES.map(s =>
            `<option value="${s}" ${s === scope ? 'selected' : ''}>${s.charAt(0).toUpperCase() + s.slice(1)}</option>`
        ).join('\n');

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${r ? 'Edit Rule' : 'Add Rule'}</title>
    <style>
        body { font-family: var(--vscode-font-family); padding: 16px; color: var(--vscode-foreground); }
        label { display: block; margin-top: 12px; font-weight: 600; }
        input, select, textarea { width: 100%; padding: 6px 8px; margin-top: 4px; border: 1px solid var(--vscode-input-border); background: var(--vscode-input-background); color: var(--vscode-input-foreground); border-radius: 3px; box-sizing: border-box; }
        textarea { min-height: 60px; resize: vertical; }
        .checkbox-row { display: flex; align-items: center; margin-top: 12px; }
        .checkbox-row input[type="checkbox"] { width: auto; margin-right: 8px; }
        .buttons { display: flex; gap: 8px; margin-top: 20px; }
        button { padding: 8px 16px; border: none; border-radius: 3px; cursor: pointer; font-size: 13px; }
        .btn-primary { background: var(--vscode-button-background); color: var(--vscode-button-foreground); }
        .btn-secondary { background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); }
        .scope-info { font-size: 11px; color: var(--vscode-descriptionForeground); margin-top: 2px; }
    </style>
</head>
<body>
    <h2>${r ? 'Edit Rule' : 'Add Rule'}</h2>

    <label for="trigger">Trigger (scene description)</label>
    <input type="text" id="trigger" value="${trigger}" placeholder="e.g., database connection, API design, report writing" />

    <label for="action">Action (behavioral instruction)</label>
    <textarea id="action" placeholder="e.g., Always use SSL for database connections">${action}</textarea>

    <label for="rule_type">Rule Type</label>
    <select id="rule_type">${typeOptions}</select>

    <label for="scope">Scope</label>
    <select id="scope">${scopeOptions}</select>
    <div class="scope-info">
        <strong>Personal</strong>: User-created | <strong>Company</strong>: Org-mandated | <strong>Negotiated</strong>: Adapted from company
    </div>

    <div class="checkbox-row">
        <input type="checkbox" id="override" ${override ? 'checked' : ''} />
        <label for="override" style="margin-top:0;font-weight:normal">Override (AI cannot ignore this rule)</label>
    </div>

    <div class="buttons">
        <button class="btn-primary" onclick="save()">Save</button>
        <button class="btn-secondary" onclick="cancel()">Cancel</button>
    </div>

    <script>
        const vscode = acquireVsCodeApi();

        function save() {
            vscode.postMessage({
                command: 'save',
                trigger: document.getElementById('trigger').value,
                action: document.getElementById('action').value,
                rule_type: document.getElementById('rule_type').value,
                scope: document.getElementById('scope').value,
                override: document.getElementById('override').checked,
            });
        }

        function cancel() {
            vscode.postMessage({ command: 'cancel' });
        }
    </script>
</body>
</html>`;
    }

    private _escapeHtml(text: string): string {
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    public dispose() {
        RuleEditorPanel.currentPanel = undefined;
        this._panel.dispose();
        while (this._disposables.length) {
            const d = this._disposables.pop();
            if (d) { d.dispose(); }
        }
    }
}
