import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {groupConfig,consumeScore,buildScoreReport,reviewRatingLabel} from '../src/utils/reviewScoring.js';
const bundle=JSON.parse(fs.readFileSync(new URL('../../desktop/role_bundle.json',import.meta.url),'utf8'));
const draft='先展示分镜，再生成工程。最后打开预览检查结果。';
function fixture(pid='source-beginner') {
  const cfg=groupConfig(bundle.personas[pid].system_prompt);
  const dimension_notes=Object.fromEntries(cfg.dimensions.map(d=>[d.id,{basis:'先展示分镜',context:'最后打开预览检查结果',rationale:'有明确控制点',deduction:'尚未给具体入口',checks:d.checks.map(c=>({id:c.id,score:3.5,basis:'先展示分镜',rationale:'顺序能跟上',gap:'需要具体操作示例'}))}]));
  dimension_notes.commercial={...dimension_notes.commercial,deduction:'不适用：没有商业推广依据',checks:[]};
  return {cfg,notes:{comments:[],dimension_notes}};
}
const content=(notes,tail='')=>'这步能跟上。\n<review-comments>'+JSON.stringify(notes)+'</review-comments>\n'+tail;

test('complete checkpoints calculate a missing or malformed summary, keeping commercial N/A',()=>{
  const {cfg,notes}=fixture();
  for(const tail of ['', '<review-score>{bad}</review-score>','<review-score>{"scores":{}}}</review-score>']) {
    const {rating}=consumeScore(content(notes,tail),cfg,null,draft);
    assert.equal(rating.score,7);assert.equal(rating.coverage,75);
    assert.equal(rating.calculation_source,'validated_check_ledger');
    assert.equal(rating.evidence_status,'located');
    assert.equal(reviewRatingLabel(rating,true),'已按评分明细计算');
  }
});

test('old saved invalid record can display its validated ledger without editing the record',()=>{
  const {cfg,notes}=fixture();
  const saved={group_id:cfg.id,status:'invalid',dimensions:[],score:null,reason:'评分数据缺失或格式无效'};
  const original=content(notes)+'\n\n本团稿面评分：**暂缺**（评分数据缺失或格式无效）。';
  const copy=JSON.stringify(saved);
  const result=consumeScore(original,cfg,saved,draft);
  assert.equal(result.rating.score,7);assert.equal(result.content.includes('**暂缺**'),false);
  assert.equal(JSON.stringify(saved),copy);
  assert.equal(consumeScore(original,cfg,{...saved,ledger_recovery_blocked:true},draft).rating.score,null);
});

test('unmatched quotes, missing checkpoints or gaps never create a fallback score',()=>{
  for(const change of ['quote','context','gap','missing_check','duplicate','fraction','bool','missing_dim','extra_dim','na_reason','na_quote']) {
    const {cfg,notes}=fixture();const n=notes.dimension_notes.clarity,c=n.checks[0];
    if(change==='quote')c.basis='没有这句话';
    if(change==='context')n.context='没有这句话';
    if(change==='gap')c.gap='';
    if(change==='missing_check')n.checks.pop();
    if(change==='duplicate')n.checks[1].id=c.id;
    if(change==='fraction')c.score=3.25;
    if(change==='bool')c.score=true;
    if(change==='missing_dim')delete notes.dimension_notes.opening;
    if(change==='extra_dim')notes.dimension_notes.other=n;
    if(change==='na_reason')notes.dimension_notes.commercial.deduction='只是没看到广告';
    if(change==='na_quote')notes.dimension_notes.commercial.basis='没有这句话';
    assert.equal(consumeScore(content(notes),cfg,null,draft).rating.score,null,change);
  }
});

test('truncated, duplicate and semantically invalid summaries are never replaced',()=>{
  const {cfg,notes}=fixture();
  for(const tail of ['<review-score>{','<review-score>{}</review-score>','<review-score>null</review-score>','<review-score>{}</review-score><review-score>{}</review-score>']) {
    assert.equal(consumeScore(content(notes,tail),cfg,null,draft).rating.score,null,tail);
  }
});

test('parseable totals that disagree with checkpoint numbers remain unverified',()=>{
  const {cfg,notes}=fixture();
  const summary={scores:Object.fromEntries(cfg.dimensions.map(d=>[d.id,d.id==='commercial'?null:10])),unrated_reasons:{commercial:'不适用：没有推广'}};
  const rating=consumeScore(content(notes,'<review-score>'+JSON.stringify(summary)+'</review-score>'),cfg,null,draft).rating;
  assert.equal(rating.status,'unverified');assert.equal(rating.proposed_score,10);
  assert.equal(reviewRatingLabel(rating,true),'评分依据待核对');
});

test('all five historical-style ledgers yield the correct fixed-weight total',()=>{
  const personas=[],responses=[];
  for(const pid of Object.keys(bundle.personas).filter(p=>p!=='source-editor')) {
    const {cfg,notes}=fixture(pid);
    personas.push({id:pid,...bundle.personas[pid]});
    responses.push({persona_id:pid,content:content(notes),review_rating:{group_id:cfg.id,status:'invalid',dimensions:[]}});
  }
  const report=buildScoreReport(personas,responses,draft);
  assert.equal(report.complete,true);assert.equal(report.available_weight,100);assert.equal(report.score,7);
  responses[0].content='只有评论没有明细';
  assert.equal(buildScoreReport(personas,responses,draft).score,null);
});

test('without original manuscript or with v1 rules no ledger score is synthesized',()=>{
  const {cfg,notes}=fixture();
  assert.equal(consumeScore(content(notes),cfg).rating.score,null);
  delete cfg.rubric_version;
  assert.equal(consumeScore(content(notes),cfg,null,draft).rating.score,null);
  assert.equal(reviewRatingLabel({status:'invalid'},true),'评分格式或明细有缺漏');
});
