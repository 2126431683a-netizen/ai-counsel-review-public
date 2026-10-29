import { groupConfig } from './reviewScoring.js';

export const REVIEW_IDENTITIES = [
  { id: 'tech', label: '技术团', iconName: '拿笔核对的技术团', focus: '准确性与实测边界', summary:'核对术语、型号和实测条件，判断结论有没有说过头。', accent: '#275a91', tint: '#d7eafb' },
  { id: 'value', label: '实用团', iconName: '拿计算器的实用团', focus: '成本、门槛与实际价值', summary:'看花多少钱、要折腾多久，以及观众拿回去能做什么。', accent: '#815017', tint: '#ffe6b4' },
  { id: 'fun', label: '表达趣味团', iconName: '戴耳机的趣味团', focus: '表达节奏与趣味', summary:'留意哪里有共鸣、哪里拖沓，梗和例子是不是自然。', accent: '#8a3b61', tint: '#fbdde9' },
  { id: 'think', label: '观点思考团', iconName: '托腮思考的观点团', focus: '观点深度与论证', summary:'检查观点怎么推出来、边界在哪里，有没有新的理解。', accent: '#62448f', tint: '#e8dff9' },
  { id: 'learn', label: '新手团', iconName: '抱笔记本的新手团', focus: '理解门槛与动手路径', summary:'从第一次接触的角度，找没听懂的概念和跟做的断点。', accent: '#316951', tint: '#d9efdf' },
  { id: 'editor', label: '主编', iconName: '拿红笔的主编', focus: '核对依据与整理优先级', summary:'回到原稿核对意见，整理该改什么、先改什么。', accent: '#93443b', tint: '#f8ddd3' },
  { id: 'custom', label: '自定义评审团', iconName: '自定义人物评审团', focus: '按自己的设定审阅', accent: '#535969', tint: '#e5e7ee' },
];
const BY_ID = Object.fromEntries(REVIEW_IDENTITIES.map(item => [item.id, item]));
const GROUP_IDS = { 'source-tech':'tech', 'source-practical':'value', 'source-surfer':'fun', 'source-thinker':'think', 'source-beginner':'learn' };
const OLD_EMOJIS = new Set(['🔧','💰','🏄','💭','🌱','📝','🧑‍💼']);

export function reviewIdentity(persona = {}) {
  const avatar = persona.avatar_emoji || '';
  const cfg = groupConfig(persona.system_prompt);
  let id = GROUP_IDS[cfg?.id];
  const subject = `${persona.name || ''} ${persona.role || ''}`;
  if (!id) {
    if (/主编|汇总|editor|chair/i.test(subject)) id = 'editor';
    else if (/技术|较真|事实|核验|tech|fact/i.test(subject)) id = 'tech';
    else if (/实用|精打细算|成本|预算|practical|value/i.test(subject)) id = 'value';
    else if (/玩梗|趣味|冲浪|幽默|表达|humor/i.test(subject)) id = 'fun';
    else if (/思考|深度|观点|逻辑|think|logic/i.test(subject)) id = 'think';
    else if (/新手|入门|易懂|beginner|learn/i.test(subject)) id = 'learn';
  }
  const role = BY_ID[id || 'custom'];
  const chosen = avatar.startsWith('review:') ? BY_ID[avatar.slice(7)] : null;
  // A visual choice must never relabel the group's actual review responsibility.
  const identity = { ...(chosen || role), roleId:role.id, focus:role.focus, summary:role.summary };
  if (avatar && !avatar.startsWith('review:') && !OLD_EMOJIS.has(avatar)) return { ...identity, emoji: avatar };
  return identity;
}
