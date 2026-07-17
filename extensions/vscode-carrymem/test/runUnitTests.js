/**
 * Unit test runner — runs integration tests without VSCode.
 *
 * Usage: node ./out/test/runUnitTests.js
 *
 * This script runs the CarryMemClient integration tests via mocha in a plain
 * Node.js environment (no VSCode required). The vscode module is mocked in
 * the test file itself.
 */

const path = require('path');
const Mocha = require('mocha');

const mocha = new Mocha({
    ui: 'bdd',
    timeout: 10000,
    color: true,
});

mocha.addFile(path.resolve(__dirname, 'carrymemClient.test.js'));

mocha.run((failures) => {
    process.exitCode = failures ? 1 : 0;
});
