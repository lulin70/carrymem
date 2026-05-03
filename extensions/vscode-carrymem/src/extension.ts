import * as vscode from 'vscode';
import { CarryMemClient } from './carrymemClient';
import { RuleTreeProvider, RuleTreeItem } from './ruleTreeProvider';
import { RuleEditorPanel } from './ruleEditorPanel';
import { Rule } from './carrymemClient';

export function activate(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('carrymem');
    const client = new CarryMemClient(config);
    const treeProvider = new RuleTreeProvider(client);

    const treeView = vscode.window.createTreeView('carrymem-rules', {
        treeDataProvider: treeProvider,
        showCollapseAll: false,
    });

    context.subscriptions.push(treeView);

    const register = (cmd: string, handler: (...args: any[]) => any) => {
        context.subscriptions.push(vscode.commands.registerCommand(cmd, handler));
    };

    register('carrymem.refreshRules', () => {
        treeProvider.refresh();
    });

    register('carrymem.addRule', async () => {
        RuleEditorPanel.createOrShow(client);
    });

    register('carrymem.editRule', async (item?: RuleTreeItem | Rule) => {
        const rule = item instanceof RuleTreeItem ? item.rule : item as Rule | undefined;
        if (rule) {
            RuleEditorPanel.createOrShow(client, rule);
        }
    });

    register('carrymem.deleteRule', async (item?: RuleTreeItem) => {
        const rule = item?.rule;
        if (!rule) { return; }

        const confirm = await vscode.window.showWarningMessage(
            `Delete rule "${rule.trigger}"?`,
            { modal: true },
            'Delete',
        );
        if (confirm !== 'Delete') { return; }

        try {
            await client.deleteRule(rule.id);
            vscode.window.showInformationMessage(`Rule deleted: ${rule.trigger}`);
            treeProvider.refresh();
        } catch (e: any) {
            vscode.window.showErrorMessage(`Failed to delete rule: ${e.message}`);
        }
    });

    register('carrymem.toggleRule', async (item?: RuleTreeItem) => {
        const rule = item?.rule;
        if (!rule) { return; }

        try {
            if (rule.status === 'active') {
                await client.pauseRule(rule.id);
                vscode.window.showInformationMessage(`Rule paused: ${rule.trigger}`);
            } else if (rule.status === 'paused') {
                await client.resumeRule(rule.id);
                vscode.window.showInformationMessage(`Rule resumed: ${rule.trigger}`);
            }
            treeProvider.refresh();
        } catch (e: any) {
            vscode.window.showErrorMessage(`Failed to toggle rule: ${e.message}`);
        }
    });

    register('carrymem.matchRules', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('No active editor');
            return;
        }

        const fileName = editor.document.fileName.split('/').pop() || '';
        const language = editor.document.languageId;
        const scene = `${fileName} ${language}`;

        try {
            const matches = await client.matchRules(scene);
            if (matches.length === 0) {
                vscode.window.showInformationMessage('No matching rules found');
                return;
            }

            const items = matches.map(m => ({
                label: `[${m.rule.rule_type.toUpperCase()}] ${m.rule.action}`,
                description: `${m.rule.scope} (${m.score.toFixed(2)})`,
                detail: m.rule.trigger,
                rule: m.rule,
            }));

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: `Matched ${matches.length} rules for "${scene}"`,
            });

            if (selected) {
                RuleEditorPanel.createOrShow(client, selected.rule);
            }
        } catch (e: any) {
            vscode.window.showErrorMessage(`Match failed: ${e.message}`);
        }
    });

    register('carrymem.showEffectivenessReport', async () => {
        try {
            const report = await client.getEffectivenessReport();
            const panel = vscode.window.createWebviewPanel(
                'carrymemReport',
                'CarryMem Effectiveness Report',
                vscode.ViewColumn.One,
                { enableScripts: false },
            );

            panel.webview.html = renderReport(report);
        } catch (e: any) {
            vscode.window.showErrorMessage(`Report failed: ${e.message}`);
        }
    });

    register('carrymem.skillPack', async () => {
        const name = await vscode.window.showInputBox({
            prompt: 'Skill name',
            placeHolder: 'e.g., security-best-practices',
        });
        if (!name) { return; }

        const scope = await vscode.window.showQuickPick(
            ['personal', 'company', 'negotiated'] as const,
            { placeHolder: 'Select scope' },
        );
        if (!scope) { return; }

        const uri = await vscode.window.showSaveDialog({
            defaultUri: vscode.Uri.file(`${name}-skill.json`),
            filters: { 'JSON': ['json'] },
        });
        if (!uri) { return; }

        try {
            await client.skillPack(name, scope, uri.fsPath);
            vscode.window.showInformationMessage(`Skill packed: ${name}`);
        } catch (e: any) {
            vscode.window.showErrorMessage(`Skill pack failed: ${e.message}`);
        }
    });

    register('carrymem.skillInstall', async () => {
        const uris = await vscode.window.showOpenDialog({
            filters: { 'JSON': ['json'] },
            canSelectMany: false,
        });
        if (!uris || uris.length === 0) { return; }

        const scope = await vscode.window.showQuickPick(
            ['personal', 'company', 'negotiated', '(use skill default)'] as const,
            { placeHolder: 'Override scope?' },
        );

        try {
            const scopeArg = scope === '(use skill default)' ? undefined : scope;
            await client.skillInstall(uris[0].fsPath, scopeArg, 'skip');
            vscode.window.showInformationMessage('Skill installed');
            treeProvider.refresh();
        } catch (e: any) {
            vscode.window.showErrorMessage(`Skill install failed: ${e.message}`);
        }
    });

    checkAvailability(client);
}

async function checkAvailability(client: CarryMemClient) {
    const available = await client.isAvailable();
    if (!available) {
        vscode.window.showWarningMessage(
            'CarryMem CLI not found. Install with: pip install carrymem',
        );
    }
}

function escapeHtml(text: string | number): string {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderReport(report: any): string {
    const typeRows = Object.entries(report.type_breakdown || {})
        .map(([t, c]) => `<tr><td>${escapeHtml(t)}</td><td>${escapeHtml(c as number)}</td></tr>`)
        .join('');

    const scopeRows = Object.entries(report.scope_breakdown || {})
        .map(([s, c]) => `<tr><td>${escapeHtml(s)}</td><td>${escapeHtml(c as number)}</td></tr>`)
        .join('');

    const topRows = (report.top_triggered || [])
        .map((r: any) => `<tr><td>${escapeHtml(r.trigger)}</td><td>${escapeHtml(r.trigger_count)}</td></tr>`)
        .join('');

    return `<!DOCTYPE html>
<html><head>
<style>
    body { font-family: var(--vscode-font-family); padding: 20px; color: var(--vscode-foreground); }
    h2 { border-bottom: 1px solid var(--vscode-panel-border); padding-bottom: 8px; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; }
    th, td { border: 1px solid var(--vscode-panel-border); padding: 6px 10px; text-align: left; }
    th { background: var(--vscode-editor-background); }
    .stat { display: inline-block; margin: 8px 16px; }
    .stat-value { font-size: 24px; font-weight: bold; }
    .stat-label { font-size: 11px; color: var(--vscode-descriptionForeground); }
</style>
</head><body>
    <h2>CarryMem Effectiveness Report</h2>

    <div>
        <span class="stat"><div class="stat-value">${escapeHtml(report.total_rules)}</div><div class="stat-label">Total Rules</div></span>
        <span class="stat"><div class="stat-value">${escapeHtml(report.active)}</div><div class="stat-label">Active</div></span>
        <span class="stat"><div class="stat-value">${report.trigger_rate ? escapeHtml((report.trigger_rate * 100).toFixed(1) + '%') : 'N/A'}</div><div class="stat-label">Trigger Rate</div></span>
    </div>

    <h3>Type Breakdown</h3>
    <table><tr><th>Type</th><th>Count</th></tr>${typeRows}</table>

    <h3>Scope Breakdown</h3>
    <table><tr><th>Scope</th><th>Count</th></tr>${scopeRows}</table>

    <h3>Top Triggered Rules</h3>
    <table><tr><th>Trigger</th><th>Count</th></tr>${topRows || '<tr><td colspan="2">No triggered rules yet</td></tr>'}</table>
</body></html>`;
}

export function deactivate() {}
