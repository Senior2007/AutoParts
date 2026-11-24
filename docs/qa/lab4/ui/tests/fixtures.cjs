const path = require('node:path');
const { randomBytes } = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { test: base } = require('@playwright/test');

function unique() {
  return randomBytes(5).toString('hex');
}

function makeData(mode) {
  const root = path.resolve(__dirname, '../../../../..');
  const python = process.env.QA_PYTHON || 'python3';
  const output = execFileSync(python, ['-m', 'docs.qa', 'fixture', mode, unique()], {
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
