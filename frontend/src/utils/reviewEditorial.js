// Excerpt existing text without inventing a verdict from scores or reviewer votes.
export function editorialPreview(content = '') {
  let body = typeof content === 'string' ? content.replace(/\r\n/g, '\n').trim() : '';
  body = body.replace(/^(?:#{1,6}[ \t]+(?:总体判断|主编(?:意见|结论|审阅)|综合(?:判断|结论)|审阅结论|结论)[ \t]*[：:]?(?:\n+|$))+/, '').trim();
  if (!body) return { lead:'', support:'', rest:'' };
  const blocks = body.split(/\n[ \t]*\n/);
  let lead = blocks.shift();
  if (/^#{1,6}\s/.test(lead) && blocks.length) lead += '\n\n' + blocks.shift();
  const support = blocks.length && !/^(?:#{1,6}\s|[-*+]\s|\d+[.)、]\s|\|)/.test(blocks[0]) ? blocks.shift() : '';
  return { lead, support, rest:blocks.join('\n\n') };
}

// Presentation only: retain source wording, with the full original still available.
export function editorialPlain(text = '') {
  return text.replace(/^\s{0,3}#{1,6}\s+/gm, '').replace(/\*\*([^\n]+?)\*\*/g, '$1')
    .replace(/__([^\n]+?)__/g, '$1').replace(/`([^`\n]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^\s)]+\)/g, '$1').trim();
}

export function editorialDashboard(content = '') {
  const { lead, support, rest } = editorialPreview(content);
  if (!lead) return { title:'', summary:'', points:[] };
  const lines = lead.split('\n').filter(s=>s.trim());
  const heading = /^#{1,6}\s/.test(lines[0]);
  const first = editorialPlain(heading ? lines.slice(1).join(' ') : lead);
  const sentence = first.match(/^[\s\S]*?[。！？](?:[”’」』])?/u)?.[0] || first;
  const title = editorialPlain(heading ? lines[0] : sentence);
  const summary = heading ? sentence : editorialPlain(support).match(/^[\s\S]*?[。！？](?:[”’」』])?/u)?.[0] || editorialPlain(support);
  // Only the first contiguous source list, never manufactured priorities.
  const points = [];
  let item = '', inList = false, fenced = false;
  for (const line of rest.split('\n')) {
    if (/^\s*(```|~~~)/.test(line)) { if(inList) break; fenced=!fenced; continue; }
    if (fenced) continue;
    const match = line.match(/^\s{0,3}(?:[-*+]\s+|\d+[.)、]\s+)(.+)/);
    if (match) { if(item) points.push(item); item=match[1]; inList=true; }
    else if (inList && /^\s{2,}\S/.test(line)) item+='\n'+line.trim();
    else if (inList && line.trim()) break;
  }
  if(item) points.push(item);
  return { title, summary:summary===title ? '' : summary, points:points.map(body=>{
    const emphasized = body.match(/^\*\*([\s\S]+?)\*\*/)?.[1];
    const plain = editorialPlain(body);
    return { title:editorialPlain(emphasized || plain.match(/^[\s\S]*?[。！？](?:[”’」』])?/u)?.[0] || plain), body:plain };
  }) };
}

// Chinese punctuation next to closing ** is not always valid CommonMark emphasis.
// Reading mode removes this decoration; preserve code fences and inline code.
export function editorialReading(content = '') {
  return content.split(/(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)/g)
    .map((part,i)=>i%2 ? part : part.replace(/\*\*([^\n]+?)\*\*/g,'$1').replace(/__([^\n]+?)__/g,'$1')).join('');
}
