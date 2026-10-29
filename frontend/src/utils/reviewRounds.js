export function clampReviewRounds(value,fallback=3){return typeof value==='number' && Number.isFinite(value)?Math.min(10,Math.max(1,Math.trunc(value))):fallback;}
export function reviewRoundPlan(n){
  if(n===1)return '独立审阅 → 主编汇总';
  if(n===2)return '独立审阅 → 交叉复核 → 主编汇总';
  return `独立审阅 → 交叉复核 → ${n===3?'收束复核':`继续复核至第${n}轮`} → 主编汇总`;
}
