import { useId, useState } from 'react';
import MarkdownContent from './MarkdownContent.jsx';
import ReviewEmblem from './ReviewEmblem.jsx';
import { editorialReading } from '../utils/reviewEditorial.js';
import { reportChapters, reportAxisRows, reportTableModel, REPORT_AXES } from '../utils/reviewReport.js';
import { reviewIdentity } from '../utils/reviewIdentity.js';
import './ReviewServiceTheme.css';

function ReportTable({children,node}) {
  const {headers,rows,kind}=reportTableModel(node);
  const table=<div className="report-table"><table>{children}</table></div>;
  if(kind==='table' || !rows.length) return table;
  return <div className={`report-table-visual is-${kind}`}>
    {kind==='stages' ? <div className="report-stage-flow" role="list" aria-label="原文中的阶段对照">{rows.map((row,i)=><section role="listitem" key={i}><h5>{row[0]}</h5><dl>{headers.slice(1).map((h,j)=><div key={j}><dt>{h}</dt><dd>{row[j+1]}</dd></div>)}</dl></section>)}</div> : <div className="report-decisions" role="list" aria-label="各团意见与主编取舍">{rows.map((row,i)=><section role="listitem" key={i}>{headers.map((h,j)=><div key={j}><h5>{h}</h5>{/处理|取舍/.test(h) ? <span className="report-decision-tag">{row[j]}</span> : <p>{row[j]}</p>}</div>)}</section>)}</div>}
    <details className="report-original-table"><summary>查看原表</summary>{table}</details>
  </div>;
}
const reportComponents={table:ReportTable};
export default function ReviewEditorialReport({ content='',report,notes={} }) {
  const prefix=useId();
  const chapters=reportChapters(content);
  const rows=reportAxisRows(report);
  const [choice,setChoice]=useState(null);
  const [chapterChoice,setChapterChoice]=useState(null);
  const group=rows.find(r=>r.persona_id===choice?.group);
  const axis=group?.axes.find(a=>a.id===choice?.axis);
  return <article className="editorial-report" aria-label="主编完整审阅报告">
    {rows.length>0 && <section className="report-analysis" aria-label="内容、开头与商业融合分析"><header><h4>各团怎么看这篇稿</h4><p>点击分数，查看对应的原始维度。</p></header>
      <div className="report-matrix" role="table" aria-label="各团三项分析，满分10分"><div className="report-matrix__row is-heading" role="row"><span role="columnheader">评审视角</span>{REPORT_AXES.map(a=><span key={a.id} role="columnheader">{a.name}</span>)}</div>{rows.map(row=><div className="report-matrix__row" key={row.persona_id} role="row"><span className="report-matrix__name" role="rowheader"><ReviewEmblem persona={{name:row.name}} compact/>{reviewIdentity({name:row.name}).roleId==='custom' ? row.name : reviewIdentity({name:row.name}).label}</span>{row.axes.map(a=><span role="cell" key={a.id}><button className="report-matrix__cell" aria-label={`${row.name}，${a.name}，${a.score===null ? '未评分' : `${a.score.toFixed(1)}分`}`} aria-pressed={choice?.group===row.persona_id && choice?.axis===a.id} onClick={()=>setChoice({group:row.persona_id,axis:a.id})} style={{'--cell-tint':`${a.score===null ? 0 : 12+a.score*2.7}%`}}>{a.score===null ? '—' : a.score.toFixed(1)}</button></span>)}</div>)}</div>
      <p className="report-analysis__note">颜色越深，分数越高。内容列按本团内容维度加权；“—”表示未评分或不适用。</p>
      {axis && <section className="report-analysis__detail" aria-label="选中分析的评分依据"><header><strong>{group.name} · {axis.name}</strong><button onClick={()=>setChoice(null)} aria-label="收起分析依据">×</button></header>{axis.score===null && <p>{axis.reason}</p>}{axis.dimensions.map(d=>{const note=notes[group.persona_id]?.[d.id];return <div key={d.id}><div className="report-analysis__dimension"><span>{d.name}</span><strong>{d.score===null ? '未评分' : `${d.score.toFixed(1)} / 10`}</strong></div>{note?.basis && <blockquote>{note.basis}</blockquote>}{note?.rationale && <p>{note.rationale}</p>}{note?.deduction && <p className="report-analysis__gap">{note.deduction}</p>}</div>;})}</section>}
    </section>}
    <div className="editorial-report__reading"><nav aria-label="主编报告章节"><strong>阅读导航</strong>{chapters.map(c=><a href={`#${prefix}-${c.id}`} key={c.id} onClick={()=>setChapterChoice(c.id)} aria-current={(chapterChoice || chapters[0]?.id)===c.id ? 'location' : undefined}>{c.title}</a>)}</nav><div>{chapters.map(c=><section className="report-chapter" id={`${prefix}-${c.id}`} key={c.id}><h3>{c.title}</h3><MarkdownContent components={reportComponents}>{editorialReading(c.body)}</MarkdownContent></section>)}</div></div>
  </article>;
}
