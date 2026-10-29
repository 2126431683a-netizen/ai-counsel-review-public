import test from 'node:test';
import assert from 'node:assert/strict';
import {consumeScore,normalizeReviewBlocks} from '../src/utils/reviewScoring.js';
import {parseReviewResponse} from '../src/utils/reviewPresentation.js';
const question='先展示两条原话，再对照分组结果。';
const cfg={id:'source-tech',name:'技术团',weight:25,rubric_version:2,dimensions:[{id:'accuracy',name:'技术表述',weight:100,checks:[{id:'a',name:'对象'},{id:'b',name:'关系'}]}]};
const notes=()=>({comments:[{text:'想对照两条原话。',basis:'先展示两条原话'}],dimension_notes:{accuracy:{basis:'先展示两条原话',rationale:'有对照安排',deduction:'还需具体结果',checks:['a','b'].map(id=>({id,score:3,basis:'先展示两条原话',rationale:'基本可用',gap:'对照较泛'}))}}});
const text=(p,score=6)=>'想对照两条原话。\n<review-comments>'+JSON.stringify(p)+'</review-comments><review-score>'+JSON.stringify({scores:{accuracy:score}})+'</review-score>';
test('anchor score sums and quoted checkpoints survive the production detail parser',()=>{
  const parsed=parseReviewResponse({content:text(notes())},{system_prompt:'<review-group-config>'+JSON.stringify(cfg)+'</review-group-config>'},question);
  assert.equal(parsed.rating.score,6);
  assert.equal(parsed.dimensionNotes.accuracy.checks[0].name,'对象');
  assert.equal(parsed.dimensionNotes.accuracy.checks[0].score,3);
});
test('high scores without checks and mismatched sums stay unverified, never silently lowered',()=>{
  const mismatch=consumeScore(text(notes(),10),cfg,null,question).rating;
  assert.equal(mismatch.status,'unverified');assert.equal(mismatch.score,null);assert.equal(mismatch.proposed_score,10);
  const p=notes();delete p.dimension_notes.accuracy.checks;
  assert.equal(consumeScore(text(p),cfg,null,question).rating.status,'unverified');
});
test('invented checkpoint evidence and unexplained gaps are rejected',()=>{
  const p=notes();p.dimension_notes.accuracy.checks[0].basis='没有这句话';p.dimension_notes.accuracy.checks[1].gap='';
  assert.equal(consumeScore(text(p),cfg,null,question).rating.status,'unverified');
});
test('only unambiguous complete JSON can receive a missing closing delimiter',()=>{
  const raw=text(notes()).replace('</review-comments>','').replace('</review-score>','')+'\nCONSENSUS_SCORE: 4';
  assert.equal(consumeScore(raw,cfg,null,question).rating.score,6);
  const partial='<review-score>{"scores":{"accuracy":6';
  assert.equal(normalizeReviewBlocks(partial),partial);
  assert.equal(consumeScore(partial,cfg,null,question).rating.score,null);
  const ambiguous='<review-score>{"scores":{"accuracy":6}} unexpected text';
  assert.equal(normalizeReviewBlocks(ambiguous),ambiguous);
});
