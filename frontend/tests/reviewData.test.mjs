import test from 'node:test';
import assert from 'node:assert/strict';
import {reviewSeries,reviewPlot} from '../src/utils/reviewData.js';
const report=(score,complete=true)=>({score,complete,groups:[{group_id:'a',weight:100,score:complete ? score : null,dimensions:complete ? [{id:'accuracy',weight:100,score}] : []}]});
test('round totals remain exact and use a fixed 0–10 axis including zero',()=>{
  const series=reviewSeries([{round:1,report:report(0)},{round:2,report:report(6.7)},{round:3,report:report(10)}]);
  assert.deepEqual(series.map(p=>p.score),[0,6.7,10]);
  assert.deepEqual(reviewPlot(series).points.map(p=>p.y),[132,65,32]);
});
test('missing scores create a real gap, never zero or a connecting segment',()=>{
  const series=reviewSeries([{round:1,report:report(7)},{round:2,report:report(null,false)},{round:3,report:report(6.7)}]);
  assert.equal(series[1].compatible,true);
  assert.deepEqual(series.map(p=>p.score),[7,null,6.7]);
  assert.deepEqual(reviewPlot(series).segments.map(s=>s.length),[1,1]);
});
test('different configured weights or dimensions are not a continuous trend',()=>{
  for(const mutate of [r=>r.groups[0].weight=99,r=>r.groups[0].dimensions[0].id='other']) {
    const old=report(8);mutate(old);
    const series=reviewSeries([{round:1,report:old},{round:2,report:report(6)}]);
    assert.equal(series[0].score,null);assert.equal(series[0].compatible,false);
  }
});
test('single-round and empty histories do not invent another point',()=>{
  assert.deepEqual(reviewSeries(),[]);
  const p=reviewPlot(reviewSeries([],report(6.7)));
  assert.equal(p.points.length,1);assert.equal(p.points[0].x,190);
  assert.deepEqual(p.segments.map(s=>s.length),[1]);
});
