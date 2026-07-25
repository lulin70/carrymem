/**
 * Mocha test runner for VSCode extension host.
 *
 * VSCode loads this module via --extensionTestsPath and calls its exported
 * `run` function. The function must return a Promise that resolves on
 * success and rejects on failure.
 *
 * The test files (extension.test.js) use mocha BDD syntax (describe/it)
 * but do NOT set up mocha themselves — this runner does that.
 *
 * VSCode's extension host checks for `exports.run` — if missing, it throws
 * "does not point to a valid extension test runner" (nightly run 30144537953,
 * job 89643749845).
 *
 * Usage: referenced by runVscodeTests.js as the extensionTestsPath.
 */

const Mocha = require('mocha');
const path = require('path');

exports.run = function () {
    return new Promise((resolve, reject) => {
        const mocha = new Mocha({
            ui: 'bdd',
            timeout: 30000,
        });

        // Load the actual test file
        mocha.addFile(path.resolve(__dirname, 'extension.test.js'));

        // Run tests
        mocha.run(failures => {
            if (failures > 0) {
                reject(new Error(`${failures} tests failed`));
            } else {
                resolve();
            }
        });
    });
};
