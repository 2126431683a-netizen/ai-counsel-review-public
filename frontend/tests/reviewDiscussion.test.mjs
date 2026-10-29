import test from 'node:test';
import assert from 'node:assert/strict';
import { discussionBubble, discussionBubbles } from '../src/utils/reviewDiscussion.js';
test('waiting bubbles are role-specific status, never invented review conclusions',()=>{
  const tech={id:'t',name:'技术评审团'},value={id:'v',name:'实用评审团'};
  assert.notEqual(discussionBubble(tech).text,discussionBubble(value).text);
  assert.equal(discussionBubble(tech).type,'status');
  assert.equal(discussionBubble(tech).label,'状态示意');
  assert.notEqual(discussionBubble(tech,[],0).text,discussionBubble(tech,[],1).text);
});
test('bubble trail retains two distinct messages and never invents missing returned comments',()=>{
  const p={id:'a',name:'技术团'};
  assert.equal(discussionBubbles(p,[],0).length,2);
  const only=[{key:'one',persona:{id:'a'},text:'只有这一条实际评论'}];
  assert.equal(discussionBubbles(p,only,0,'returned').length,1);
  assert.equal(discussionBubbles(p,only,0,'failed').length,1);
  assert.equal(discussionBubbles(p,only,0,'preparing').length,1);
  const comments=[...only,{key:'two',persona:{id:'a'},text:'第二条实际评论'},{key:'other',persona:{id:'b'},text:'其他团'}];
  assert.deepEqual(discussionBubbles(p,comments,0,'returned').map(b=>b.commentKey),['two','one']);
  assert.ok(discussionBubbles(p,[],0,'returned').every(b=>b.type==='status'));
});
test('returned bubbles cycle actual comments from that group only',()=>{
  const p={id:'a',name:'技术团'};
  const comments=[{key:'a1',persona:{id:'a'},text:'第一条'},{key:'b1',persona:{id:'b'},text:'别团'},{key:'a2',persona:{id:'a'},text:'第二条'}];
  assert.deepEqual(discussionBubble(p,comments,1,'returned'),{type:'comment',label:'已返回评论',text:'第二条',commentKey:'a2'});
  assert.equal(discussionBubble(p,comments,0,'reading').type,'status');
  assert.equal(discussionBubble(p,[],0,'returned').type,'status');
  assert.equal(discussionBubble(p,comments,0,'failed').type,'status');
});
