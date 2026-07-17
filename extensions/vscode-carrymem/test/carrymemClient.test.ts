/**
 * Integration tests for CarryMemClient (Tier 1 — CI-runnable, no VSCode required).
 *
 * These tests verify the CLI bridge logic by mocking `child_process.execFile`
 * and asserting that the client constructs correct CLI arguments and parses
 * responses properly. They do NOT require a running VSCode instance.
 *
 * User journeys covered:
 * - Rule CRUD: add → list → edit → delete
 * - Rule toggle: pause → resume
 * - Rule matching: match-rules scene
 * - Effectiveness report
 * - Availability check
 *
 * NOTE: This test mocks the `vscode` module via Node's require cache before
 * importing CarryMemClient. The client only uses `vscode.WorkspaceConfiguration`
 * (an interface), so a minimal mock suffices.
 */

import * as assert from 'assert';
import * as cp from 'child_process';

// === Mock vscode module BEFORE importing CarryMemClient ===
// CarryMemClient constructor expects a WorkspaceConfiguration-like object.
// We bypass the vscode import by mocking the module in the require cache.
const mockConfig = {
    get: <T>(key: string, defaultValue: T): T => {
        if (key === 'dbPath') { return '' as unknown as T; }
        return defaultValue;
    },
};

const vscodeMock = {
    workspace: { getConfiguration: () => mockConfig },
    // Stub other APIs that might be imported transitively
    window: {},
    commands: {},
    TreeItem: class {},
    TreeItemCollapsibleState: { None: 0 },
    ThemeIcon: class {},
    ThemeColor: class {},
    EventEmitter: class {},
    ViewColumn: { One: 1 },
};

// Register the mock before any src/ module is loaded
const Module = require('module');
const originalResolve = (Module as any)._resolveFilename;
(Module as any)._resolveFilename = function (request: string, ...args: any[]) {
    if (request === 'vscode') { return 'vscode-mock'; }
    return originalResolve.call(this, request, ...args);
};
require.cache['vscode-mock'] = { exports: vscodeMock, loaded: true } as any;

// NOW import the module under test
import { CarryMemClient, Rule, MatchResult, EffectivenessReport } from '../src/carrymemClient';

// === Test fixtures ===

const SAMPLE_RULE: Rule = {
    id: 'rule-001',
    trigger: 'database',
    action: 'Always use SSL connections',
    rule_type: 'always',
    override: false,
    confidence: 0.95,
    trigger_count: 3,
    status: 'active',
    scope: 'personal',
    derived_from: 'manual',
    created_at: '2026-07-17T00:00:00Z',
    updated_at: '2026-07-17T00:00:00Z',
};

const SAMPLE_MATCH: MatchResult = {
    rule: SAMPLE_RULE,
    score: 0.85,
    match_type: 'keyword',
};

const SAMPLE_REPORT: EffectivenessReport = {
    total_rules: 10,
    active: 8,
    paused: 1,
    deprecated: 1,
    triggered: 5,
    never_triggered: 5,
    trigger_rate: 0.5,
    type_breakdown: { always: 4, prefer: 3, forbid: 2, avoid: 1 },
    scope_breakdown: { personal: 7, company: 3 },
    confidence_distribution: { high: 6, medium: 3, low: 1 },
    top_triggered: [{ id: 'rule-001', trigger: 'database', action: 'SSL', trigger_count: 3 }],
};

// === Mock helper ===

interface MockCall {
    cmd: string;
    args: string[];
}

function createMockClient(
    stdout: string = '',
    error: Error | null = null,
): { client: CarryMemClient; calls: MockCall[] } {
    const calls: MockCall[] = [];
    (cp as any).execFile = (cmd: string, args: string[], opts: any, cb: Function) => {
        calls.push({ cmd, args });
        if (error) {
            cb(error, '', error.message);
        } else {
            cb(null, stdout, '');
        }
    };
    const client = new CarryMemClient(mockConfig as any);
    return { client, calls };
}

// === Tests ===

describe('CarryMemClient — CLI bridge integration', () => {

    describe('Rule CRUD journey', () => {

        it('addRule: constructs correct CLI arguments', async () => {
            const { client, calls } = createMockClient(JSON.stringify(SAMPLE_RULE));
            const rule = await client.addRule('database', 'Use SSL', 'always', 'personal', false);
            assert.strictEqual(rule.id, 'rule-001');
            assert.strictEqual(calls.length, 1);
            assert.strictEqual(calls[0].cmd, 'carrymem');
            assert.strictEqual(calls[0].args[0], 'add-rule');
            assert.strictEqual(calls[0].args[1], 'database');
            assert.strictEqual(calls[0].args[2], 'Use SSL');
            assert(calls[0].args.includes('--type'));
            assert(calls[0].args.includes('always'));
            assert(calls[0].args.includes('--scope'));
            assert(calls[0].args.includes('personal'));
            assert(calls[0].args.includes('--json'));
        });

        it('listRules: returns parsed rules array', async () => {
            const { client, calls } = createMockClient(JSON.stringify([SAMPLE_RULE]));
            const rules = await client.listRules();
            assert.strictEqual(rules.length, 1);
            assert.strictEqual(rules[0].trigger, 'database');
            assert(calls[0].args.includes('list-rules'));
            assert(calls[0].args.includes('--limit'));
            assert(calls[0].args.includes('200'));
            assert(calls[0].args.includes('--json'));
        });

        it('listRules: returns empty array on CLI error (graceful degradation)', async () => {
            const { client } = createMockClient('', new Error('carrymem not found'));
            const rules = await client.listRules();
            assert.deepStrictEqual(rules, []);
        });

        it('editRule: passes update fields as CLI flags', async () => {
            const { client, calls } = createMockClient(JSON.stringify(SAMPLE_RULE));
            await client.editRule('rule-001', { trigger: 'db', action: 'Use TLS' });
            assert.strictEqual(calls[0].args[0], 'edit-rule');
            assert.strictEqual(calls[0].args[1], 'rule-001');
            assert(calls[0].args.includes('--trigger'));
            assert(calls[0].args.includes('db'));
            assert(calls[0].args.includes('--action'));
            assert(calls[0].args.includes('Use TLS'));
        });

        it('deleteRule: calls delete-rule command', async () => {
            const { client, calls } = createMockClient('');
            await client.deleteRule('rule-001');
            assert.strictEqual(calls[0].args[0], 'delete-rule');
            assert.strictEqual(calls[0].args[1], 'rule-001');
        });
    });

    describe('Rule toggle journey', () => {

        it('pauseRule: calls pause-rule with --json', async () => {
            const pausedRule = { ...SAMPLE_RULE, status: 'paused' };
            const { client, calls } = createMockClient(JSON.stringify(pausedRule));
            const result = await client.pauseRule('rule-001');
            assert.strictEqual(result.status, 'paused');
            assert.strictEqual(calls[0].args[0], 'pause-rule');
            assert(calls[0].args.includes('--json'));
        });

        it('resumeRule: calls resume-rule with --json', async () => {
            const { client, calls } = createMockClient(JSON.stringify(SAMPLE_RULE));
            const result = await client.resumeRule('rule-001');
            assert.strictEqual(result.status, 'active');
            assert.strictEqual(calls[0].args[0], 'resume-rule');
        });
    });

    describe('Rule matching journey', () => {

        it('matchRules: passes scene to match-rules', async () => {
            const { client, calls } = createMockClient(JSON.stringify([SAMPLE_MATCH]));
            const matches = await client.matchRules('security review');
            assert.strictEqual(matches.length, 1);
            assert.strictEqual(matches[0].score, 0.85);
            assert.strictEqual(calls[0].args[0], 'match-rules');
            assert.strictEqual(calls[0].args[1], 'security review');
            assert(calls[0].args.includes('--json'));
        });
    });

    describe('Effectiveness report journey', () => {

        it('getEffectivenessReport: parses report structure', async () => {
            const { client, calls } = createMockClient(JSON.stringify(SAMPLE_REPORT));
            const report = await client.getEffectivenessReport();
            assert.strictEqual(report.total_rules, 10);
            assert.strictEqual(report.active, 8);
            assert.strictEqual(report.trigger_rate, 0.5);
            assert.strictEqual(Object.keys(report.type_breakdown).length, 4);
            assert.strictEqual(calls[0].args[0], 'rules-effectiveness');
        });
    });

    describe('Availability check', () => {

        it('isAvailable: returns true when --version succeeds', async () => {
            const { client } = createMockClient('carrymem 0.8.0');
            const available = await client.isAvailable();
            assert.strictEqual(available, true);
        });

        it('isAvailable: returns false on error', async () => {
            const { client } = createMockClient('', new Error('not found'));
            const available = await client.isAvailable();
            assert.strictEqual(available, false);
        });
    });

    describe('DB path configuration', () => {

        it('passes --db flag when dbPath is configured', async () => {
            const configWithDb = {
                get: <T>(key: string, defaultValue: T): T => {
                    if (key === 'dbPath') { return '/custom/path.db' as unknown as T; }
                    return defaultValue;
                },
            };
            const calls: MockCall[] = [];
            (cp as any).execFile = (cmd: string, args: string[], opts: any, cb: Function) => {
                calls.push({ cmd, args });
                cb(null, JSON.stringify([SAMPLE_RULE]), '');
            };
            const client = new CarryMemClient(configWithDb as any);
            // listRules includes --db flag (isAvailable does not, by design)
            await client.listRules();
            assert(calls[0].args.includes('--db'));
            assert(calls[0].args.includes('/custom/path.db'));
        });
    });

    describe('Error handling', () => {

        it('execJson: throws on invalid JSON (via addRule which does not catch)', async () => {
            const { client } = createMockClient('not json');
            await assert.rejects(
                client.addRule('trigger', 'action', 'always', 'personal', false),
                /Failed to parse CarryMem output/,
            );
        });

        it('exec: rejects on CLI error with stderr', async () => {
            const { client } = createMockClient('', new Error('command failed'));
            await assert.rejects(
                client.deleteRule('rule-001'),
                /command failed/,
            );
        });
    });
});
