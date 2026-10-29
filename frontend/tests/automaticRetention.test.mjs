import test from 'node:test';
import assert from 'node:assert/strict';
import { automaticRetention, forecastEvidence, retentionNodeEvidence, spokenParagraphs } from '../src/utils/automaticRetention.js';

const paragraphs=[
  '今天用一个实际例子讲清楚这个工具能解决什么问题，先看最后做成的效果，再回头解释每一步为什么这样选择。这个过程保留限制和失败的地方，方便判断自己是否值得动手。',
  '接着把刚才的结果拆成两步来做，因为上一步已经准备好了素材，所以这里可以直接接着处理，不需要重新注册账号。后面还会演示关闭软件再打开时记录是否保留。',
  '本期由示例工具支持，点击购买链接可以看到对应套餐，不过先看实际操作和限制，不准备购买也能使用免费功能。这一段说明具体成本和适用条件，再回到刚才的案例。',
  '最后回到最初的问题，刚才已经展示了实际成果，重新打开时记录仍然保留。如果只需要这个功能，免费方案就够了，这里不把一次案例推广成所有任务都能完成。'
];
const manuscript=paragraphs.join('\n\n');
function fixture({opening=7,cohesion=7,commercial=7,content=7,na=false}={}) {
  const ids=['value','clarity','opening','commercial'],names=['内容价值','段落衔接与论证','开头15–20秒','商业融合'],weights=[20,40,15,25];
  const scores=[content,cohesion,opening,na ? null : commercial],basis=[paragraphs[3],paragraphs[1],paragraphs[0],paragraphs[2]];
  return {report:{complete:true,score:6.7,groups:[{persona_id:'a',group_id:'a',name:'测试评审团',score:7,weight:100,dimensions:ids.map((id,i)=>({id,name:names[i],score:scores[i],weight:weights[i],reason:na && id==='commercial' ? '无商业推广，不适用' : ''}))}]},notes:{a:Object.fromEntries(ids.map((id,i)=>[id,{basis:basis[i],rationale:`全文复核后的${names[i]}评价`,context:paragraphs[3],deduction:'这是一项测试保留意见，不能单靠局部截句断言问题。'}]))}};
}
const predict=options=>{const {report,notes}=fixture(options);return automaticRetention(manuscript,report,notes);};

test('automatic forecast uses real text, valid dimension evidence and bounded monotonic survival',()=>{
  const f=predict();assert.equal(f.status,'ready');assert.equal(f.paragraphs.length,4);assert.equal(f.rows.length,4);
  assert.equal(f.points[0].value,100);assert.ok(f.points.some(p=>p.time===15));assert.ok(f.points.some(p=>p.time===20));
  assert.ok(f.duration>20);assert.equal(f.completion.time,f.duration);
  assert.ok(f.points.every((p,i)=>p.low>=0 && p.low<=p.value && p.value<=p.high && p.high<=100 && (!i || p.value<=f.points[i-1].value)));
  assert.ok(f.paragraphs[2].ad);assert.equal(f.paragraphs[0].ad,false);
});
test('opening, cohesion and commercial quality affect appropriate portions, never total-score scaling',()=>{
  const good=predict({opening:9,cohesion:9,commercial:10}),weakOpen=predict({opening:3,cohesion:9,commercial:10});
  assert.ok(weakOpen.points.find(p=>p.time===20).value<good.points.find(p=>p.time===20).value);
  const weakLogic=predict({opening:9,cohesion:3,commercial:10});
  assert.equal(weakLogic.points.find(p=>p.time===20).value,good.points.find(p=>p.time===20).value);
  assert.ok(weakLogic.completion.value<good.completion.value);
  const hardAd=predict({opening:9,cohesion:9,commercial:1});
  assert.equal(hardAd.points.find(p=>p.time===20).value,good.points.find(p=>p.time===20).value);
  assert.ok(hardAd.completion.value<good.completion.value);
  assert.equal(good.paragraphs[2].rates.commercial,0);
  assert.equal(hardAd.paragraphs[1].rates.commercial,0);
  const {report,notes}=fixture();const baseline=automaticRetention(manuscript,report,notes);
  report.score=0;report.groups[0].score=0;
  assert.equal(automaticRetention(manuscript,report,notes).completion.value,baseline.completion.value);
});
test('more repeated reviewers with identical scores do not multiply one issue into extra penalties',()=>{
  const {report,notes}=fixture();const baseline=automaticRetention(manuscript,report,notes);
  const repeated={...report,groups:Array.from({length:5},(_,i)=>({...report.groups[0],persona_id:`p${i}`,group_id:`p${i}`,weight:20}))};
  const repeatedNotes=Object.fromEntries(repeated.groups.map(g=>[g.persona_id,notes.a]));
  assert.ok(Math.abs(automaticRetention(manuscript,repeated,repeatedNotes).completion.value-baseline.completion.value)<1e-10);
});
test('missing or invented evidence cannot produce a probability; explicit noncommercial does not incur ad cost',()=>{
  const {report,notes}=fixture();notes.a.opening.basis='这句话根本没有出现在原稿里';
  assert.equal(automaticRetention(manuscript,report,notes).status,'insufficient');
  assert.equal(automaticRetention('',report,notes).status,'insufficient');
  const n=predict({na:true});assert.equal(n.status,'ready');assert.equal(n.axes.commercial,null);
  assert.ok(n.paragraphs.every(p=>!p.ad && p.rates.commercial===0));
  const f=fixture();f.report.groups[0].dimensions.find(d=>d.id==='commercial').score=null;
  assert.equal(automaticRetention(manuscript,f.report,f.notes).status,'insufficient');
});
test('clicked node keeps actual source, local versus whole-text provenance, and matched later explanation',()=>{
  const f=predict(),point=f.points.find(p=>p.paragraph===1 && p.time>20);
  const local=retentionNodeEvidence(f,point,'cohesion');assert.equal(local.local,true);assert.equal(local.rows[0].quote,paragraphs[1]);assert.equal(local.rows[0].context,paragraphs[3]);
  const global=retentionNodeEvidence(f,f.points.at(-1),'cohesion');assert.equal(global.local,false);assert.equal(global.rows[0].quote,paragraphs[1]);
  const {report,notes}=fixture();notes.a.clarity.context='不在原文里的后文解释';
  assert.equal(forecastEvidence(manuscript,report,notes).find(r=>r.axis==='cohesion').context,'');
});
test('speech timing excludes explicit directions and code while wrapping alone changes neither units nor results',()=>{
  const text='# 标题\n画面：'+'不是口播的画面备注。'.repeat(100)+'\n\n'+paragraphs[0]+'\n\n```js\nconst neverSpeakThis = 123;\n```';
  const parsed=spokenParagraphs(text);assert.equal(parsed.length,1);assert.equal(parsed[0].units,spokenParagraphs(paragraphs[0])[0].units);
  const wrapped=manuscript.replaceAll('，','，\n');
  const {report,notes}=fixture();const before=automaticRetention(manuscript,report,notes),after=automaticRetention(wrapped,report,notes);
  assert.equal(before.duration,after.duration);assert.equal(before.completion.value,after.completion.value);
  assert.equal(after.paragraphs.length,4);
  assert.equal(spokenParagraphs('源宝【气喘吁吁】：'+paragraphs[0]+'【配合相应的画面展示】')[0].units,spokenParagraphs(paragraphs[0])[0].units);
});

test('a warning against purchase links is not treated as a local advertising call',()=>{
  const text=manuscript+'\n\n不要点击购买链接，不用下单，先学会分辨这些营销话术。';
  const {report,notes}=fixture();const f=automaticRetention(text,report,notes);
  assert.equal(f.status,'ready');assert.equal(f.paragraphs.at(-1).ad,false);
});
