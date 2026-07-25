/**
 * VSCode E2E test runner — launches a real VSCode instance and runs tests.
 *
 * Usage: node ./out/test/runVscodeTests.js
 *
 * This downloads a VSCode test instance (~150MB, cached after first run)
 * and launches it with the extension loaded. Tests in extension.test.ts
 * run inside the VSCode extension host.
 *
 * Requirements:
 * - The extension must be compiled first: npm run compile
 * - @vscode/test-electron must be installed: npm install
 *
 * On CI (Linux), this requires xvfb-run. On macOS/Windows, it runs natively.
 */

const path = require('path');
const { runTests } = require('@vscode/test-electron');

async function main() {
    try {
        // The folder containing the Extension Manifest package.json.
        // __dirname is .../extensions/vscode-carrymem/out/test (this file is
        // copied from test/ to out/test/ by the compile script). The extension
        // root (which contains package.json with "main": "./out/src/extension.js")
        // is two levels up: out/test -> out -> extensions/vscode-carrymem.
        // Using one level up (out/) is wrong because VSCode would treat out/
        // as the extension root and fail to resolve ./out/src/extension.js.
        const extensionDevelopmentPath = path.resolve(__dirname, '..', '..');

        // Absolute path to the test runner module.
        // The @vscode/test-electron API requires `extensionTestsPath` (NOT
        // `testsPath`) — see node_modules/@vscode/test-electron/out/runTest.d.ts.
        // Passing `testsPath` silently sets `options.extensionTestsPath` to
        // undefined, which VSCode forwards as `--extensionTestsPath=undefined`,
        // producing "Cannot find module '/undefined'" in the extension host
        // ( nightly run 30140373325, job 89637433895).
        // We point to runTests.js (not extension.test.js) because VSCode's
        // extension host does NOT set up mocha automatically — runTests.js
        // creates a Mocha instance, loads the test files, runs them, and exits.
        // Pointing directly to extension.test.js produces "describe is not
        // defined" (nightly run 30143639995, job 89642688616).
        const extensionTestsPath = path.resolve(__dirname, 'runTests.js');

        // Download VSCode, unzip it, and run the tests via the public runTests API.
        // (Previously used downloadAndRunTests which is not a public export of
        //  @vscode/test-electron — see node_modules/@vscode/test-electron/out/index.d.ts)
        await runTests({
            extensionDevelopmentPath,
            extensionTestsPath,
            // Use stable VSCode version
            version: 'stable',
            // Additional launch arguments
            launchArgs: [
                // Open a temporary workspace
                '--disable-extensions',
            ],
        });
    } catch (err) {
        console.error('VSCode E2E tests failed:');
        console.error(err);
        process.exit(1);
    }
}

main();
