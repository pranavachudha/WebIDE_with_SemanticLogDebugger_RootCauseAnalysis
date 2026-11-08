const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'pyworker.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));

function worker(load) {
  const messages = [];
  const context = { importScripts() {}, loadPyodide: load, postMessage: value => messages.push(value) };
  context.self = context;
  vm.runInNewContext(source, context);
  return { context, messages };
}

test('runtime announces readiness only after Python initialization completes', async () => {
  let ready;
  const pending = new Promise(resolve => { ready = resolve; });
  const { messages } = worker(() => pending);
  assert.equal(messages.length, 0);
  ready({ globals: { set() {} }, async runPythonAsync() {}, setStdin() {} });
  await settle();
  assert.deepEqual(messages.map(message => message.type), ['ready']);
});

test('initialization failures are explicit and queued runs fail without hanging', async () => {
  const { context, messages } = worker(async () => { throw new Error('download failed'); });
  await settle();
  assert.equal(messages[0].type, 'init_error');
  await context.onmessage({ data: { type: 'run', id: 'run_main', code: 'print(1)' } });
  assert.equal(messages.at(-1).type, 'error');
  assert.equal(messages.at(-1).id, 'run_main');
});

test('execution errors retain their operation identity', async () => {
  const { context, messages } = worker(async () => ({ globals: { set() {} }, setStdin() {},
    async runPythonAsync(code) { if (code === 'bad code') throw new Error('SyntaxError: fixture'); } }));
  await settle();
  await context.onmessage({ data: { type: 'run', id: 'example-run', code: 'bad code' } });
  assert.equal(messages.at(-1).type, 'error');
  assert.equal(messages.at(-1).id, 'example-run');
});
