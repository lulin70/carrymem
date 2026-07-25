/**
 * Mocha test runner for VSCode extension host.
 *
 * VSCode loads this module via --extensionTestsPath and expects it to:
 * 1. Set up the test framework (mocha)
 * 2. Run the tests
 * 3. Exit with appropriate code
 *
 * The test files (extension.test.js) use mocha BDD syntax (describe/it)
 * but do NOT set up mocha themselves — this runner does that.
 *
 * Usage: referenced by runVscodeTests.js as the extensionTestsPath.
 */

const Mocha = require('mocha');
const path = require('path');

const mocha = new Mocha({
    ui: 'bdd',
    timeout: 30000,
});

// Load the actual test file
mocha.addFile(path.resolve(__dirname, 'extension.test.js'));

// Run tests and exit with appropriate code
mocha.run(failures => {
    // eslint-disable-next-line no-process-exit
    process.exit(failures ? 1 : 0);
});
