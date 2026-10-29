import test from 'node:test';
import assert from 'node:assert/strict';
import { reviewProgress, reviewFeedback } from '../src/utils/reviewProgress.js';

const personas = [{id:'tech',name:'技术团'},{id:'value',name:'实用团'}];
const snapshot = args => ({...reviewProgress({personas,...args}),running:Boolean(args.isRunning)});

test('only selected groups with successful content count as returned; failures stay distinct',()=>{
  const p = snapshot({isRunning:true,rounds:[{round_number:1,responses:[{persona_id:'tech',content:'意见'},{persona_id:'value',error:'连接失败'},{persona_id:'unknown',content:'无关'}]}]});
  assert.deepEqual(p.returned,['tech']);
  assert.deepEqual(p.failed,['value']);
  assert.equal(p.total,2);
  assert.match(p.message,/1 \/ 2 团已返回.*1 团未完成/);
});
test('advancing to a new round never reuses earlier responses as completed work',()=>{
  const p = snapshot({isRunning:true,currentRound:2,rounds:[{round_number:1,responses:[{persona_id:'tech',content:'旧一轮'}]}]});
  assert.deepEqual(p.returned,[]);
  assert.match(p.message,/第 2/);
});
test('history mount is silent; new successful response gives one real group acknowledgement',()=>{
  const initial = snapshot({isRunning:true,rounds:[]});
  const next = snapshot({isRunning:true,rounds:[{round_number:1,responses:[{persona_id:'tech',content:'返回'}]}]});
  assert.equal(reviewFeedback(null,next,personas),null);
  assert.match(reviewFeedback(initial,next,personas).text,/技术团的意见已返回/);
  assert.equal(reviewFeedback(next,next,personas),null);
});
test('complete feedback requires a live-to-success transition and a usable chair verdict',()=>{
  const running = snapshot({isRunning:true});
  const done = snapshot({isRunning:false,phase:'complete',verdict:{content:'主编意见'},rounds:[{round_number:1,responses:personas.map(p=>({persona_id:p.id,content:'已返回'}))}]});
  assert.equal(reviewFeedback(running,done,personas).kind,'complete');
  assert.equal(reviewFeedback(null,done,personas),null);
  for(const extra of [{aborted:true},{error:'失败'},{phase:'error'},{verdict:{content:''}},{verdict:{content:'残留',error:'失败'}}]){
    const failed=snapshot({isRunning:false,phase:'complete',verdict:{content:'主编意见'},...extra});
    assert.equal(reviewFeedback(running,failed,personas),null);
  }
});
test('chair stage has a truthful label and announces only the transition',()=>{
  const running = snapshot({isRunning:true,phase:'round'});
  const chair = snapshot({isRunning:true,phase:'verdict'});
  assert.match(chair.message,/主编正在核对/);
  assert.equal(reviewFeedback(running,chair,personas).kind,'chair');
  assert.equal(reviewFeedback(chair,chair,personas),null);
});

test('stage rail follows preparing, reviewing, chair and a usable completed verdict',()=>{
  assert.equal(snapshot({isRunning:true,phase:'initializing'}).stage,'preparing');
  assert.equal(snapshot({isRunning:true,phase:'round'}).stage,'reviewing');
  assert.equal(snapshot({isRunning:true,phase:'verdict'}).stage,'chair');
  assert.equal(snapshot({phase:'complete',verdict:{content:'真实结论'}}).stage,'complete');
  assert.equal(snapshot({phase:'complete',verdict:{content:''}}).stage,'idle');
  assert.equal(snapshot({isRunning:true,phase:'round',aborted:true}).stage,'stopped');
});

test('submit acknowledgement requires a real transition into preparation, never history mount',()=>{
  const idle=snapshot({isRunning:false});
  const preparing=snapshot({isRunning:true,phase:'initializing'});
  assert.equal(reviewFeedback(idle,preparing,personas).kind,'started');
  assert.equal(reviewFeedback(null,preparing,personas),null);
  assert.equal(reviewFeedback(preparing,preparing,personas),null);
  assert.equal(reviewFeedback(idle,{...preparing,stopped:true},personas),null);
});
