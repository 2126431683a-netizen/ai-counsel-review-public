import test from 'node:test';
import assert from 'node:assert/strict';
import { editorialPreview, editorialDashboard, editorialReading } from '../src/utils/reviewEditorial.js';

test('real conclusion and its qualification appear before detailed sections without rewriting',()=>{
  const text='主体成立，**但关键结论仍要核对**。\n\n演示已经安排，交付时确认即可。\n\n## 需要处理\n\n只保留这条具体事项。';
  assert.deepEqual(editorialPreview(text),{lead:'主体成立，**但关键结论仍要核对**。',support:'演示已经安排，交付时确认即可。',rest:'## 需要处理\n\n只保留这条具体事项。'});
});
test('generic leading headings do not replace the actual judgment',()=>{
  const p=editorialPreview('## 总体判断\r\n\r\n这次需要修改后再拍。\r\n\r\n## 原因\r\n\r\n前后约束矛盾。');
  assert.equal(p.lead,'这次需要修改后再拍。');
  assert.equal(p.support,'');
  assert.match(p.rest,/前后约束矛盾/);
});
test('missing verdict cannot become a score-inferred or invented conclusion',()=>{
  for(const input of [null,undefined,'','## 总体判断']) assert.deepEqual(editorialPreview(input),{lead:'',support:'',rest:''});
});
test('a substantive warning heading and its original paragraph remain together',()=>{
  const p=editorialPreview('## 必须先修正时长\n\n总长与分章长度矛盾。\n\n## 其余内容\n\n已经成立。');
  assert.equal(p.lead,'## 必须先修正时长\n\n总长与分章长度矛盾。');
  assert.match(p.rest,/已经成立/);
});

test('dashboard excerpts the actual judgment and first source list, not later votes or headings',()=>{
  const text='### 主编结论：基本可用，但还需补齐验证\n\n这是一份有案例的体验稿。后面的解释仍然保留。\n\n目前不足：\n\n- **能理解过程，却不能开始。**Step Studio入口未交代。\n- **看到效果，尚无验证。**已有演示安排。\n\n所以先处理入口。\n\n## 可选建议\n\n- 不应被混成优先项。';
  const view=editorialDashboard(text);
  assert.equal(view.title,'主编结论：基本可用，但还需补齐验证');
  assert.equal(view.summary,'这是一份有案例的体验稿。');
  assert.deepEqual(view.points,[{title:'能理解过程，却不能开始。',body:'能理解过程，却不能开始。Step Studio入口未交代。'},{title:'看到效果，尚无验证。',body:'看到效果，尚无验证。已有演示安排。'}]);
});
test('no list or missing verdict creates no invented action items',()=>{
  assert.deepEqual(editorialDashboard(''),{title:'',summary:'',points:[]});
  assert.deepEqual(editorialDashboard('成立，但解释不足。\n\n先补明确的操作入口。').points,[]);
  assert.deepEqual(editorialDashboard('结论。\n\n## 代码例子\n\n```md\n- 代码中的列表\n```').points,[]);
});
test('reading mode fixes Chinese bold markers but preserves words and literal code',()=>{
  const text='- **能理解，却不能开始。**Step入口待补。\n\n`**literal**`\n\n```md\n**literal**\n```';
  assert.equal(editorialReading(text),'- 能理解，却不能开始。Step入口待补。\n\n`**literal**`\n\n```md\n**literal**\n```');
});
