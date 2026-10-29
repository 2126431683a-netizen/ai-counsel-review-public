import { groupConfig, consumeScore } from './reviewScoring.js';

const NAMES = {
  '较真技术党': '技术评审团', '精打细算实用党': '实用评审团',
  '玩梗冲浪党': '表达趣味评审团', '深度思考派': '观点思考评审团', '跃跃欲试新手': '新手评审团',
};
const CONFIG_NAMES = { 'source-tech': '技术评审团', 'source-practical': '实用评审团',
  'source-surfer': '表达趣味评审团', 'source-thinker': '观点思考评审团', 'source-beginner': '新手评审团' };
export function reviewGroupName(persona = {}) {
  const cfg = groupConfig(persona.system_prompt);
  return CONFIG_NAMES[cfg?.id] || NAMES[persona.name] || (persona.name?.includes('评审团') ? persona.name : `${persona.name || '未命名'}评审团`);
}

const plain = s => String(s || '').replace(/[*_`]/g, '').replace(/^[ \t]*[-+][ \t]+/gm, '').trim();
const normalize = s => plain(s).replace(/[\s“”"‘’']/g, '');
const tidy = s => String(s || '').replace(/^\s*(?:[-*+]\s+|\d+[.)、]\s*)/, '').trim();

export function parseReviewResponse(response = {}, persona = {}, manuscript) {
  const original = typeof response.content === 'string' ? response.content : '';
  const cfg = groupConfig(persona.system_prompt);
  const scored = consumeScore(original, cfg, response.review_rating, manuscript);
  const blocks = [...scored.content.matchAll(/<review-comments>\s*([\s\S]*?)\s*<\/review-comments>/g)];
  const fullText = scored.content.replace(/<review-comments>[\s\S]*?<\/review-comments>/g, '').split('<review-comments>')[0].trim();
  const memoMatch = /(?:^|\n)[#*\s]*(?:给作者的备忘|审阅备忘|证据备忘|本团备忘|审稿备忘)[*：:\s]*(?:\n|$)/m.exec(fullText);
  const lead = memoMatch ? fullText.slice(0, memoMatch.index).trim() : fullText;
  const memo = memoMatch ? fullText.slice(memoMatch.index + memoMatch[0].length).trim() : '';
  const result = { comments: [], dimensionNotes: {}, memo, fullText, rating: scored.rating,
    legacyScore: null, structured: false };
  const oldScore = /评分[^\n：:]{0,20}[：:]\s*([0-9]+(?:\.[0-9]+)?)\s*分/.exec(plain(original));
  if (oldScore && Number(oldScore[1]) <= 10) result.legacyScore = Number(oldScore[1]);
  if (blocks.length === 1) {
    try {
      const payload = JSON.parse(blocks[0][1]);
      const candidates = Array.isArray(payload) ? payload : payload?.comments;
      const parsed = Array.isArray(candidates) ? candidates.filter(x => x && typeof x.text === 'string' && x.text.trim() && normalize(lead).includes(normalize(x.text))) : null;
      if (Array.isArray(parsed) && candidates.length <= 20 && (parsed.length || candidates.length===0)) {
        result.skippedComments = candidates.length-parsed.length;
        result.comments = parsed.map((item, i) => {
          const parent = typeof item.reply_to === 'string' ? parsed.findIndex((x,j) => j < i && x.id === item.reply_to && parsed.filter(y=>y.id===x.id).length===1) : -1;
          return { id: `c-${i}`, text: item.text.trim(), association: 'comment',
          reply:parent >= 0 ? {id:`c-${parent}`,text:parsed[parent].text.trim()} : null,
          kind: ['确定问题','待核实','素材待补','个人口味','观众反应'].includes(item.kind) ? item.kind : '观众反应',
          detail: Object.fromEntries(['basis','context','rationale','limits','next_step'].filter(k => typeof item[k] === 'string' && item[k].trim()).map(k => [k, item[k].trim()])) };
        });
        const notes = payload?.dimension_notes;
        if (!Array.isArray(payload) && notes && typeof notes === 'object') for (const d of cfg?.dimensions || []) {
          const note = notes[d.id];
          if (note && typeof note === 'object') result.dimensionNotes[d.id] = Object.fromEntries(['basis','context','rationale','deduction'].filter(k=>typeof note[k]==='string' && note[k].trim()).map(k=>[k,note[k].trim()]));
            if (result.dimensionNotes[d.id] && Array.isArray(note.checks) && d.checks) result.dimensionNotes[d.id].checks = note.checks.filter(c=>c && d.checks.some(expected=>expected.id===c.id) && typeof c.score==='number' && Number.isFinite(c.score)).map(c=>({id:c.id,name:d.checks.find(expected=>expected.id===c.id).name,score:c.score,...Object.fromEntries(['basis','rationale','gap'].filter(k=>typeof c[k]==='string').map(k=>[k,c[k]]))}));
        }
        result.structured = true;
        return result;
      }
    } catch { /* Keep the visible original text; never invent a per-comment reason. */ }
  }
  // Legacy reports explicitly associate a reaction with the immediately preceding issue.
  const legacy = /(?:你看到这里的真实反应|真实反应)[*\s]*[：:]\s*/g;
  const matches = [...fullText.matchAll(legacy)];
  if (matches.length) {
    result.comments = matches.map((match, i) => {
      const start = match.index + match[0].length;
      const tail = fullText.slice(start);
      const stop = /\n\s*(?:\n|[-*#]*\s*(?:原句|问题在哪|你会在评论区|共识信号|Consensus Signal|\d+[.、]))/.exec(tail);
      const text = tidy(tail.slice(0, stop ? stop.index : tail.length));
      const before = fullText.slice(i ? matches[i - 1].index + matches[i - 1][0].length : 0, match.index);
      const quoteStarts = [...before.matchAll(/(?:原句|位置)[*\s]*[：:]/g)];
      const detail = before.slice(quoteStarts.length ? quoteStarts[quoteStarts.length - 1].index : 0).trim();
      return { id: `legacy-${i}`, text, kind: '观众反应', association: 'comment', detail: { content: detail } };
    }).filter(x => x.text);
    return result;
  }
  // V4 comments may be bullets, independent paragraphs or separated by horizontal rules.
  const cleanLead = lead.replace(/^.*(?:模拟短评|团内短评|模拟反应)[*#：:\s]*$/gm, '')
    .split(/\n\s*(?:#{1,6}\s*)?(?:共识信号|Consensus Signal|本团稿面评分|评分依据)/)[0];
  const paragraphs = cleanLead.split(/\n\s*\n|\n(?=\s*[-*+]\s+)/).map(tidy)
    .filter(x => x && !/^[-*_=]{3,}$/.test(x) && !/^#{1,6}\s/.test(x))
    .filter(x => !/^(?:本期是|本稿是|评分[（(:：]|你最在意的)/.test(plain(x)));
  result.comments = paragraphs.map((text, i) => ({ id: `p-${i}`, text, kind: '观众反应', association: 'group', detail: {} }));
  return result;
}

// Text presence only: this is not a factual verification or a claim of correctness.
export function reviewQuoteStatus(quote, manuscript) {
  if (!quote?.trim() || !manuscript?.trim()) return 'unavailable';
  const text=normalize(quote);
  if (!text) return 'unavailable';
  return normalize(manuscript).includes(text) ? 'matched' : 'unmatched';
}

export function roundComments(personas, round = {}, roundIndex = 0, manuscript) {
  return (round.responses || []).flatMap(response => {
    if (response.error || !response.content) return [];
    const persona = personas.find(p => p.id === response.persona_id) || { id: response.persona_id, name: response.persona_name };
    const parsed = parseReviewResponse(response, persona, manuscript);
    return parsed.comments.map(comment => ({ ...comment, key: `${roundIndex}:${persona.id}:${comment.id}`, persona, parsed, response }));
  });
}
