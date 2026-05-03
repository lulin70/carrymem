import * as vscode from 'vscode';
import { CarryMemClient, Rule } from './carrymemClient';

const SCOPE_ICONS: Record<string, string> = {
    company: 'shield',
    negotiated: 'git-merge',
    personal: 'person',
};

const TYPE_ICONS: Record<string, vscode.ThemeColor> = {
    forbid: new vscode.ThemeColor('errorForeground'),
    always: new vscode.ThemeColor('charts.green'),
    avoid: new vscode.ThemeColor('charts.yellow'),
    prefer: new vscode.ThemeColor('charts.blue'),
    format: new vscode.ThemeColor('charts.purple'),
};

export class RuleTreeItem extends vscode.TreeItem {
    constructor(public readonly rule: Rule) {
        const scopeIcon = SCOPE_ICONS[rule.scope] || 'circle';
        const overrideMarker = rule.override ? '🔒' : '';
        const statusMarker = rule.status === 'paused' ? '⏸' : '';
        const countMarker = rule.trigger_count > 0 ? ` (${rule.trigger_count}x)` : '';

        super(
            `${statusMarker} [${rule.rule_type.toUpperCase()}] ${rule.trigger}${countMarker}`,
            vscode.TreeItemCollapsibleState.None
        );

        this.tooltip = [
            `Trigger: ${rule.trigger}`,
            `Action: ${rule.action}`,
            `Type: ${rule.rule_type}`,
            `Scope: ${rule.scope}`,
            `Override: ${rule.override}`,
            `Confidence: ${rule.confidence}`,
            `Status: ${rule.status}`,
            `Used: ${rule.trigger_count}x`,
        ].join('\n');

        this.description = `${rule.scope}${overrideMarker}`;
        this.iconPath = new vscode.ThemeIcon(scopeIcon);
        this.contextValue = `rule-${rule.status}`;

        this.command = {
            command: 'carrymem.editRule',
            title: 'Edit Rule',
            arguments: [this.rule],
        };
    }
}

export class RuleTreeProvider implements vscode.TreeDataProvider<RuleTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<RuleTreeItem | undefined | null>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    constructor(private client: CarryMemClient) {}

    refresh(): void {
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: RuleTreeItem): vscode.TreeItem {
        return element;
    }

    async getChildren(): Promise<RuleTreeItem[]> {
        try {
            const rules = await this.client.listRules();
            return rules.map(r => new RuleTreeItem(r));
        } catch {
            return [];
        }
    }
}
