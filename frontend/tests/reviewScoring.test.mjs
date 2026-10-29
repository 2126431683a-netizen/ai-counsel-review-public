import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { groupConfig, consumeScore, buildScoreReport, combineVerdict } from '../src/utils/reviewScoring.js';
const groups = JSON.parse(fs.readFileSync(new URL('../../desktop/review_groups.json', import.meta.url), 'utf8')).groups;
const personas = groups.map(g => ({ id: g.id, system_prompt: `<review-group-config>${JSON.stringify(g)}</review-group-config>` }));
const payload = (g, value) => `<review-score>${JSON.stringify({ scores: Object.fromEntries(g.dimensions.map(d => [d.id, value])), unrated_reasons: {} })}</review-score>`;

test('raw current-server responses yield fixed two-level weights, hide JSON, copy one table', () => {
  const values = [8, 9, 6, 7, 5];
  const responses = groups.map((g, i) => ({ persona_id: g.id, content: '先看这一步。\n' + payload(g, values[i]) }));
  const report = buildScoreReport(personas, responses);
  assert.equal(report.score, 7.3);
  assert.equal(report.complete, true);
  assert.equal(consumeScore(responses[0].content, groups[0]).content.includes('<review-score>'), false);
  const verdict = combineVerdict('主编建议\n\n### 审稿团加权评分\n模型的旧表', report);
  assert.equal(verdict.match(/审稿团加权评分/g).length, 1);
  assert.match(verdict, /7.3\/10/);
  assert.equal(verdict.includes('模型的旧表'), false);
});

test('missing group, null without reason and nonnumeric score cannot produce total', () => {
  const responses = groups.map(g => ({ persona_id: g.id, content: payload(g, 8) }));
  assert.equal(buildScoreReport(personas, responses.slice(0, 4)).complete, false);
  for (const bad of [null, true, '8', -1, 11]) assert.equal(consumeScore(payload(groups[0], bad), groups[0]).rating.status, 'invalid');
});

test('null dimensions only normalize within a team with >=60% coverage', () => {
  const raw = { scores: { accuracy: 8, evidence: null, scope: 6 }, unrated_reasons: { evidence: '未给实测资料' } };
  const r = consumeScore(`<review-score>${JSON.stringify(raw)}</review-score>`, groups[0]).rating;
  assert.equal(r.coverage, 65);
  assert.equal(r.score, 7.4);
  const low = { scores: { accuracy: null, evidence: 8, scope: 6 }, unrated_reasons: { accuracy: '信息不足' } };
  assert.equal(consumeScore(`<review-score>${JSON.stringify(low)}</review-score>`, groups[0]).rating.status, 'unrated');
});

test('new backend saved dimension ratings are also supported without duplicate footer', () => {
  const responses = groups.map(g => ({ persona_id: g.id, content: '已有评分页脚', review_rating: consumeScore(payload(g, 8), g).rating }));
  assert.equal(buildScoreReport(personas, responses).score, 8);
  assert.equal(consumeScore(responses[0].content, groups[0], responses[0].review_rating).content, '已有评分页脚');
});

test('ordinary old reviews are not retroactively rated', () => {
  assert.equal(groupConfig('普通角色'), null);
  assert.equal(buildScoreReport([{ id: 'old', system_prompt: '普通角色' }], []), null);
  assert.equal(combineVerdict('原来的主编报告', null), '原来的主编报告');
});

test('duplicates and incomplete machine data stay unavailable', () => {
  for (const raw of [payload(groups[0], 8) + payload(groups[0], 8), '<review-score>{', '<review-score>bad</review-score>']) {
    const r = consumeScore(raw, groups[0]);
    assert.equal(r.rating.status, 'invalid');
    assert.equal(r.content.includes('<review-score>'), false);
  }
});

test('real synthetic five-group check agrees with backend decimal result', () => {
  const file = new URL('../../build/group-voice-v4-real-check.json', import.meta.url);
  if (!fs.existsSync(file)) return;
  const real = JSON.parse(fs.readFileSync(file, 'utf8'));
  const responses = real.results.map(r => ({ persona_id: r.id, content: r.content, review_rating: r.rating }));
  assert.equal(buildScoreReport(personas, responses).score, real.scoreReport.score);
});
