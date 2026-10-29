import test from 'node:test';
import assert from 'node:assert/strict';
import { finalPaperScore, retentionTime } from '../src/utils/reviewRetention.js';

test('red paper score keeps exact final ten-point total including zero, never incomplete totals',()=>{
  assert.equal(finalPaperScore({complete:true,score:6.7}),6.7);
  assert.equal(finalPaperScore({complete:true,score:0}),0);
  for(const report of [null,{complete:false,score:6.7},{complete:true,score:null},{complete:true,score:'6.7'},{complete:true,score:NaN},{complete:true,score:11}]) assert.equal(finalPaperScore(report),null);
});
test('estimated time rolls over minutes without false sixty-second labels',()=>{
  assert.equal(retentionTime(0),'0:00');assert.equal(retentionTime(59.8),'1:00');assert.equal(retentionTime(300),'5:00');
});
