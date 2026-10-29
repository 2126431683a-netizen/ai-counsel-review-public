import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {consumeScore,buildScoreReport,groupConfig} from '../src/utils/reviewScoring.js';
import {parseReviewResponse} from '../src/utils/reviewPresentation.js';
import {reviewAvailability,reviewFailureMessage} from '../src/utils/reviewAvailability.js';
import {reviewProgress,reviewFeedback} from '../src/utils/reviewProgress.js';

const bundle=JSON.parse(fs.readFileSync(new URL('../../desktop/role_bundle.json',import.meta.url),'utf8'));
const people=Object.entries(bundle.personas).filter(([id])=>id!=='source-editor').map(([id,p])=>({id,...p}));
const question='先确认内容，再生成工程。改完回到预览检查。';
const response=(p,basis='先确认内容')=>{
  const cfg=groupConfig(p.system_prompt);
  const notes=Object.fromEntries(cfg.dimensions.map(d=>[d.id,{basis,rationale:'先有内容检查点再继续',deduction:'仅保留针对本例的有限判断'}]));
  if(cfg.rubric_version===2)for(const d of cfg.dimensions)notes[d.id].checks=d.checks.map(c=>({id:c.id,score:4,basis,rationale:'有明确的内容检查点',gap:'具体核对内容仍需补充'}));
  return {persona_id:p.id,content:'先把内容定下来。\n<review-comments>'+JSON.stringify({comments:[{text:'先把内容定下来。',basis}],dimension_notes:notes})+'</review-comments>\n<review-score>'+JSON.stringify({scores:Object.fromEntries(cfg.dimensions.map(d=>[d.id,8]))})+'</review-score>'};
};

test('finished missing roles never look as if still waiting; live calls and explicit failures differ',()=>{
  assert.equal(reviewAvailability(undefined).state,'missing');
  assert.match(reviewAvailability(undefined).reason,/旧记录未保留失败原因/);
  assert.equal(reviewAvailability(undefined,{running:true}).state,'waiting');
  assert.equal(reviewAvailability({error:'接口超时'}).state,'failed');
  assert.equal(reviewAvailability({content:'备忘'},{count:0}).label,'已返回，暂无可展示短评');
});

test('transport failures explain that grading did not complete',()=>{
  assert.match(reviewFailureMessage('The provider closed the connection unexpectedly'),/模型接口提前断开连接/);
  assert.match(reviewAvailability({error:'The provider closed the connection unexpectedly'}).reason,/不是稿件评分结果/);
  assert.match(reviewFailureMessage('API error: 401'),/密钥与访问权限/);
});

test('a numeric rating without matching dimension evidence stays out of total',()=>{
  const responses=people.map(p=>response(p));
  assert.equal(buildScoreReport(people,responses,question).score,8);
  responses[0]=response(people[0],'不存在的引文');
  const report=buildScoreReport(people,responses,question);
  assert.equal(report.score,null);
  assert.equal(report.groups[0].score,null);
  assert.match(report.groups[0].reason,/引文未匹配/);
  const parsed=consumeScore(responses[0].content,groupConfig(people[0].system_prompt),null,question).rating;
  assert.equal(parsed.proposed_score,8);
  assert.equal(parsed.dimensions[0].score,8);
});

test('saved totals cannot override dimension math or bypass evidence checks',()=>{
  const r=response(people[0]);const cfg=groupConfig(people[0].system_prompt);
  const valid=consumeScore(r.content,cfg,null,question).rating;
  const saved={...valid,score:999,raw_score:999};
  assert.equal(consumeScore(r.content,cfg,saved,question).rating.score,8);
  assert.equal(consumeScore('旧记录没有评分依据',cfg,saved,question).rating.status,'unverified');
});

test('one malformed comment association does not suppress the other genuine comments',()=>{
  const content='实际可见评论\n<review-comments>'+JSON.stringify({comments:[{text:'实际可见评论',basis:'实际原文'},{text:'机器块另造的评论'}]})+'</review-comments>';
  const parsed=parseReviewResponse({content});
  assert.equal(parsed.structured,true);
  assert.deepEqual(parsed.comments.map(c=>c.text),['实际可见评论']);
  assert.equal(parsed.skippedComments,1);
});

test('a chair result with only part of the panel never triggers the all-results celebration',()=>{
  const running={...reviewProgress({personas:people,isRunning:true}),running:true};
  const partial={...reviewProgress({personas:people,rounds:[{round_number:1,responses:[response(people[0])]}],phase:'complete',verdict:{content:'主编意见'}}),running:false};
  assert.equal(reviewFeedback(running,partial,people).kind,'partial');
  assert.match(reviewFeedback(running,partial,people).text,/1\/5/);
});
