const path = require('node:path');
const { randomBytes } = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { test: base } = require('@playwright/test');

function unique() {
  return randomBytes(5).toString('hex');
}

function makeData(mode) {
  const root = process.env.QA_PROJECT_DIR;
  if (!root) throw new Error('Укажите QA_PROJECT_DIR с копией стенда и файлом .qa-scratch.');
  const python = process.env.QA_PYTHON || 'python3';
  const script = path.resolve(__dirname, '../../../stand/fixtures.py');
  const output = execFileSync(python, [script, 'ui', mode, unique()], {
    cwd: root,
    encoding: 'utf8',
  });
  return JSON.parse(output);
}

const test = base.extend({
  newPart: async ({}, use) => use(makeData('part')),
  manyParts: async ({}, use) => use(makeData('large')),
  username: async ({}, use) => use('qa_ui_' + unique()),
});

module.exports = { test };
