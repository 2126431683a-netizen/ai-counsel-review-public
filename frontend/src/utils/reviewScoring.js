// Uses saved persona snapshots; model output supplies dimensions, never weights.
const GROUPS = new Set(['source-tech', 'source-practical', 'source-surfer', 'source-thinker', 'source-beginner']);
const finite = (n, min, max) => typeof n === 'number' && Number.isFinite(n) && n >= min && n <= max;
const shown = (n) => Math.round((n + Number.EPSILON * 100) * 10) / 10;

export function normalizeReviewBlocks(content = '') {
  let value=content;
  for (const tag of ['review-comments','review-score']) {
    const opening=`<${tag}>`,closing=`</${tag}>`;
    if (value.split(opening).length!==2 || value.includes(closing)) continue;
    let start=value.indexOf(opening)+opening.length;
    while (/\s/.test(value[start] || '') && start<value.length) start++;
    if (value[start]!=='{') continue;
    let depth=0,quoted=false,escaped=false,end=-1;
    for (let i=start;i<value.length;i++) {
      const char=value[i];
      if (quoted) {if(escaped)escaped=false;else if(char==='\\')escaped=true;else if(char==='"')quoted=false;continue;}
      if(char==='"'){quoted=true;continue;}
      if(char==='{' || char==='[')depth++;
      if(char==='}' || char===']'){depth--;if(depth===0){end=i+1;break;}}
    }
    if(end<0)continue;
    try {const object=JSON.parse(value.slice(start,end));if(!object || Array.isArray(object))continue;} catch {continue;}
    const tail=value.slice(end).trimStart();
    if (!tail || tag==='review-comments' && tail.startsWith('<review-score>') || tag==='review-score' && tail.startsWith('CONSENSUS_SCORE:')) value=value.slice(0,end)+closing+value.slice(end);
  }
  return value;
}

export function groupConfig(prompt = '') {
  const matches = [...prompt.matchAll(/<review-group-config>\s*([\s\S]*?)\s*<\/review-group-config>/g)];
  if (matches.length !== 1) return null;
  try {
    const c = JSON.parse(matches[0][1]);
    if (!GROUPS.has(c.id) || typeof c.name !== 'string' || !finite(c.weight, 1, 100)) return null;
    if (!Array.isArray(c.dimensions) || c.dimensions.length < 1 || c.dimensions.length > 8) return null;
    if (!c.dimensions.every(d => typeof d.id === 'string' && typeof d.name === 'string' && finite(d.weight, 1, 100))) return null;
    if (new Set(c.dimensions.map(d => d.id)).size !== c.dimensions.length) return null;
    if (Math.abs(c.dimensions.reduce((a, d) => a + d.weight, 0) - 100) > 1e-9) return null;
    if ('scoring_policy' in c && (c.scoring_policy !== 'opening-commercial-v1' || c.rubric_version !== 2 || c.dimensions.length !== 5 || c.dimensions.find(d=>d.id==='opening')?.weight !== 15 || c.dimensions.find(d=>d.id==='commercial')?.weight !== 25)) return null;
    if ('rubric_version' in c && (c.rubric_version !== 2 || !c.dimensions.every(d=>Array.isArray(d.checks) && d.checks.length===2 && d.checks.every(x=>x && typeof x.id==='string' && x.id && typeof x.name==='string') && new Set(d.checks.map(x=>x.id)).size===2))) return null;
    return c;
  } catch { return null; }
}

export function auditScoreEvidence(content, cfg, manuscript, dimensions=cfg.dimensions) {
  const normalize = value => value.replace(/[\s“”"‘’'*`_]/g, '');
  try {
    const blocks = [...content.matchAll(/<review-comments>\s*([\s\S]*?)\s*<\/review-comments>/g)];
    if (blocks.length !== 1) throw Error('missing notes');
    const notes = JSON.parse(blocks[0][1])?.dimension_notes || {};
    const text = normalize(manuscript);
    return dimensions.flatMap(d => {
      const n = notes[d.id];
      if (!n || !['basis','rationale'].every(k=>typeof n[k]==='string' && n[k].trim())) return [`${d.name}缺少独立原文与理由`];
      const issues=[];
      if (!normalize(n.basis) || !text.includes(normalize(n.basis))) issues.push(`${d.name}的原文引文未匹配`);
      if (n.context && (typeof n.context!=='string' || !text.includes(normalize(n.context)))) issues.push(`${d.name}的相关解释未匹配`);
      if (d.score<10 && !(typeof n.deduction==='string' && n.deduction.trim())) issues.push(`${d.name}缺少扣分或主观保留说明`);
      if (cfg.rubric_version===2) {
        const expected=new Set(d.checks.map(c=>c.id));
        if (!Array.isArray(n.checks) || n.checks.length!==2 || !n.checks.every(c=>c && typeof c.id==='string' && expected.has(c.id)) || new Set(n.checks.map(c=>c.id)).size!==2) issues.push(`${d.name}缺少两项画像评分明细`);
        else {
          let total=0;
          for (const check of n.checks) {
            if (!finite(check.score,0,5) || !Number.isInteger(check.score*2)) {issues.push(`${d.name}子项分应为0至5的半分步进`);continue;}
            total+=check.score;
            if (!['basis','rationale'].every(k=>typeof check[k]==='string' && check[k].trim())) issues.push(`${d.name}子项缺少原文与档位理由`);
            else if (!normalize(check.basis) || !text.includes(normalize(check.basis))) issues.push(`${d.name}子项引文未匹配`);
            if (check.score<5 && !(typeof check.gap==='string' && check.gap.trim())) issues.push(`${d.name}子项缺少距更高档位的具体差距`);
          }
          if (d.score!=null && Math.abs(total-d.score)>1e-9) issues.push(`${d.name}维度分与两项明细之和不一致`);
        }
      }
      return issues;
    });
  } catch { return ['未保存可核对的逐维评分依据']; }
}

export function scoreFromLedger(content, cfg, manuscript) {
  if (cfg.rubric_version!==2 || typeof manuscript!=='string' || !manuscript.trim()) return null;
  try {
    const blocks=[...content.matchAll(/<review-comments>\s*([\s\S]*?)\s*<\/review-comments>/g)];
    if (blocks.length!==1) return null;
    const notes=JSON.parse(blocks[0][1]).dimension_notes;
    if (!notes || Array.isArray(notes) || Object.keys(notes).sort().join('|')!==cfg.dimensions.map(d=>d.id).sort().join('|')) return null;
    const scores={},unrated_reasons={},dimensions=[];
    for (const d of cfg.dimensions) {
      const note=notes[d.id], checks=note?.checks;
      if (d.id==='commercial' && cfg.scoring_policy==='opening-commercial-v1' && Array.isArray(checks) && checks.length===0) {
        const reason=note.deduction;
        if (typeof reason!=='string' || !/^不适用(?:[：:，,。；;\s]|$)/u.test(reason.trim())) return null;
        if (auditScoreEvidence(content,{...cfg,rubric_version:1},manuscript,[d]).length) return null;
        scores[d.id]=null;unrated_reasons[d.id]=reason.trim();continue;
      }
      const expected=new Set(d.checks.map(c=>c.id));
      if (!Array.isArray(checks) || checks.length!==2 || !checks.every(c=>c && typeof c.id==='string' && expected.has(c.id) && finite(c.score,0,5) && Number.isInteger(c.score*2)) || new Set(checks.map(c=>c.id)).size!==2) return null;
      scores[d.id]=checks.reduce((sum,c)=>sum+c.score,0);
      dimensions.push({...d,score:scores[d.id]});
    }
    if (auditScoreEvidence(content,cfg,manuscript,dimensions).length) return null;
    return {scores,unrated_reasons};
  } catch { return null; }
}

export function consumeScore(content = '', cfg, savedRating = null, manuscript) {
  if (!cfg) return { content, rating: null };
  if (cfg.rubric_version===2) content=normalizeReviewBlocks(content);
  const matches = [...content.matchAll(/<review-score>\s*([\s\S]*?)\s*<\/review-score>/g)];
  let clean = content.replace(/<review-score>[\s\S]*?<\/review-score>/g, '').split('<review-score>')[0].trim();
  let rating = { group_id: cfg.id, status: 'invalid', score: null, coverage: 0, dimensions: [], reason: '评分数据缺失或格式无效' };
  let recovered=false;
  try {
    let payload;
    if (savedRating?.dimensions?.length && savedRating.group_id === cfg.id) {
      if (savedRating.dimensions.length !== cfg.dimensions.length || new Set(savedRating.dimensions.map(d=>d.id)).size!==cfg.dimensions.length) throw Error('saved dimensions');
      payload = { scores: Object.fromEntries(savedRating.dimensions.map(d => [d.id, d.score])),
        unrated_reasons: Object.fromEntries(savedRating.dimensions.filter(d => d.score === null).map(d => [d.id, d.reason])) };
    } else {
      const recoverable=matches.length<=1 && content.split('<review-score>').length-1===matches.length && !savedRating?.ledger_recovery_blocked && (!savedRating || savedRating.status==='invalid');
      if (matches.length===1) {
        try {payload=JSON.parse(matches[0][1]);} catch { /* Only a full ledger can replace invalid JSON. */ }
      }
      // Parseable summaries must be checked as supplied; never silently replace
      // contradictory numbers, empty objects, or explicit null values.
      if (payload===undefined && recoverable) {
        payload=scoreFromLedger(content,cfg,manuscript);
        recovered=Boolean(payload);
      }
      if (matches.length>1 || !payload) throw Error('评分汇总缺失或格式错误，且没有可完整校验的评分明细');
    }
    const values = payload.scores;
    const reasons = payload.unrated_reasons || {};
    if (!values || Array.isArray(values) || Object.keys(values).sort().join('|') !== cfg.dimensions.map(d => d.id).sort().join('|')) throw Error('评分维度与本团设定不一致');
    let numerator = 0, coverage = 0;
    const dimensions = cfg.dimensions.map(d => {
      const value = values[d.id];
      let reason = null;
      if (value === null) {
        if (cfg.scoring_policy === 'opening-commercial-v1' && d.id !== 'commercial') throw Error('内容与开头维度不可留空');
        reason = reasons[d.id];
        if (typeof reason !== 'string' || !reason.trim()) throw Error('不适用维度缺少原因');
      } else {
        if (!finite(value, 0, 10)) throw Error('维度评分必须是0至10的有效数字');
        numerator += value * d.weight;
        coverage += d.weight;
      }
      return { ...d, score: value, reason };
    });
    rating = { ...rating, dimensions, coverage };
    if (recovered || savedRating?.calculation_source==='validated_check_ledger') rating.calculation_source='validated_check_ledger';
    if (coverage < 60) rating = { ...rating, status: 'unrated', reason: '可判断维度权重不足60%，本团暂不评分' };
    else rating = { ...rating, status: 'ok', score: shown(numerator / coverage), raw_score: numerator / coverage, reason: null };
  } catch (error) { rating.reason=savedRating?.ledger_recovery_blocked && savedRating.reason ? savedRating.reason : error.message || '评分汇总字段不完整或类型错误'; }
  if (rating.status === 'ok' && typeof manuscript === 'string' && manuscript.trim()) {
    const issues = auditScoreEvidence(content, cfg, manuscript, rating.dimensions.filter(d=>d.score!==null));
    rating = {...rating, evidence_status:issues.length ? 'insufficient' : 'located', evidence_issues:issues};
    if (issues.length) rating = {...rating,status:'unverified',proposed_score:rating.score,score:null,reason:`评分依据待核对：${issues.join('；')}`};
  } else if (rating.status === 'ok' && savedRating?.evidence_status === 'insufficient') {
    rating = {...rating,status:'unverified',proposed_score:rating.score,score:null,
      evidence_status:'insufficient',evidence_issues:savedRating.evidence_issues,reason:savedRating.reason};
  }
  if (recovered && rating.status==='ok') {
    // Historical records retain the old unavailable footer on disk. Correct the
    // derived display only, leaving comments, editor conclusions and files intact.
    clean=clean.replace(/\n*本团稿面评分：\*\*暂缺\*\*[^\n]*/g,'').trim();
    clean+=`\n\n本团稿面评分：**${rating.score.toFixed(1)}/10**（按校验通过的子项明细计算；未重新评价稿件）。`;
  }
  // A newer server already removed the payload and appended a team footer.
  if (!savedRating && !recovered) {
    if (rating.status === 'ok') {
      const detail = rating.dimensions.map(d => `${d.name} ${d.score === null ? '待定' : d.score}`).join('；');
      clean += `\n\n本团稿面评分：**${rating.score.toFixed(1)}/10**（${detail}；可判断维度${rating.coverage}%）。`;
    } else clean += `\n\n本团稿面评分：**暂缺**（${rating.reason}）。`;
  }
  return { content: clean, rating };
}

export function reviewRatingLabel(rating, hasContent=false) {
  if (rating?.status==='ok' && rating.calculation_source==='validated_check_ledger') return '已按评分明细计算';
  if (rating?.status==='ok' && rating.evidence_status==='located') return '评分引文可定位';
  if (rating?.status==='unverified') return '评分依据待核对';
  if (rating?.status==='invalid') return '评分格式或明细有缺漏';
  if (rating?.status==='unrated') return '可评分维度不足';
  return hasContent ? '模型主观评分' : '未计入总分';
}

export function buildScoreReport(personas = [], responses = [], manuscript) {
  const configs = personas.map(p => [p.id, groupConfig(p.system_prompt)]).filter(([, c]) => c);
  if (!configs.length) return null;
  const validPanel = configs.length === 5 && personas.length === 5 && new Set(configs.map(([, c]) => c.id)).size === 5 && Math.abs(configs.reduce((s, [, c]) => s + c.weight, 0) - 100) < 1e-9;
  let total = 0, available = 0;
  const rows = configs.map(([pid, c]) => {
    const response = responses.find(r => r.persona_id === pid && !r.error);
    const rating = response ? consumeScore(response.content || '', c, response.review_rating, manuscript).rating : null;
    const valid = rating?.status === 'ok';
    const contribution = valid ? Number(rating.raw_score) * c.weight / 100 : null;
    if (valid) { total += contribution; available += c.weight; }
    return { persona_id: pid, group_id: c.id, name: c.name, weight: c.weight, score: valid ? rating.score : null,
      contribution: valid ? shown(contribution) : null, dimensions: rating?.dimensions || [], coverage: rating?.coverage || 0,
      evidence_status:rating?.evidence_status || 'legacy',
      reason: valid ? null : responses.find(r=>r.persona_id===pid)?.error || rating?.reason || '本轮未取得有效评分' };
  });
  const complete = validPanel && Math.abs(available - 100) < 1e-9;
  return { version: 1, complete, score: complete ? shown(total) : null, available_weight: available,
    configured_weight: configs.reduce((s, [, c]) => s + c.weight, 0), groups: rows,
    reason: complete ? null : !validPanel ? '需要五个不同审稿团，且权重合计100%' : '部分团评分暂缺，不将缺分当0，也不提高其他团权重' };
}

export function scoreMarkdown(report) {
  if (!report) return '';
  const lines = ['### 审稿团加权评分', '', '|审稿团|权重|稿面分 /10|加权贡献|', '|---|---:|---:|---:|'];
  for (const r of report.groups) lines.push(`|${r.name}|${r.weight}%|${r.score === null ? '暂缺' : r.score.toFixed(1)}|${r.contribution === null ? '—' : r.contribution.toFixed(1)}|`);
  lines.push('', report.complete ? `**加权总分：${report.score.toFixed(1)}/10**` : `**总分暂缺**：${report.reason}`, '',
    '程序按未四舍五入的团内加权分计算，最后保留一位小数；显示的各项贡献相加可能有0.1差异。权重是编辑偏好，不是粉丝人数。高分不能抵消已核实的严重错误。');
  for (const r of report.groups) {
    const pending = r.dimensions.filter(d => d.score === null).map(d => `${d.name}：${d.reason}`);
    if (pending.length) lines.push('', `${r.name}待判断：${pending.join('；')}`);
  }
  return lines.join('\n');
}

export function combineVerdict(content = '', report) {
  if (!report) return content;
  // The authoritative program table replaces any copied/model-authored table.
  const body = content.split(/(?:^|\n)#{1,6}\s*审稿团加权评分/)[0].trim();
  return body + '\n\n' + scoreMarkdown(report);
}
