import ReviewWeightCells from './ReviewWeightCells.jsx';
import ReviewEmblem from './ReviewEmblem.jsx';
import { reviewIdentity } from '../utils/reviewIdentity.js';

export default function ReviewScoreSummary({ report }) {
  if (!report) return null;
  return <section className="review-score-summary score-breakdown" aria-label="审稿团加权评分">
    <header className="score-breakdown__header"><div><h4>各团加权明细</h4><p>亮格越多，对总分的影响越大。</p></div><strong>{report.complete ? report.score.toFixed(1) : '—'}<small> / 10</small></strong></header>
    <div className="score-breakdown__mix" role="img" aria-label="各团对总分的权重分布">{report.groups.map(row=><span key={row.group_id} style={{flex:row.weight,background:reviewIdentity({name:row.name}).accent}} title={`${row.name}：${row.weight}%`}/>)}</div>
    <div className="score-breakdown__groups">{report.groups.map(row=>{const identity=reviewIdentity({name:row.name});return <details key={row.group_id} className="score-breakdown__group">
      <summary><ReviewEmblem persona={{name:row.name}} compact/><span className="score-breakdown__name"><strong>{row.name}</strong><ReviewWeightCells weight={row.weight} label={`${row.name}权重`} color={identity.accent}/></span><span className="score-breakdown__value">{row.score===null ? '暂缺' : row.score.toFixed(1)}<small>{row.score!==null ? ' / 10' : ''}</small></span><i aria-hidden="true">⌄</i></summary>
      <div className="score-breakdown__dimensions">{row.score===null && <p className="score-breakdown__notice">{row.reason}</p>}{row.dimensions.map(d=><div className="score-breakdown__dimension" key={d.id}><span>{d.name}</span><strong>{d.score===null ? '未评分' : d.score.toFixed(1)}{d.score!==null && <small> / 10</small>}</strong>{d.score!==null ? <meter min="0" max="10" value={d.score} aria-label={`${row.name}：${d.name}`} style={{'--dimension-color':identity.accent}}/> : <p>{d.reason}</p>}</div>)}{!row.dimensions.length && <p>这份记录没有可展示的维度分。</p>}</div>
    </details>;})}</div>
    {!report.complete && <p className="score-breakdown__notice">{report.reason}</p>}
    <p className="score-breakdown__footnote">按保存的规则计算，最后保留一位小数。这里展示模型对稿面的评分。</p>
  </section>;
}
