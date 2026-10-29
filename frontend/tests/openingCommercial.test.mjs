import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {groupConfig,consumeScore,buildScoreReport} from '../src/utils/reviewScoring.js';
const bundle=JSON.parse(fs.readFileSync(new URL('../../desktop/role_bundle.json',import.meta.url),'utf8'));
const people=Object.entries(bundle.personas).filter(([id])=>id!=='source-editor').map(([id,p])=>({id,...p}));
const cfg=groupConfig(people[0].system_prompt);
function rate(c,commercial,opening=8){const scores=Object.fromEntries(c.dimensions.map(d=>[d.id,d.id==='commercial'?commercial:d.id==='opening'?opening:8]));return consumeScore('<review-score>'+JSON.stringify({scores,unrated_reasons:{commercial:'不适用：未见推广依据'}})+'</review-score>',c).rating;}
test('integration and opening contribute by their actual configured weights',()=>{
  assert.equal(rate(cfg,2).score,6.5);assert.equal(rate(cfg,9).score,8.3);assert.equal(rate(cfg,2,2).score,5.6);
});
test('noncommercial is excluded, never given automatic full marks',()=>{assert.equal(rate(cfg,null,4).score,7.2);assert.equal(rate(cfg,null,4).coverage,75);});
test('missing opening or content cannot inflate remaining axes',()=>{
  for(const d of cfg.dimensions.filter(d=>d.id!=='commercial')){const scores=Object.fromEntries(cfg.dimensions.map(x=>[x.id,x.id===d.id?null:8]));const r=consumeScore('<review-score>'+JSON.stringify({scores,unrated_reasons:{[d.id]:'未知'}})+'</review-score>',cfg).rating;assert.equal(r.status,'invalid');}
});
test('all five v11 saved ratings use the same production report math',()=>{
  const responses=people.map(p=>({persona_id:p.id,review_rating:rate(groupConfig(p.system_prompt),2)}));
  const report=buildScoreReport(people,responses);assert.equal(report.complete,true);assert.equal(report.score,6.5);
  const invalid=structuredClone(cfg);invalid.dimensions[0].weight++;invalid.dimensions.at(-1).weight--;assert.equal(groupConfig('<review-group-config>'+JSON.stringify(invalid)+'</review-group-config>'),null);
});
