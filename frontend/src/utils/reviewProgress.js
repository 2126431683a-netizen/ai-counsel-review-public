// Progress is driven by returned responses, not a timer or an invented percentage.
export function reviewProgress({ personas = [], rounds = [], currentRound = 1, maxRounds = 3, isRunning = false, phase, error, aborted = false, verdict }) {
  const round = rounds.find(r => (r.round_number || r.round) === currentRound) || rounds[currentRound - 1];
  const responses = round?.responses || [];
  const ids = new Set(personas.map(p => p.id));
  const settled = new Map(responses.filter(r => ids.has(r.persona_id)).map(r => [r.persona_id, r]));
  const returned = [...settled.values()].filter(r => r.content && !r.error).map(r => r.persona_id);
  const failed = [...settled.values()].filter(r => r.error).map(r => r.persona_id);
  const stopped = Boolean(error || aborted || phase === 'error');
  const completed = !isRunning && !stopped && phase === 'complete' && Boolean(verdict?.content && !verdict.error);
  const chair = isRunning && ['verdict','tiebreaker'].includes(phase);
  let message = `第 ${currentRound} / ${maxRounds} 轮 · ${returned.length} / ${personas.length} 团已返回`;
  if (phase === 'initializing' && isRunning) message = '正在准备稿件与评审团';
  if (chair) message = phase === 'tiebreaker' ? '正在复核分歧，保留各团的判断' : '主编正在核对各团意见，整理修改顺序';
  if (stopped) message = aborted ? '评审已停止，已返回的意见仍可查看' : '评审遇到问题，请查看错误说明';
  if (failed.length && !chair && !stopped) message += ` · ${failed.length} 团未完成`;
  const stage = stopped ? 'stopped' : completed ? 'complete' : chair ? 'chair' : isRunning ? phase === 'initializing' ? 'preparing' : 'reviewing' : 'idle';
  return { returned, failed, total: personas.length, round: currentRound, chair, completed, incomplete:completed && returned.length<personas.length, stopped, stage, message };
}

export function reviewFeedback(previous, current, personas = []) {
  if (current.stopped) return null;
  if (previous && !previous.running && current.running && current.stage === 'preparing') return {kind:'started',text:'稿件已送达，评审团准备就位。'};
  if (!previous?.running) return null;
  if (!current.running) return current.completed ? current.incomplete ? {kind:'partial',text:`已保存 ${current.returned.length}/${current.total} 团意见和主编汇总，未返回的团没有计分。`} : { kind:'complete', text:'本次审阅完成，主编结论与各团意见已就位。' } : null;
  const fresh = current.returned.filter(id => previous.round !== current.round || !previous.returned.includes(id));
  if (fresh.length) {
    const names = fresh.map(id => personas.find(p => p.id === id)?.name || '评审团');
    return { kind:'returned', text:`${names.join('、')}的意见已返回，可以先看评论。` };
  }
  if (current.chair && !previous.chair) return { kind:'chair', text:'进入汇总环节，主编正在核对意见。' };
  return null;
}
