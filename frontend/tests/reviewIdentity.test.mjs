import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { REVIEW_IDENTITIES, reviewIdentity } from '../src/utils/reviewIdentity.js';

test('five saved review settings and chair have distinct stable emblems', () => {
  const bundle = JSON.parse(fs.readFileSync(new URL('../../desktop/role_bundle.json', import.meta.url), 'utf8'));
  const icons = Object.values(bundle.personas).map(reviewIdentity);
  assert.equal(new Set(icons.map(x => x.id)).size, 6);
  assert.deepEqual(icons.map(x => x.id), ['tech','value','fun','think','learn','editor']);
  assert.ok(icons.every(x => x.iconName && x.focus));
});

test('legacy role names resolve with original default emoji', () => {
  assert.equal(reviewIdentity({name:'精打细算实用党',avatar_emoji:'💰'}).id, 'value');
  assert.equal(reviewIdentity({name:'较真技术党',avatar_emoji:'🔧'}).id, 'tech');
  assert.equal(reviewIdentity({name:'主编',avatar_emoji:'📝'}).id, 'editor');
});

test('explicit choice survives role changes; auto resolves settings again', () => {
  assert.equal(reviewIdentity({name:'技术评审团',avatar_emoji:'review:learn'}).id, 'learn');
  assert.equal(reviewIdentity({name:'技术评审团',avatar_emoji:'review:learn'}).focus, '准确性与实测边界');
  assert.equal(reviewIdentity({name:'技术评审团',avatar_emoji:'review:auto'}).id, 'tech');
  assert.equal(reviewIdentity({name:'技术评审团',avatar_emoji:'review:missing'}).id, 'tech');
});

test('new custom groups follow their role while user emoji remains available', () => {
  assert.equal(reviewIdentity({name:'预算评审团',role:'成本评估'}).id, 'value');
  assert.equal(reviewIdentity({name:'随笔团',role:'文稿评审',avatar_emoji:'🐈'}).emoji, '🐈');
  assert.equal(reviewIdentity({name:'随笔团',role:'文稿评审'}).id, 'custom');
  assert.equal(REVIEW_IDENTITIES.length, 7);
});
