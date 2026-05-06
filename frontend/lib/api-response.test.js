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

const { readApiResponse } = loadTypeScriptModule('api-response.ts');

function response(status, body, contentType = 'application/json') {
  return new Response(body, {
    status,
    headers: { 'content-type': contentType },
  });
}

test('readApiResponse returns parsed data for successful JSON responses', async () => {
  const result = await readApiResponse(response(200, JSON.stringify({ job_id: 'job-123' })));

  assert.equal(result.ok, true);
  assert.deepEqual(result.data, { job_id: 'job-123' });
});

test('readApiResponse maps unauthorized responses to a sign-in message', async () => {
  const result = await readApiResponse(response(401, JSON.stringify({ error: 'missing token' })));

  assert.equal(result.ok, false);
  assert.equal(result.error, 'Your sign-in session expired. Please sign in again.');
});

test('readApiResponse maps forbidden responses to a permission message', async () => {
  const result = await readApiResponse(response(403, JSON.stringify({ error: 'forbidden' })));

  assert.equal(result.ok, false);
  assert.equal(result.error, 'You do not have permission to access this resource.');
});

test('readApiResponse maps auth service outages to a retryable message', async () => {
  const result = await readApiResponse(response(503, JSON.stringify({ error: 'jwks unavailable' })));

  assert.equal(result.ok, false);
  assert.equal(result.error, 'Authentication service is temporarily unavailable. Please retry in a moment.');
});

test('readApiResponse handles non-JSON error responses without throwing', async () => {
  const result = await readApiResponse(response(500, '<html>error</html>', 'text/html'), 'Pipeline request failed');

  assert.equal(result.ok, false);
  assert.equal(result.error, 'Pipeline request failed');
  assert.deepEqual(Object.keys(result.data), []);
});

test('readApiResponse handles invalid JSON error responses without throwing', async () => {
  const result = await readApiResponse(response(500, '{not json'));

  assert.equal(result.ok, false);
  assert.equal(result.error, 'Request failed');
});
