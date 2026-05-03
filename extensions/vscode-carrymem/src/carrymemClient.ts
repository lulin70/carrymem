import * as vscode from 'vscode';
import { execFile } from 'child_process';

export interface Rule {
    id: string;
    trigger: string;
    action: string;
    rule_type: string;
    override: boolean;
    confidence: number;
    trigger_count: number;
    status: string;
    scope: string;
    derived_from: string;
    created_at: string;
    updated_at: string;
}

export interface MatchResult {
    rule: Rule;
    score: number;
    match_type: string;
}

export interface EffectivenessReport {
    total_rules: number;
    active: number;
    paused: number;
    deprecated: number;
    triggered: number;
    never_triggered: number;
    trigger_rate: number;
    type_breakdown: Record<string, number>;
    scope_breakdown: Record<string, number>;
    confidence_distribution: Record<string, number>;
    top_triggered: Array<{ id: string; trigger: string; action: string; trigger_count: number }>;
}

export class CarryMemClient {
    private dbPath: string;

    constructor(context: vscode.WorkspaceConfiguration) {
        this.dbPath = context.get<string>('dbPath', '');
    }

    private getDbArg(): string[] {
        return this.dbPath ? ['--db', this.dbPath] : [];
    }

    private async exec(args: string[]): Promise<string> {
        return new Promise((resolve, reject) => {
            execFile('carrymem', args, { timeout: 10000 }, (error, stdout, stderr) => {
                if (error) {
                    reject(new Error(stderr || error.message));
                } else {
                    resolve(stdout);
                }
            });
        });
    }

    private async execJson<T>(args: string[]): Promise<T> {
        const stdout = await this.exec(args);
        try {
            return JSON.parse(stdout) as T;
        } catch {
            throw new Error(`Failed to parse CarryMem output: ${stdout.substring(0, 200)}`);
        }
    }

    async listRules(scope?: string, status?: string): Promise<Rule[]> {
        const args = ['list-rules', '--limit', '200', '--json', ...this.getDbArg()];
        if (scope) {
            args.push('--scope', scope);
        }
        if (status) {
            args.push('--status', status);
        }
        try {
            return await this.execJson<Rule[]>(args);
        } catch {
            return [];
        }
    }

    async addRule(trigger: string, action: string, ruleType: string, scope: string, override: boolean): Promise<Rule> {
        const args = [
            'add-rule', trigger, action,
            '--type', ruleType,
            '--scope', scope,
            '--override', override ? 'true' : 'false',
            '--json',
            ...this.getDbArg(),
        ];
        return this.execJson<Rule>(args);
    }

    async editRule(ruleId: string, updates: Partial<Pick<Rule, 'trigger' | 'action' | 'rule_type' | 'scope' | 'override'>>): Promise<Rule> {
        const args = ['edit-rule', ruleId, '--json', ...this.getDbArg()];
        if (updates.trigger) { args.push('--trigger', updates.trigger); }
        if (updates.action) { args.push('--action', updates.action); }
        if (updates.rule_type) { args.push('--type', updates.rule_type); }
        if (updates.scope) { args.push('--scope', updates.scope); }
        if (updates.override !== undefined) { args.push('--override', updates.override ? 'true' : 'false'); }
        return this.execJson<Rule>(args);
    }

    async deleteRule(ruleId: string): Promise<void> {
        await this.exec(['delete-rule', ruleId, ...this.getDbArg()]);
    }

    async pauseRule(ruleId: string): Promise<Rule> {
        return this.execJson<Rule>(['pause-rule', ruleId, '--json', ...this.getDbArg()]);
    }

    async resumeRule(ruleId: string): Promise<Rule> {
        return this.execJson<Rule>(['resume-rule', ruleId, '--json', ...this.getDbArg()]);
    }

    async matchRules(scene: string): Promise<MatchResult[]> {
        const args = ['match-rules', scene, '--json', ...this.getDbArg()];
        return this.execJson<MatchResult[]>(args);
    }

    async getEffectivenessReport(): Promise<EffectivenessReport> {
        const args = ['rules-effectiveness', '--json', ...this.getDbArg()];
        return this.execJson<EffectivenessReport>(args);
    }

    async skillPack(name: string, scope: string, outputPath: string): Promise<void> {
        await this.exec(['skill-pack', outputPath, '--name', name, '--scope', scope, ...this.getDbArg()]);
    }

    async skillInstall(path: string, scope?: string, mode?: string): Promise<void> {
        const args = ['skill-install', path, ...this.getDbArg()];
        if (scope) { args.push('--scope', scope); }
        if (mode) { args.push('--mode', mode); }
        await this.exec(args);
    }

    async doctor(): Promise<string> {
        return this.exec(['doctor', '--json', ...this.getDbArg()]);
    }

    async isAvailable(): Promise<boolean> {
        try {
            await this.exec(['--version']);
            return true;
        } catch {
            return false;
        }
    }
}
