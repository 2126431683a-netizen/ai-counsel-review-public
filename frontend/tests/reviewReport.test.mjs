import test from 'node:test';
import assert from 'node:assert/strict';
import {reportChapters,reportAxisRows,reportTableModel} from '../src/utils/reviewReport.js';

test('report chapters preserve body order, tables, subordinate headings and literal fenced headings',()=>{
  const source='## 结论\n\n原结论。\n\n### 限定\n仍需核对。\n\n## 修改方向\n\n|位置|建议|\n|---|---|\n|开头|前移结果|\n\n````md\n## 不是章节\n```\n保留代码\n````\n\n## 交付检查\n\n最后检查。';
  const chapters=reportChapters(source);
  assert.deepEqual(chapters.map(c=>c.title),['结论','修改方向','交付检查']);
  assert.match(chapters[0].body,/### 限定\n仍需核对/);
  assert.match(chapters[1].body,/\|开头\|前移结果\|/);
  assert.match(chapters[1].body,/## 不是章节\n```\n保留代码/);
  assert.equal(chapters[2].body,'最后检查。');
});
test('unstructured text and empty titled sections do not disappear',()=>{
  assert.deepEqual(reportChapters(''),[]);
  assert.equal(reportChapters('完整正文。')[0].body,'完整正文。');
  assert.deepEqual(reportChapters('## 空标题\n\n## 结论\n内容。').map(c=>[c.title,c.body]),[['空标题',''],['结论','内容。']]);
});
test('analysis axes use existing dimension weights and distinguish commercial N/A',()=>{
  const group={persona_id:'p',score:6.4,dimensions:[{id:'a',score:4,weight:30},{id:'b',score:8,weight:20},{id:'c',score:6,weight:10},{id:'opening',score:7,weight:15},{id:'commercial',score:null,weight:25,reason:'不适用：没有推广'}]};
  const before=JSON.stringify(group);
  const axes=reportAxisRows({groups:[group]})[0].axes;
  assert.deepEqual(axes.map(a=>a.score),[5.7,7,null]);
  assert.match(axes[2].reason,/不适用/);assert.equal(JSON.stringify(group),before);
});
test('unverified groups, absent old axes and missing content never produce invented scores',()=>{
  const missing={persona_id:'p',score:null,reason:'依据缺失',dimensions:[{id:'a',score:8,weight:100}]};
  assert.deepEqual(reportAxisRows({groups:[missing]})[0].axes.map(a=>a.score),[null,null,null]);
  const old={...missing,score:0,dimensions:[{id:'a',score:0,weight:100}]};
  assert.deepEqual(reportAxisRows({groups:[old]})[0].axes.map(a=>a.score),[0,null,null]);
});
test('table visuals use source headers and cells rather than synthesizing stage or decision content',()=>{
  const table=rows=>({tagName:'table',children:rows.map(row=>({tagName:'tr',children:row.map(value=>({tagName:'td',children:[{type:'text',value}]}))}))});
  assert.deepEqual(reportTableModel(table([['阶段','已有信息','尚未交代'],['前15秒附近','痛点','方法']])),{headers:['阶段','已有信息','尚未交代'],rows:[['前15秒附近','痛点','方法']],kind:'stages'});
  assert.equal(reportTableModel(table([['真实意见','处理','依据'],['入口不明','采纳','原稿未说明入口']])).kind,'decisions');
  assert.equal(reportTableModel(table([['产品','评分'],['A','6']])).kind,'table');
});
