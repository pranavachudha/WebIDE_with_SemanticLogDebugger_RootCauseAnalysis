const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const parser = require('@babel/parser');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const source = html.match(/<script type="text\/babel">([\s\S]*?)<\/script>/)[1];
const names = new Set(['EXAMPLES_FOLDER_ID', 'WORKSPACE_FOLDER_ID', 'loadFiles', 'loadTabs', 'mergeExampleFiles',
  'subtreeIds', 'validWorkspaceName', 'uniqueCopyName', 'DEFAULT_LAYOUT', 'loadLayout', 'safeGetStats']);
const program = parser.parse(source, { plugins: ['jsx'] });
const declarations = program.program.body.filter(node => node.type === 'VariableDeclaration' && node.declarations.some(item => names.has(item.id.name)));
const clean = value => JSON.parse(JSON.stringify(value));

function helpers(saved = {}, width = 1440) {
  const values = new Map(Object.entries(saved).map(([key, value]) => [key, JSON.stringify(value)]));
  const context = vm.createContext({
    window: { innerWidth: width }, console,
    localStorage: { getItem: key => values.get(key) ?? null },
  });
  vm.runInContext(declarations.map(node => source.slice(node.start, node.end)).join('\n'), context);
  return vm.runInContext(`({${[...names].join(',')}})`, context);
}

const diskFile = content => ({ id: 'example:key_error.py', name: 'key_error.py', type: 'file', content,
  examplePath: 'key_error.py', isPredefined: true });

test('unchanged cached examples refresh from disk', () => {
  const h = helpers();
  const result = h.mergeExampleFiles([{ ...diskFile('old'), sourceContent: 'old', parentId: h.EXAMPLES_FOLDER_ID }], { folder_exists: true, files: [diskFile('new')] });
  assert.equal(result.find(file => file.examplePath).content, 'new');
});

test('local example edits survive an external disk refresh', () => {
  const h = helpers();
  const result = h.mergeExampleFiles([{ ...diskFile('my edits'), sourceContent: 'old', parentId: h.EXAMPLES_FOLDER_ID }], { folder_exists: true, files: [diskFile('new disk version')] });
  const file = result.find(file => file.examplePath);
  assert.equal(file.content, 'my edits');
  assert.equal(file.sourceContent, 'new disk version');
  assert.equal(file.isPredefined, true);
});

test('disk deletion removes cached examples while preserving ordinary files', () => {
  const h = helpers();
  const result = h.mergeExampleFiles([diskFile('old'), { id: 'mine', name: 'mine.py', type: 'file', parentId: null, content: 'saved work' }], { folder_exists: true, files: [] });
  assert.equal(result.some(file => file.examplePath), false);
  assert.equal(result.find(file => file.id === 'mine').content, 'saved work');
});

test('custom descendants survive an externally removed example folder', () => {
  const h = helpers();
  const result = h.mergeExampleFiles([{ id: h.EXAMPLES_FOLDER_ID, type: 'folder', isExamplesFolder: true },
    { id: 'mine', type: 'file', name: 'mine.py', parentId: h.EXAMPLES_FOLDER_ID, content: 'work' }], { folder_exists: false, files: [] });
  assert.equal(result.find(file => file.id === 'mine').parentId, h.WORKSPACE_FOLDER_ID);
});

test('legacy browser edits bind to protected disk identities without duplicates', () => {
  const h = helpers();
  const disk = { ...diskFile('disk'), id: 'example:complex_call_stack_error.py', name: 'complex_call_stack_error.py', examplePath: 'complex_call_stack_error.py' };
  const result = h.mergeExampleFiles([{ id: '4', type: 'file', name: disk.name, content: 'legacy work', parentId: null }], { folder_exists: true, files: [disk] });
  const linked = result.filter(file => file.examplePath);
  assert.equal(linked.length, 1);
  assert.equal(linked[0].id, '4');
  assert.equal(linked[0].content, 'legacy work');
  assert.equal(linked[0].isPredefined, true);
});

test('folder nicknames and moves persist across example refreshes', () => {
  const h = helpers();
  const existing = [{ id: h.EXAMPLES_FOLDER_ID, name: 'my examples', type: 'folder', isExamplesFolder: true, isOpen: false },
    { id: 'other', type: 'folder', name: 'other', parentId: null }, { ...diskFile('same'), sourceContent: 'same', parentId: 'other' }];
  const result = h.mergeExampleFiles(existing, { folder_exists: true, files: [diskFile('same')] });
  assert.equal(result.find(file => file.isExamplesFolder).name, 'my examples');
  assert.equal(result.find(file => file.examplePath).parentId, 'other');
});

test('subtree deletion includes every nested tab/file once', () => {
  const h = helpers();
  const ids = h.subtreeIds('folder', [{ id: 'folder' }, { id: 'child', parentId: 'folder' },
    { id: 'nested', parentId: 'child' }, { id: 'unrelated', parentId: null }]);
  assert.deepEqual([...ids].sort(), ['child', 'folder', 'nested']);
});

test('duplicate names remain unique, including case-insensitive siblings', () => {
  const h = helpers();
  assert.equal(h.uniqueCopyName('demo.py', ['DEMO_COPY.PY', 'demo_copy2.py']), 'demo_copy3.py');
  assert.equal(h.uniqueCopyName('folder', ['folder_copy']), 'folder_copy2');
});

test('new names reject paths and reserved Windows names', () => {
  const h = helpers();
  for (const name of ['', '.', '..', '../file.py', 'a/b.py', 'a\\b.py', 'CON.py', 'file.', 'file ']) assert.equal(h.validWorkspaceName(name), false, name);
  assert.equal(h.validWorkspaceName('my_example.py'), true);
});

test('bad cached entries and tab schemas do not crash startup', () => {
  const h = helpers({ pyglide_workspace: [null, { id: 'a', name: 'a.py', content: 'work' }, { id: 'a', name: 'duplicate' }], pyglide_tabs: { wrong: true } });
  assert.equal(h.loadFiles().length, 1);
  assert.equal(h.loadFiles()[0].content, 'work');
  assert.deepEqual(clean(h.loadTabs()), []);
});

test('sidebar preferences are clamped and old preferences get a default width', () => {
  assert.equal(helpers({ pyglide_layout: { explorerWidth: 90000 } }).loadLayout().explorerWidth, 10000);
  assert.equal(helpers({ pyglide_layout: { explorerWidth: -1 } }).loadLayout().explorerWidth, 160);
  assert.equal(helpers({ pyglide_layout: { consoleVisible: false } }).loadLayout().explorerWidth, 224);
});

test('statistics ignore malformed counts and derive totals from recorded failures', () => {
  const h = helpers({ pyglide_stats: { total: 999, concepts: { valid: 3, negative: -2, text: '12', zero: 0 } } });
  assert.deepEqual(clean(h.safeGetStats()), { concepts: { valid: 3 }, total: 3 });
});
