import { reviewIdentity } from './reviewIdentity.js';

const STATUS = {
  tech:['对照术语与前后解释','核对结论和实测范围','回查后文有没有回答','串起工具各自的输入输出','核对前后是不是同一条件','对照前后两段的技术因果'],
  value:['看这套办法解决什么事','对照投入与实际用途','找可复用的具体步骤','把必要条件和操作接起来','区分这次体验与普遍承诺','回看结尾是否兑现开头'],
  fun:['对照开头和结尾的回应','看例子能否接住解释','留意重复和表达节奏','区分故意反转与突然转题','把笑点放回整段语境','看段落转场是否跟得上'],
  think:['分清作者真正的主张','对照论据与结论边界','看人工取舍是否讲明','回查结论需要哪些前提','区分一个例子与普遍结论','对照前后有没有偷换条件'],
  learn:['串起从概念到操作的路','回看前后术语解释','区分待拍演示与漏步骤','核对前置步骤出现的顺序','把“它”和前文对象对上','确认后文是否补上了疑问'],
  custom:['按本团设定通读全文','回查前后解释与限定','整理有依据的评论','核对段落之间的承接','回看开头承诺是否兑现','区分理解断点与表达偏好'],
};

export function discussionBubble(persona, comments = [], tick = 0, state = 'reading') {
  if (state === 'failed') return {type:'status',label:'本团未完成',text:'已返回的其他团意见仍可查看。'};
  if (state === 'preparing') return {type:'status',label:'准备状态',text:'稿件已送达，等待连接就绪。'};
  const usable = comments.filter(c=>c.persona?.id===persona.id && c.text?.trim());
  if (state === 'returned' && usable.length) {const c=usable[((tick%usable.length)+usable.length)%usable.length];return {type:'comment',label:'已返回评论',text:c.text,commentKey:c.key};}
  if (state === 'returned') return {type:'status',label:'意见已返回',text:'可在下方查看本团完整记录。'};
  const choices=STATUS[reviewIdentity(persona).roleId] || STATUS.custom;
  return {type:'status',label:'状态示意',text:choices[((tick%choices.length)+choices.length)%choices.length]};
}

// A small visible trail, never fabricate extra replies when only one exists.
export function discussionBubbles(persona, comments = [], tick = 0, state = 'reading') {
  const current = discussionBubble(persona, comments, tick, state);
  if (state === 'failed' || state === 'preparing') return [current];
  const previous = discussionBubble(persona, comments, tick - 1, state);
  return previous.text === current.text ? [current] : [previous, current];
}
