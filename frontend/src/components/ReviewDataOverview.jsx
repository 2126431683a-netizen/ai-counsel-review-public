import { useState } from 'react';
import ReviewEmblem from './ReviewEmblem.jsx';
import { reviewIdentity } from '../utils/reviewIdentity.js';
import { reviewSeries, reviewPlot } from '../utils/reviewData.js';
import './ReviewDataOverview.css';

export default function ReviewDataOverview({ report, roundReports = [] }) {
  const [roundChoice,setRoundChoice]=useState(null);
  const series=reviewSeries(roundReports,report);
  const selectedIndex=roundChoice===null ? series.length-1 : Math.min(roundChoice,series.length-1);
  const selected=series[selectedIndex];
  const {points,segments}=reviewPlot(series);
  if(!selected) return null;
  const valid=selected.report?.groups.filter(g=>g.score!==null).length || 0;
  return <section className="review-data" aria-label="审稿评分数据概览">
    <div className="review-data__trend">
      <header><div><h4>{series.length>1 ? '各轮评分变化' : '本轮评分'}</h4><p>{series.length>1 ? '同一份稿件的多轮审阅' : '依据本轮已返回评分'}</p></div><span>第 {selected.round} 轮{selectedIndex===series.length-1 ? ' · 最终轮' : ''}</span></header>
      <div className="review-data__metric"><strong>{selected.score===null ? '—' : selected.score.toFixed(1)}</strong><span>/ 10<small>{selected.score===null ? selected.compatible ? '总分暂缺' : selected.report ? '计分结构不同，不作连线' : '尚无评分记录' : '五团加权稿面分'}</small></span><span className="review-data__coverage">{valid}/{selected.report?.groups.length || 0} 团评分可用</span></div>
      <svg viewBox="0 0 380 162" role="group" aria-label="各轮总分，纵轴0至10；选择圆点查看该轮">
        {[0,5,10].map(value=><g key={value}><line x1="32" x2="348" y1={132-value*10} y2={132-value*10} className="review-data__grid"/><text x="12" y={136-value*10}>{value}</text></g>)}
        {segments.filter(s=>s.length>1).map((s,i)=><polyline key={i} points={s.map(p=>`${p.x},${p.y}`).join(' ')} className="review-data__line"/>)}
        {points.map((p,i)=><g key={`${p.round}-${i}`}><text x={p.x} y="155" textAnchor="middle">第{p.round}轮</text><g role="button" tabIndex={0} aria-label={`查看第${p.round}轮，总分${p.score===null ? '暂缺' : p.score.toFixed(1)}`} aria-pressed={selectedIndex===i} onClick={()=>setRoundChoice(i)} onKeyDown={e=>{if(e.key==='Enter' || e.key===' '){e.preventDefault();setRoundChoice(i);}}} className={selectedIndex===i ? 'is-selected' : ''}>{p.y===null ? <><rect x={p.x-23} y="72" width="46" height="25" className="review-data__hit"/><text x={p.x} y="88" textAnchor="middle">暂缺</text></> : <><circle cx={p.x} cy={p.y} r="15" className="review-data__hit"/><circle cx={p.x} cy={p.y} r={selectedIndex===i ? 6 : 4} className="review-data__dot"/><text x={p.x} y={p.y-14} textAnchor="middle" className="review-data__value">{p.score.toFixed(1)}</text></>}</g></g>)}
      </svg>
      {series.length>1 && <div className="review-data__round-picker" aria-label="选择查看轮次">{series.map((p,i)=><button key={`${p.round}-${i}`} aria-pressed={selectedIndex===i} onClick={()=>setRoundChoice(i)}>第{p.round}轮<span>{p.score===null ? '暂缺' : p.score.toFixed(1)}</span></button>)}</div>}
      <footer>{points.every(p=>p.score===null) ? '还没有可绘制的有效总分，已有团分见右侧。' : series.length>1 ? '点击圆点查看该轮；分差不等于稿件质量提升。' : '单轮记录，不生成变化趋势。'}</footer>
    </div>
    <figure className="review-data__groups" aria-label={`第${selected.round}轮各团评分对比，满分10分`}>
      <figcaption><div><h4>各团评分对比</h4><span>第 {selected.round} 轮</span></div>{selectedIndex!==series.length-1 && <button onClick={()=>setRoundChoice(null)}>回到最终轮</button>}</figcaption>
      <div className="review-data__scale" aria-hidden="true"><span>0</span><span>5</span><span>10</span></div>
      <div className="review-data__group-list">{selected.report?.groups.map(row=>{const identity=reviewIdentity({name:row.name});return <div className="review-data__group" key={row.persona_id || row.group_id}>
        <ReviewEmblem persona={{name:row.name}} compact/><span title={row.name}>{identity.roleId==='custom' ? row.name : identity.label}</span><div className="review-data__track" role={row.score===null ? undefined : 'meter'} aria-label={`${row.name}稿面评分`} aria-valuemin={row.score===null ? undefined : 0} aria-valuemax={row.score===null ? undefined : 10} aria-valuenow={row.score ?? undefined}><i style={{width:`${row.score===null ? 0 : row.score*10}%`,background:identity.accent}}/></div><strong>{row.score===null ? '暂缺' : row.score.toFixed(1)}</strong>
      </div>;})}</div>
      <p>不同画像保留各自判断，缺分不计为零。</p>
    </figure>
  </section>;
}
