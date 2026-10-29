import test from 'node:test';
import assert from 'node:assert/strict';
import { parseReviewResponse, roundComments, reviewGroupName, reviewQuoteStatus } from '../src/utils/reviewPresentation.js';

test('paragraph comments show first, memo stays separate and is explicitly group-level', () => {
  const text = '入口会放出来吗？\n\n---\n\n先看它分错以后怎么改。\n\n### 给作者的备忘\n原文已安排录屏，交付前确认即可。';
  const p = parseReviewResponse({ content: text }, { name: '跃跃欲试新手' });
  assert.equal(p.comments.length, 2);
  assert.equal(p.comments[0].text, '入口会放出来吗？');
  assert.equal(p.comments[0].association, 'group');
  assert.match(p.memo, /已安排录屏/);
  assert.equal(p.comments.some(c => c.text.includes('已安排录屏')), false);
});

test('legacy issue reactions retain their own preceding evidence', () => {
  const text = '评分（1-10）：6分\n\n你最在意的3个问题：\n- 原句：“设备A”\n- 问题在哪：这里缺少范围。\n- 你看到这里的真实反应：这个配置是必须的吗？\n\n- 原句：“下一步”\n- 问题在哪：没有连接关系。\n- 你看到这里的真实反应：下一步在哪打开？\n\n共识信号：待讨论';
  const p = parseReviewResponse({ content: text });
  assert.equal(p.legacyScore, 6);
  assert.equal(p.comments.length, 2);
  assert.equal(p.comments[0].text, '这个配置是必须的吗？');
  assert.match(p.comments[1].detail.content, /下一步/);
  assert.equal(p.comments[1].detail.content.includes('设备A'), false);
});

test('verified structured comment rationale is tied to a visible comment', () => {
  const item = { text: '入口在哪？', basis: '原稿：打开页面', context: '后文：接下来演示入口', rationale: '已安排演示，交付时核对覆盖即可', limits: '可能在录屏里', next_step: '确认画面覆盖', kind: '待核实' };
  const p = parseReviewResponse({ content: `入口在哪？\n\n给作者的备忘\n确认录屏。\n<review-comments>${JSON.stringify([item])}</review-comments>` });
  assert.equal(p.structured, true);
  assert.equal(p.comments[0].association, 'comment');
  assert.equal(p.comments[0].detail.basis, '原稿：打开页面');
  assert.equal(p.comments[0].detail.context, '后文：接下来演示入口');
  assert.equal(p.fullText.includes('<review-comments>'), false);
});

test('unmatched or malformed rationale metadata does not invent visible comments', () => {
  const p = parseReviewResponse({ content: '只保留这句。\n\n### 给作者的备忘\n原有备忘。\n<review-comments>[{"text":"模型另造的句子","rationale":"伪关联"}]</review-comments>' });
  assert.equal(p.structured, false);
  assert.equal(p.comments.length, 1);
  assert.equal(p.comments[0].text, '只保留这句。');
  assert.equal(p.comments[0].association, 'group');
  const bad = parseReviewResponse({ content: '可见评论\n<review-comments>{' });
  assert.equal(bad.fullText, '可见评论');
});

test('ordinary bullets are separate reactions, failure responses are not comments', () => {
  const personas = [{ id: 'a', name: '较真技术党' }, { id: 'b', name: '自定义' }];
  const items = roundComments(personas, { responses: [{ persona_id: 'a', content: '**模拟短评**\n- 先核对条件。\n- 这个版本呢？\n\n**给作者的备忘**\n待查。' }, { persona_id: 'b', error: '请求失败', content: '' }] }, 1);
  assert.equal(items.length, 2);
  assert.notEqual(items[0].key, items[1].key);
  assert.equal(reviewGroupName(personas[0]), '技术评审团');
  assert.equal(reviewGroupName(personas[1]), '自定义评审团');
});

test('v6 object keeps verified comments, earlier replies and configured dimension notes',()=>{
  const persona={system_prompt:'<review-group-config>'+JSON.stringify({id:'source-tech',name:'技术团',weight:25,dimensions:[{id:'accuracy',name:'准确',weight:100}]})+'</review-group-config>'};
  const payload={comments:[{id:'one',text:'分工清楚了',basis:'模型写代码'},{id:'two',text:'我更在意后面还能不能改',reply_to:'one',basis:'再修改一处字幕'}],dimension_notes:{accuracy:{basis:'模型写代码',context:'工具渲染',rationale:'稿面分工明确',deduction:'不推定成片已完成'},invented:{rationale:'不得新增维度'}}};
  const p=parseReviewResponse({content:'分工清楚了\n\n我更在意后面还能不能改\n\n给作者的备忘\n简短说明\n<review-comments>'+JSON.stringify(payload)+'</review-comments>'},persona);
  assert.equal(p.structured,true);
  assert.equal(p.comments[1].reply.id,'c-0');
  assert.equal(p.comments[1].reply.text,'分工清楚了');
  assert.equal(p.dimensionNotes.accuracy.rationale,'稿面分工明确');
  assert.equal(p.dimensionNotes.invented,undefined);
  assert.equal(p.fullText.includes('dimension_notes'),false);
});

test('unknown, forward and duplicate reply references cannot invent discussion links',()=>{
  for(const comments of [[{id:'a',text:'甲',reply_to:'b'},{id:'b',text:'乙'}],[{id:'a',text:'甲',reply_to:'missing'}],[{id:'a',text:'甲'},{id:'a',text:'乙'},{id:'b',text:'丙',reply_to:'a'}]]){
    const p=parseReviewResponse({content:comments.map(c=>c.text).join('\n\n')+'\n<review-comments>'+JSON.stringify({comments})+'</review-comments>'});
    assert.equal(p.comments.some(c=>c.reply),false);
  }
});

test('quote presence does not verify facts and never fills missing evidence',()=>{
  assert.equal(reviewQuoteStatus('模型写代码','前文：模型写代码。后文：工具渲染。'),'matched');
  assert.equal(reviewQuoteStatus('不存在的引文','全文已有解释'),'unmatched');
  assert.equal(reviewQuoteStatus('','全文'),'unavailable');
  assert.equal(reviewQuoteStatus('引文',''),'unavailable');
});
