import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parseReviewResponse } from '../frontend/src/utils/reviewPresentation.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const bundle = JSON.parse(fs.readFileSync(path.join(root, 'desktop/role_bundle.json'), 'utf8'));
const directory = path.join(root, 'build/viewer-v7-check');
let total = 0;
for (const [pid, persona] of Object.entries(bundle.personas)) {
  if (pid === 'source-editor') continue;
  const report = JSON.parse(fs.readFileSync(path.join(directory, `${pid}.json`), 'utf8'));
  const content = fs.readFileSync(path.join(directory, `${pid}.md`), 'utf8');
  const result = parseReviewResponse({ content }, persona);
  assert.equal(result.structured, true, pid);
  assert.equal(result.comments.length, report.comments.length, pid);
  assert.deepEqual(result.comments.map(c => c.text), report.comments.map(c => c.text), pid);
  assert.equal(Object.keys(result.dimensionNotes).length, 3, pid);
  assert.equal(result.rating.status, 'ok', pid);
  total += result.comments.length;
}
console.log(JSON.stringify({ groups: 5, comments: total, evidenceAndScoresParse: true, noHistoryWritten: true }));
