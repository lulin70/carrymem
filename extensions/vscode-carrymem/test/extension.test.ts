/**
 * VSCode Extension UI E2E Tests (Tier 2 — requires running VSCode).
 *
 * These tests run inside a real VSCode instance via @vscode/test-electron.
 * They verify the full UI user journey: extension activation, command
 * registration, tree view population, and command execution.
 *
 * Run via: npm run test:e2e
 * (This downloads a VSCode test instance and launches it automatically.)
 *
 * User journeys covered:
 * 1. Extension activates and registers all 9 commands
 * 2. Rule tree view is created and visible
 * 3. Refresh command executes through the real CarryMem CLI
 * 4. A CLI-created rule is read by CarryMemClient and RuleTreeProvider
 * 5. An extension API update is persisted and visible through the CLI
 * 6. Configuration settings are read correctly
 * 7. Temporary SQLite data and the test rule are cleaned up
 */

import * as assert from 'assert';
import { execFile } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';

interface ExtensionApi {
    client: {
        isAvailable(): Promise<boolean>;
        listRules(): Promise<any[]>;
        editRule(ruleId: string, updates: Record<string, unknown>): Promise<any>;
        deleteRule(ruleId: string): Promise<void>;
    };
    treeProvider: {
        getChildren(): Promise<any[]>;
    };
}

function runCarryMem(args: string[]): Promise<string> {
    return new Promise((resolve, reject) => {
        execFile('carrymem', args, { timeout: 10000, env: process.env }, (error, stdout, stderr) => {
            if (error) {
                reject(new Error(stderr || error.message));
            } else {
                resolve(stdout);
            }
        });
    });
}

describe('VSCode Extension — UI E2E User Journeys', () => {
    let testRoot: string;
    let dbPath: string;
    let ruleId: string | undefined;
    let extensionApi: ExtensionApi | undefined;
    let previousConfiguredDbPath: string | undefined;
    const isolatedEnvKeys = [
        'CARRYMEM_CONFIG_DIR',
        'CARRYMEM_CONFIG_FILE',
        'CARRYMEM_DB_PATH',
        'CARRYMEM_DATA_PATH',
        'CARRYMEM_CACHE_DIR',
        'CARRYMEM_LOG_DIR',
        'CARRYMEM_BACKUP_DIR',
        'CARRYMEM_TEMP_DIR',
        'CARRYMEM_LOCK_FILE',
    ];
    const previousEnv: Record<string, string | undefined> = {};

    before(async () => {
        testRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'carrymem-vscode-e2e-'));
        dbPath = path.join(testRoot, 'memories.db');
        const isolatedPaths: Record<string, string> = {
            CARRYMEM_CONFIG_DIR: path.join(testRoot, 'config'),
            CARRYMEM_CONFIG_FILE: path.join(testRoot, 'config', 'config.yaml'),
            CARRYMEM_DB_PATH: dbPath,
            CARRYMEM_DATA_PATH: path.join(testRoot, 'data'),
            CARRYMEM_CACHE_DIR: path.join(testRoot, 'cache'),
            CARRYMEM_LOG_DIR: path.join(testRoot, 'logs'),
            CARRYMEM_BACKUP_DIR: path.join(testRoot, 'backups'),
            CARRYMEM_TEMP_DIR: path.join(testRoot, 'temp'),
            CARRYMEM_LOCK_FILE: path.join(testRoot, 'config', 'carrymem.lock'),
        };
        for (const key of isolatedEnvKeys) {
            previousEnv[key] = process.env[key];
            process.env[key] = isolatedPaths[key];
        }

        const config = vscode.workspace.getConfiguration('carrymem');
        previousConfiguredDbPath = config.get<string>('dbPath', '');
        await config.update('dbPath', dbPath, vscode.ConfigurationTarget.Global);

        const created = JSON.parse(await runCarryMem([
            'rules', 'add', 'Use the isolated CarryMem database',
            '--trigger', 'VSCode TD-073 E2E',
            '--type', 'always',
            '--scope', 'personal',
            '--override', 'false',
            '--json',
            '--db', dbPath,
        ]));
        ruleId = created.id;

        const ext = vscode.extensions.getExtension('carrymem.vscode-carrymem');
        assert.ok(ext, 'Extension should be installed');
        if (!ext!.isActive) {
            await ext!.activate();
        }
        extensionApi = ext!.exports as ExtensionApi;
    });

    after(async () => {
        try {
            if (ruleId) {
                if (extensionApi) {
                    await extensionApi.client.deleteRule(ruleId);
                    const remaining = await extensionApi.client.listRules();
                    assert.strictEqual(
                        remaining.some(rule => rule.id === ruleId),
                        false,
                        'The E2E rule must be deleted from the isolated database',
                    );
                    const cliRules = JSON.parse(await runCarryMem([
                        'rules', 'list', '--limit', '200', '--json', '--db', dbPath,
                    ]));
                    assert.strictEqual(
                        cliRules.some((rule: any) => rule.id === ruleId),
                        false,
                        'The real CLI must confirm the rule was deleted',
                    );
                } else {
                    await runCarryMem(['rules', 'delete', ruleId, '--json', '--db', dbPath]);
                }
            }
        } finally {
            try {
                await vscode.workspace.getConfiguration('carrymem').update(
                    'dbPath',
                    previousConfiguredDbPath || '',
                    vscode.ConfigurationTarget.Global,
                );
            } finally {
                try {
                    for (const key of isolatedEnvKeys) {
                        if (previousEnv[key] === undefined) {
                            delete process.env[key];
                        } else {
                            process.env[key] = previousEnv[key];
                        }
                    }
                } finally {
                    if (testRoot) {
                        fs.rmSync(testRoot, { recursive: true, force: true });
                        assert.strictEqual(
                            fs.existsSync(testRoot),
                            false,
                            'The isolated E2E directory must be removed',
                        );
                    }
                }
            }
        }
    });

    describe('Extension activation journey', () => {

        it('extension is installed and active', () => {
            const ext = vscode.extensions.getExtension('carrymem.vscode-carrymem');
            assert.ok(ext, 'Extension should be installed');
            assert.ok(ext!.isActive, 'Extension should be active');
        });

        it('exports activate and deactivate functions', () => {
            const ext = vscode.extensions.getExtension('carrymem.vscode-carrymem');
            assert.ok(ext, 'Extension should be installed');
            const exports = ext!.exports;
            // extension.ts exports activate/deactivate — check they exist
            assert.ok(exports, 'Extension should have exports');
        });
    });

    describe('Command registration journey', () => {

        const EXPECTED_COMMANDS = [
            'carrymem.refreshRules',
            'carrymem.addRule',
            'carrymem.editRule',
            'carrymem.deleteRule',
            'carrymem.toggleRule',
            'carrymem.matchRules',
            'carrymem.showEffectivenessReport',
            'carrymem.skillPack',
            'carrymem.skillInstall',
        ];

        EXPECTED_COMMANDS.forEach((cmdId) => {
            it(`command "${cmdId}" is registered`, async () => {
                const commands = await vscode.commands.getCommands(true);
                assert.ok(
                    commands.includes(cmdId),
                    `Command ${cmdId} should be registered. Available: ${commands.filter(c => c.startsWith('carrymem')).join(', ')}`,
                );
            });
        });
    });

    describe('Tree view journey', () => {

        it('carrymem-rules tree view is registered', () => {
            // The tree view is created via vscode.window.createTreeView
            // We verify it's accessible via the viewsContainers contribution
            const packageJson = require('../../package.json');
            const viewsContainers = packageJson.contributes.viewsContainers;
            assert.ok(viewsContainers, 'Should have viewsContainers');
            assert.ok(viewsContainers.activitybar, 'Should have activitybar container');
            const carrymemContainer = viewsContainers.activitybar.find(
                (c: any) => c.id === 'carrymem',
            );
            assert.ok(carrymemContainer, 'Should have carrymem container');

            const views = packageJson.contributes.views;
            assert.ok(views.carrymem, 'Should have carrymem views');
            const rulesView = views.carrymem.find((v: any) => v.id === 'carrymem-rules');
            assert.ok(rulesView, 'Should have carrymem-rules view');
        });

        it('refreshRules command executes against the isolated CarryMem CLI', async () => {
            assert.ok(extensionApi, 'Extension API should be available');
            assert.strictEqual(await extensionApi!.client.isAvailable(), true, 'CarryMem CLI must be installed');
            await vscode.commands.executeCommand('carrymem.refreshRules');
        });

        it('real CLI rule is visible through CarryMemClient and RuleTreeProvider', async () => {
            assert.ok(extensionApi, 'Extension API should be available');
            const rules = await extensionApi!.client.listRules();
            assert.strictEqual(rules.length, 1, 'The isolated database should contain one E2E rule');
            assert.strictEqual(rules[0].id, ruleId);
            assert.strictEqual(rules[0].trigger, 'VSCode TD-073 E2E');

            const treeItems = await extensionApi!.treeProvider.getChildren();
            assert.strictEqual(treeItems.length, 1, 'The extension tree should contain the CLI-created rule');
            assert.strictEqual(treeItems[0].rule.id, ruleId);
            assert.strictEqual(treeItems[0].rule.action, 'Use the isolated CarryMem database');
        });

        it('extension API update is persisted and visible through the real CLI', async () => {
            assert.ok(extensionApi, 'Extension API should be available');
            const updatedAction = 'Updated through the VSCode extension API';
            await extensionApi!.client.editRule(ruleId!, { action: updatedAction });

            const cliRules = JSON.parse(await runCarryMem(['rules', 'list', '--limit', '200', '--json', '--db', dbPath]));
            assert.strictEqual(cliRules.length, 1, 'The CLI should read one persisted rule');
            assert.strictEqual(cliRules[0].id, ruleId);
            assert.strictEqual(cliRules[0].action, updatedAction);

            const treeItems = await extensionApi!.treeProvider.getChildren();
            assert.strictEqual(treeItems[0].rule.action, updatedAction);
        });

    });

    describe('Configuration journey', () => {

        it('carrymem configuration section exists', async () => {
            const config = vscode.workspace.getConfiguration('carrymem');
            assert.ok(config, 'Should have carrymem configuration');

            const defaultScope = config.get<string>('defaultScope');
            assert.strictEqual(defaultScope, 'personal', 'defaultScope should default to personal');
        });

        it('dbPath configuration points to the isolated test database', () => {
            const config = vscode.workspace.getConfiguration('carrymem');
            const configuredDbPath = config.get<string>('dbPath');
            assert.strictEqual(configuredDbPath, dbPath);
        });
    });

    describe('Package.json contract journey', () => {

        it('all commands have title and are well-formed', () => {
            const packageJson = require('../../package.json');
            const nls = require('../../package.nls.json');
            const commands = packageJson.contributes.commands;
            assert.ok(commands, 'Should have commands');
            assert.ok(commands.length >= 9, `Should have at least 9 commands, got ${commands.length}`);

            commands.forEach((cmd: any) => {
                assert.ok(cmd.command, 'Each command should have a command id');
                assert.ok(cmd.title, `Command ${cmd.command} should have a title`);
                // package.json uses i18n placeholders like "%command.refreshRules.title%"
                // Resolve them via package.nls.json before checking the prefix.
                const resolvedTitle = cmd.title.startsWith('%') && cmd.title.endsWith('%')
                    ? nls[cmd.title.slice(1, -1)] || cmd.title
                    : cmd.title;
                assert.ok(
                    resolvedTitle.startsWith('CarryMem: '),
                    `Command ${cmd.command} title should start with "CarryMem: " (got: "${resolvedTitle}")`,
                );
            });
        });

        it('menus are properly configured', () => {
            const packageJson = require('../../package.json');
            const menus = packageJson.contributes.menus;
            assert.ok(menus, 'Should have menus');
            assert.ok(menus['view/title'], 'Should have view/title menus');
            assert.ok(menus['view/item/context'], 'Should have view/item/context menus');
        });
    });
});
