const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function loadTypeScriptModule(relativePath) {
  const filename = path.join(__dirname, relativePath);
  const source = fs.readFileSync(filename, 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(compiled, {
    exports: module.exports,
    module,
    require,
  }, { filename });
  return module.exports;
}

const { jobProgressLabel, jobResultSummary } = loadTypeScriptModule('job-detail.ts');

test('jobProgressLabel includes step and progress percent', () => {
  assert.equal(jobProgressLabel({ meta: { step: 'running evaluation', progress: 40 } }), 'running evaluation (40%)');
});

test('jobResultSummary surfaces returned stdout and errors', () => {
  assert.equal(jobResultSummary({ result: { stdout: 'done', stderr: '' } }), 'done');
  assert.equal(jobResultSummary({ error: 'boom' }), 'boom');
});
