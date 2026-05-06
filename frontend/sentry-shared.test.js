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

const { scrubSentryData } = loadTypeScriptModule('sentry-shared.ts');

test('scrubSentryData redacts sensitive keys recursively', () => {
  const scrubbed = scrubSentryData({
    request: {
      headers: {
        Authorization: 'Bearer token-123',
        Cookie: 'session=secret',
        'X-Request-ID': 'req-1',
      },
    },
    extra: {
      refresh_token: 'refresh-123',
      nested: [{ client_secret: 'google-secret' }],
    },
  });

  assert.equal(scrubbed.request.headers.Authorization, '[Filtered]');
  assert.equal(scrubbed.request.headers.Cookie, '[Filtered]');
  assert.equal(scrubbed.request.headers['X-Request-ID'], 'req-1');
  assert.equal(scrubbed.extra.refresh_token, '[Filtered]');
  assert.equal(scrubbed.extra.nested[0].client_secret, '[Filtered]');
});

test('scrubSentryData redacts sensitive strings', () => {
  assert.equal(
    scrubSentryData('Authorization: Bearer token-123'),
    'Authorization: Bearer [Filtered]'
  );
  assert.equal(scrubSentryData('refresh_token=refresh-123'), 'refresh_token=[Filtered]');
  assert.equal(scrubSentryData('client_secret: google-secret'), 'client_secret: [Filtered]');
  assert.equal(
    scrubSentryData('SENTRY_DSN=https://abc@sentry.invalid/1'),
    'SENTRY_DSN=[Filtered]'
  );
});
