import { editorialPlain } from './reviewEditorial.js';

// Split only actual level 1/2 headings outside code; keep every source body.
export function reportChapters(content = '') {
  const chapters=[];
  let current={title:'结论与整体判断',lines:[],heading:false},fence=null;
  for(const line of content.replace(/\r\n/g,'\n').split('\n')) {
    const marker=line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if(marker) { if(!fence) fence=marker[1];else if(marker[1][0]===fence[0] && marker[1].length>=fence.length && /^\s{0,3}(?:`+|~+)\s*$/.test(line)) fence=null;current.lines.push(line);continue; }
    const heading=!fence && line.match(/^\s{0,3}#{1,2}\s+(.+?)\s*#*\s*$/);
    if(heading) {
      if(current.heading || current.lines.join('\n').trim()) chapters.push({...current,body:current.lines.join('\n').trim()});
      current={title:editorialPlain(heading[1]),lines:[],heading:true};
    } else current.lines.push(line);
  }
  if(current.lines.join('\n').trim() || current.heading) chapters.push({...current,body:current.lines.join('\n').trim()});
  return chapters.map(({title,body},i)=>({title,body,id:`chapter-${i}`}));
}

export const REPORT_AXES=[{id:'content',name:'内容解释'},{id:'opening',name:'开头吸引力'},{id:'commercial',name:'商业融合'}];
export function reportAxisRows(report) {
  return (report?.groups || []).map(group=>({...group,axes:REPORT_AXES.map(axis=>{
    const dimensions=(group.dimensions || []).filter(d=>axis.id==='content' ? !['opening','commercial'].includes(d.id) : d.id===axis.id);
    const valid=group.score!==null && Number.isFinite(group.score) && dimensions.length>0 && dimensions.every(d=>Number.isFinite(d.score) && d.score>=0 && d.score<=10 && Number.isFinite(d.weight) && d.weight>0);
    const weight=dimensions.reduce((sum,d)=>sum+d.weight,0);
    return {...axis,dimensions,score:valid && weight>0 ? Math.round(dimensions.reduce((sum,d)=>sum+d.score*d.weight,0)/weight*10)/10 : null,reason:dimensions.find(d=>d.score===null)?.reason || (group.score===null ? group.reason : dimensions.length ? '评分不完整' : '这份记录未保存此项')};
  })}));
}

export function reportTableModel(node) {
  const text=n=>n?.type==='text' ? n.value : n?.tagName==='br' ? '\n' : (n?.children || []).map(text).join('');
  const rows=[];
  const visit=n=>{if(n?.tagName==='tr') rows.push((n.children || []).filter(c=>['th','td'].includes(c.tagName)).map(c=>text(c).trim()));else for(const child of n?.children || []) visit(child);};
  visit(node);
  const [headers=[],...body]=rows;
  const kind=headers.length>=2 && /阶段|时间/.test(headers[0]) ? 'stages' : headers.some(h=>/意见/.test(h)) && headers.some(h=>/^处理$|取舍/.test(h)) ? 'decisions' : 'table';
  return {headers,rows:body,kind};
}
