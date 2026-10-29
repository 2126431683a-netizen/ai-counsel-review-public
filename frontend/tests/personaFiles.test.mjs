import test from 'node:test';
import assert from 'node:assert/strict';
import {parsePersonaFile,decodePersonaFile,personaNameKey} from '../src/utils/personaFiles.js';
import {clampReviewRounds,reviewRoundPlan} from '../src/utils/reviewRounds.js';
test('numbered MD filenames identify composed roles without treating common heading as the name',()=>{
  const text='# 审稿团 v6：共同规则\n先通读全文。\n\n# 技术团\n只按原文判断。';
  const p=parsePersonaFile('01_较真技术党.md',text)[0];
  assert.equal(p.name,'较真技术党');assert.equal(p.system_prompt,text);
});
test('explicit Markdown identity and frontmatter metadata work while instructions remain source data',()=>{
  const p=parsePersonaFile('role.md','---\nname: "叙事团"\nrole: 叙事清晰度\n---\n# 角色：其他\n正文指令原样保存')[0];
  assert.equal(p.name,'叙事团');assert.equal(p.role,'叙事清晰度');assert.match(p.system_prompt,/正文指令原样保存/);
  assert.equal(parsePersonaFile('a.txt','# 人格：新手团\n全文规则')[0].name,'新手团');
});
test('JSON bundle imports personas only, never model or credential settings',()=>{
  const roles=parsePersonaFile('bundle.json',JSON.stringify({personas:{a:{name:'甲',system_prompt:'原样人设'},b:{name:'乙',role:'核对',system_prompt:'另一人设'}},settings:{custom_endpoint_url:'ignored',api_key:'ignored'}}));
  assert.equal(roles.length,2);assert.deepEqual(Object.keys(roles[0]).sort(),['name','role','description','system_prompt','avatar_emoji'].sort());
});
test('malformed, unsupported, empty and excessive file payloads fail without creating partial roles',()=>{
  assert.throws(()=>parsePersonaFile('a.json','{'));
  assert.throws(()=>parsePersonaFile('a.exe','正文'));
  assert.throws(()=>parsePersonaFile('a.md',''));
  assert.throws(()=>parsePersonaFile('a.json','{"name":{},"system_prompt":"正文"}'));
  assert.throws(()=>parsePersonaFile('a.json',JSON.stringify(Array.from({length:21},()=>({name:'a',system_prompt:'b'})))));
});
test('UTF-8 and Windows UTF-16 BOM roles decode; invalid bytes are rejected',()=>{
  assert.equal(decodePersonaFile(new TextEncoder().encode('中文')),'中文');
  assert.equal(decodePersonaFile(Uint8Array.from([255,254,45,78,135,101])),'中文');
  assert.throws(()=>decodePersonaFile(Uint8Array.from([255,255,255])));
  assert.equal(personaNameKey(' 技术 团 '),'技术 团');
});
test('rounds allow one/two and clamp integers, while plan separates chair from review count',()=>{
  for(const n of [1,2,3,10])assert.equal(clampReviewRounds(n),n);
  assert.equal(clampReviewRounds(2.8),2);assert.equal(clampReviewRounds(NaN),3);assert.equal(clampReviewRounds(99),10);
  assert.equal(reviewRoundPlan(1),'独立审阅 → 主编汇总');
  assert.match(reviewRoundPlan(2),/交叉复核/);assert.match(reviewRoundPlan(4),/第4轮/);
});
