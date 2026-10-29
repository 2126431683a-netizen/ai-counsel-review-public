// Versioned, uncalibrated manuscript heuristic; never map the total score to views.
export const RETENTION_MODEL_VERSION='manuscript-review-v1';
export const RETENTION_AXES=[{id:'opening',name:'开头留人'},{id:'cohesion',name:'段落衔接'},{id:'commercial',name:'商业融合'}];
const valid=n=>typeof n==='number' && Number.isFinite(n) && n>=0 && n<=10;
const units=s=>(s.replace(/【[^】]*(?:画面|镜头|展示|配合|表情|喘|抹泪|抹眼|音效|停顿|笑|动作)[^】]*】/g,'').match(/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]|[\p{Script=Latin}\p{N}]+/gu) || []).length;
const normalize=s=>s.replace(/[\s“”"‘’'*`_]/g,'');

function sourceLocator(manuscript) {
  const chars=[],indices=[];
  for(let i=0;i<manuscript.length;i++) if(normalize(manuscript[i])) {chars.push(manuscript[i]);indices.push(i);}
  const source=chars.join('');
  return quote=>{
    if(typeof quote!=='string') return null;
    const query=normalize(quote),at=query.length>=8 ? source.indexOf(query) : -1;
    return at<0 ? null : {start:indices[at],end:indices[at+query.length-1]+1,quote:manuscript.slice(indices[at],indices[at+query.length-1]+1)};
  };
}

export function spokenParagraphs(manuscript='') {
  const paragraphs=[];
  let current=null,fence=false,heading='';
  const flush=()=>{if(current?.units) paragraphs.push({...current,id:`paragraph-${paragraphs.length}`,index:paragraphs.length});current=null;};
  for(const match of manuscript.matchAll(/[^\n]+|\n/g)) {
    const raw=match[0],line=raw.trim();
    if(raw==='\n') continue;
    if(!line) {flush();continue;}
    // A blank line separates paragraphs; merely wrapping a line does not.
    if(match.index>0 && /\n\s*\n$/.test(manuscript.slice(Math.max(0,match.index-20),match.index))) flush();
    if(/^\s*(`{3,}|~{3,})/.test(line)) {flush();fence=!fence;continue;}
    if(fence) continue;
    if(/^(?:#{1,6}\s+|[一二三四五六七八九十]+、|标题(?:\s|[：:]))/.test(line)) {flush();heading=line.replace(/^#+\s*/, '');continue;}
    if(/^(?:画面|镜头|场景|音效|字幕|花字|备注|表情|转场|时长|BGM|bgm|素材|拍摄说明)\s*[：:]/.test(line) || /^开场为/.test(line) || /^[（(](?:画面|镜头|音效|字幕|转场)[\s\S]*[）)]$/.test(line)) {flush();continue;}
    if(/^\s*\|/.test(line) || /^\s*(?:---+|===+)\s*$/.test(line)) {flush();continue;}
    const text=line.replace(/^(?:口播|旁白|台词|源宝|大夫|医生|家属|患者|护士|画外音|A|B|甲|乙)(?:【[^】]*】)?\s*[：:]\s*/,'');
    const start=match.index+raw.indexOf(text);
    for(const sentence of text.matchAll(/[^。！？!?；;]+[。！？!?；;]?/g)) {
      const part=sentence[0],count=units(part);
      if(!count) continue;
      if(current && current.units>=220) flush();
      const at=start+sentence.index;
      if(!current) current={start:at,end:at+part.length,text:part,units:count,heading};
      else {current.end=at+part.length;current.text+=' '+part;current.units+=count;}
    }
  }
  flush();
  let time=0;
  return paragraphs.map(p=>{const duration=p.units/4.5;const result={...p,startTime:time,endTime:time+duration};time+=duration;return result;});
}

export function forecastEvidence(manuscript='',report,notes={}) {
  const locate=sourceLocator(manuscript),rows=[];
  for(const group of report?.groups || []) {
    if(!valid(group.score) || !(group.weight>0)) continue;
    for(const d of group.dimensions || []) {
      const note=notes[group.persona_id]?.[d.id],span=locate(note?.basis);
      if(!valid(d.score) || !span || typeof note?.rationale!=='string' || !note.rationale.trim()) continue;
      const context=locate(note.context);
      const axis=d.id==='opening' ? 'opening' : d.id==='commercial' ? 'commercial' : /逻辑|论据|论证|衔接|推进|节奏|路径|讲明白|清楚|前置|卡点|观看期待/.test(d.name) ? 'cohesion' : 'content';
      rows.push({id:`${group.persona_id}-${d.id}`,groupId:group.group_id || group.persona_id,group:group.name,weight:group.weight,dimensionWeight:d.weight || 1,dimension:d.name,dimensionId:d.id,axis,score:d.score,...span,context:context?.quote || '',rationale:note.rationale.trim(),judgment:typeof note.deduction==='string' ? note.deduction.trim() : '',position:Math.round(span.start/Math.max(1,manuscript.length)*100)});
    }
  }
  return rows.sort((a,b)=>a.start-b.start);
}

function weightedMean(rows) {
  const groups=new Map();
  for(const row of rows) {
    if(!groups.has(row.groupId)) groups.set(row.groupId,{weight:row.weight,scores:new Map()});
    groups.get(row.groupId).scores.set(row.dimensionId,{score:row.score,weight:row.dimensionWeight});
  }
  let sum=0,weight=0;
  for(const group of groups.values()) {const scores=[...group.scores.values()];sum+=group.weight*scores.reduce((a,b)=>a+b.score*b.weight,0)/scores.reduce((a,b)=>a+b.weight,0);weight+=group.weight;}
  return weight ? sum/weight : null;
}
const overlaps=(row,p)=>row.start<p.end && row.end>p.start;
const PROMOTION=/(?:下单|抢购|优惠券|到手价|限时优惠|购买链接|专属福利|立即购买|本期.{0,8}(?:赞助|支持)|赞助商|售价\s*\d|立减\s*\d|点击.{0,6}(?:购买|链接))/;
function promotionSignal(text) {
  // Explicitly negated/warning clauses are not purchasing calls to action.
  return text.split(/[。！？!?，,；;\n]/).some(clause=>PROMOTION.test(clause) && !/(?:不要|别|没有|不存在|不放|无需|不用|不是|并非).{0,12}(?:下单|抢购|优惠券|购买|赞助|点击|链接)/.test(clause));
}

export function automaticRetention(manuscript='',report,notes={}) {
  const paragraphs=spokenParagraphs(manuscript),rows=forecastEvidence(manuscript,report,notes);
  const opening=rows.filter(r=>r.axis==='opening'),cohesion=rows.filter(r=>r.axis==='cohesion'),commercial=rows.filter(r=>r.axis==='commercial');
  const content=rows.filter(r=>!['opening','commercial'].includes(r.axis));
  const duration=paragraphs.at(-1)?.endTime || 0,missing=[];
  if(duration<8) missing.push('足够的可识别口播正文');
  if(!opening.length) missing.push('带原文依据的开头评分');
  if(!cohesion.length) missing.push('带原文依据的衔接或解释评分');
  if(!content.length) missing.push('带原文依据的内容评分');
  const commercialDimensions=(report?.groups || []).flatMap(g=>g.dimensions || []).filter(d=>d.id==='commercial');
  const commercialNA=commercialDimensions.length>0 && commercialDimensions.every(d=>d.score===null && /不适用|无商业|未涉及商业|无推广/.test(d.reason || ''));
  if(!commercial.length && !commercialNA) missing.push('商业融合评分或明确的不适用说明');
  if(missing.length) return {status:'insufficient',reason:`缺少${missing.join('、')}，暂不生成完播百分比。`,points:[],paragraphs,rows};
  const axes={opening:weightedMean(opening),cohesion:weightedMean(cohesion),commercial:weightedMean(commercial),content:weightedMean(content)};
  const prepared=paragraphs.map(p=>{
    const localCohesion=cohesion.filter(r=>overlaps(r,p)),localContent=content.filter(r=>overlaps(r,p)),localCommercial=commercial.filter(r=>overlaps(r,p));
    const promotionCue=commercial.length>0 && promotionSignal(p.text),ad=localCommercial.length>0 || promotionCue;
    const cohesionScore=localCohesion.length ? .65*axes.cohesion+.35*weightedMean(localCohesion) : axes.cohesion;
    const contentScore=localContent.length ? .75*axes.content+.25*weightedMean(localContent) : axes.content;
    const commercialScore=ad ? (localCommercial.length ? weightedMean(localCommercial) : axes.commercial) : null;
    // Design assumptions, NOT fitted population parameters; sensitivity band below.
    const rates={content:.02+.09*(1-contentScore/10),cohesion:.005+.04*(1-cohesionScore/10),commercial:commercialScore===null ? 0 : .25*(1-commercialScore/10)};
    return {...p,ad,promotionCue,localCohesion,localCommercial,rates,contentScore,cohesionScore,commercialScore};
  });
  const times=[...new Set([0,...[15,20].filter(t=>t<duration),...prepared.map(p=>p.endTime)])].sort((a,b)=>a-b);
  const at20=.92-.48*(1-axes.opening/10),factors=[1,.8*4.5/5.2,1.2*4.5/3.8];
  let survived=[100,100,100],previous=0;
  const points=times.map((time,i)=>{
    const paragraph=prepared.find(p=>time<=p.endTime+1e-7) || prepared.at(-1);
    const rates=paragraph.rates,total=rates.content+rates.cohesion+rates.commercial;
    survived=survived.map((v,k)=>{
      const intro=Math.max(0,Math.min(time,20)-Math.min(previous,20)),later=Math.max(0,time-Math.max(previous,20));
      return v*Math.pow(at20,intro/20*factors[k])*Math.exp(-total*later/60*factors[k]);
    });
    previous=time;
    return {id:`point-${i}`,time,value:survived[0],low:survived[2],high:survived[1],paragraph:paragraph.index,kind:time<=20 ? 'opening' : paragraph.ad ? 'commercial' : 'cohesion',ad:paragraph.ad,rates};
  });
  return {version:RETENTION_MODEL_VERSION,status:'ready',duration,paragraphs:prepared,rows,axes,commercialNA,points,completion:points.at(-1),usedGroups:new Set(rows.map(r=>r.groupId)).size,totalGroups:report.groups.length};
}

export function retentionNodeEvidence(forecast,point,axis) {
  const paragraph=forecast.paragraphs[point.paragraph],global=forecast.rows.filter(r=>r.axis===axis),local=global.filter(r=>overlaps(r,paragraph));
  return {rows:local.length ? local : global,local:axis!=='opening' && local.length>0};
}
