import test from 'node:test';
import assert from 'node:assert/strict';
import { weightCellLevels } from '../src/utils/reviewWeightCells.js';

test('five saved weights have exact filled-cell proportions without changing policy',()=>{
  for(const [weight,filled] of [[30,6],[25,5],[20,4],[15,3],[10,2]]){
    const cells=weightCellLevels(weight);
    assert.equal(cells.length,20);
    assert.equal(cells.filter(v=>v===1).length,filled);
    assert.equal(cells.reduce((a,b)=>a+b,0),filled);
  }
});
test('fractional custom proportions retain partial cells, not rounding to a new weight',()=>{
  const cells=weightCellLevels(33.3);
  assert.ok(Math.abs(cells.reduce((a,b)=>a+b,0)/20*100-33.3)<1e-8);
  assert.ok(cells.some(v=>v>0&&v<1));
  assert.equal(weightCellLevels(0).every(v=>v===0),true);
  assert.equal(weightCellLevels(100).every(v=>v===1),true);
});
test('missing or invalid configuration cannot masquerade as a real weight',()=>{
  for(const weight of [null,undefined,'25',NaN,-1,101]) assert.equal(weightCellLevels(weight),null);
});
