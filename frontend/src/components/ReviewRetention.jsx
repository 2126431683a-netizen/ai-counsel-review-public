import { useMemo, useState } from 'react';
import { automaticRetention, retentionNodeEvidence, RETENTION_AXES } from '../utils/automaticRetention.js';
import { retentionTime } from '../utils/reviewRetention.js';
import './ReviewRetention.css';
import './ReviewRetentionAuto.css';

function RetentionCurve({forecast,selected,onSelect,compact=false}) {
  const end=compact ? 302 : 708,start=compact ? 44 : 48,bottom=compact ? 170 : 202,height=compact ? 130 : 160;
  const x=t=>start+(end-start)*t/forecast.duration,y=v=>bottom-v*height/100;
  const points=forecast.points;
  return <svg className={compact ? 'retention-plot--compact' : 'retention-plot--wide'} viewBox={compact ? '0 0 324 210' : '0 0 752 248'} role="group" aria-label="自动稿面留存预估曲线，点击节点查看判断依据">
    {(compact ? [0,50,100] : [0,25,50,75,100]).map(v=><g key={v}><line x1={start} x2={end} y1={y(v)} y2={y(v)} className="retention-grid"/><text x={start-11} y={y(v)+4} textAnchor="end">{v}%</text></g>)}
    <polygon points={[...points.map(p=>`${x(p.time)},${y(p.high)}`),...points.toReversed().map(p=>`${x(p.time)},${y(p.low)}`)].join(' ')} className="retention-band"/>
    <polyline points={points.map(p=>`${x(p.time)},${y(p.value)}`).join(' ')} className="retention-line"/>
    {points.map((p,i)=>{
      const left=i ? (x(points[i-1].time)+x(p.time))/2 : start-7,right=i===points.length-1 ? end+7 : (x(points[i+1].time)+x(p.time))/2;
      const active=p.id===selected.id;
      return <g key={p.id} role="button" tabIndex={0} aria-label={`约${retentionTime(p.time)}，${p.time===0 ? '起点' : `第${p.paragraph+1}段`}${p.ad ? '，商业相关段' : ''}，预估${Math.round(p.value)}%，查看依据`} aria-pressed={active} onClick={()=>onSelect(p)} onKeyDown={e=>{if(e.key==='Enter' || e.key===' '){e.preventDefault();onSelect(p);}}} className={`retention-node ${active ? 'is-selected' : ''} ${p.ad ? 'is-commercial' : ''}`}>
        <rect x={left} y="34" width={right-left} height={bottom-24} className="retention-node__hit"/>
        {active && <line x1={x(p.time)} x2={x(p.time)} y1="38" y2={bottom} className="retention-selected-line"/>}
        <circle cx={x(p.time)} cy={y(p.value)} r={active ? 6 : p.time===15 || p.time===20 || p.ad || i===points.length-1 ? 4 : 2.5} className="retention-dot"/>
      </g>;
    })}
    <text x={start} y="24">开头 → 段落衔接 → 结尾</text>
    {(compact ? [0,.5,1] : [0,.25,.5,.75,1]).map(f=><text key={f} x={x(forecast.duration*f)} y={bottom+24} textAnchor="middle">{retentionTime(forecast.duration*f)}</text>)}
  </svg>;
}

function ForecastEvidence({forecast,selected,axis,manuscript}) {
  const p=forecast.paragraphs[selected.paragraph],evidence=retentionNodeEvidence(forecast,selected,axis);
  return <div className="retention-node-detail__body">
    <p className="retention-node-detail__explanation">{axis==='opening' ? '开头评价决定前20秒的留存基线，后续节点不会重复扣一次开头。' : axis==='commercial' ? forecast.commercialNA ? '各团标明商业不适用，本稿不叠加商业流失。' : p.ad ? '此段定位到了商业评价原文或明确推广线索；融合评价越高，额外流失影响越小。' : '此段没有定位到商业原文或明确推广线索，不额外叠加商业流失。' : evidence.local ? '此段有可定位的衔接或解释评价，结合各团全文评价调整本段推算速度。' : '此段没有直接对应的衔接引文，沿用全文评价作参考，不据此认定本段有逻辑断裂。'}</p>
    <div className="retention-node-detail__reading"><section><h5>节点对应原稿 · 第{p.index+1}段</h5>{p.heading && <small>{p.heading}</small>}<blockquote>{manuscript.slice(p.start,p.end)}</blockquote><details><summary>连同前后段一起看</summary>{forecast.paragraphs.slice(Math.max(0,p.index-1),p.index+2).map(row=><div key={row.id}><h6>第{row.index+1}段{row.index===p.index ? '（当前）' : ''}</h6><p>{manuscript.slice(row.start,row.end)}</p></div>)}</details></section>
      <section><h5>{evidence.local ? '直接对应本段的评审依据' : '各团全文评价参考'} <small>{new Set(evidence.rows.map(row=>row.groupId)).size}团可定位</small></h5>{evidence.rows.length ? evidence.rows.map((row,index)=><details className="retention-opinion" key={row.id} open={index===0}><summary><span>{row.group} · {row.dimension}</span><strong>{row.score.toFixed(1)} / 10</strong></summary><blockquote>{row.quote}</blockquote><p>{row.rationale}</p>{row.context && <div className="retention-opinion__context"><strong>全文中的相关解释</strong><p>{row.context}</p></div>}{row.judgment && <p>{row.judgment}</p>}</details>) : <p>此项没有可定位的评价，不补造评审意见。</p>}<small>只使用本视角可定位的各团依据；引文匹配仅确认出处，判断仍需结合全文核对。</small></section></div>
  </div>;
}

export default function ReviewRetention({manuscript='',report,notes={}}) {
  const forecast=useMemo(()=>automaticRetention(manuscript,report,notes),[manuscript,report,notes]);
  const [choice,setChoice]=useState(null),[axisChoice,setAxisChoice]=useState(null);
  const selected=forecast.points.find(p=>p.id===choice) || forecast.points.find(p=>p.time===20) || forecast.points.at(-1);
  const select=p=>{setChoice(p.id);setAxisChoice(null);};
  if(forecast.status!=='ready') return <section className="review-retention" aria-label="自动完播预估状态"><header><h4>完播率预估</h4><span className="review-retention__status">依据不足</span></header><p className="review-retention__note">{forecast.reason}</p></section>;
  const axis=axisChoice || selected.kind,p=forecast.paragraphs[selected.paragraph],end=forecast.completion;
  const scoreFor=id=>id==='opening' ? forecast.axes.opening : id==='commercial' ? p.commercialScore : p.cohesionScore;
  return <section className="review-retention is-automatic" aria-label="自动稿面完播预估">
    <header><div><h4>完播率预估 <span>自动分析</span></h4><p>结合全文、开头表现、段落衔接和商业融合。</p></div><span className="review-retention__status">{forecast.usedGroups}/{forecast.totalGroups} 团依据 · 未校准</span></header>
    <div className="review-retention__summary"><div><span>稿面预估完播</span><strong>约{Math.round(end.value)}%</strong></div><p>敏感性范围 {Math.round(end.low)}–{Math.round(end.high)}%<br/>口播约 {retentionTime(forecast.duration)}，按可识别正文粗估。</p></div>
    <figure className="review-retention__plot"><RetentionCurve forecast={forecast} selected={selected} onSelect={select}/><RetentionCurve forecast={forecast} selected={selected} onSelect={select} compact/><figcaption><span className="retention-legend"><i/>留存推算 <i className="is-band"/>敏感性范围 <i className="is-ad"/>商业相关节点</span>点击曲线任一段，查看原文与判断依据。</figcaption></figure>
    <div className="retention-node-picker"><div>{forecast.points.filter(point=>point.time===15 || point.time===20).map(point=><button type="button" key={point.id} aria-pressed={point.id===selected.id} onClick={()=>select(point)}>前{point.time}秒 <strong>{Math.round(point.value)}%</strong></button>)}</div><label>查看节点<select aria-label="选择预估节点" value={selected.id} onChange={e=>select(forecast.points.find(point=>point.id===e.target.value))}>{forecast.points.map(point=><option value={point.id} key={point.id}>约{retentionTime(point.time)} · {point.time===0 ? '起点' : `第${point.paragraph+1}段`}{point.ad ? ' · 商业相关' : ''}</option>)}</select></label></div>
    <section className="retention-node-detail" aria-label="曲线节点判断依据"><header><div><h5>约{retentionTime(selected.time)} · {selected.time===0 ? '起点' : selected.time<=20 ? '开头留人' : p.ad ? '商业相关段' : '段落衔接'}</h5><p>{selected.time===0 ? '以进入视频的观众为100%起点' : `此时仍在观看约${Math.round(selected.value)}%，范围${Math.round(selected.low)}–${Math.round(selected.high)}%`}</p></div><span>原稿第{p.index+1}/{forecast.paragraphs.length}段</span></header>
      <div className="retention-factor-tabs" role="group" aria-label="选择判断视角">{RETENTION_AXES.map(a=><button type="button" key={a.id} aria-pressed={axis===a.id} onClick={()=>setAxisChoice(a.id)}>{a.name}<span>{scoreFor(a.id)===null ? a.id==='commercial' && forecast.commercialNA ? '不适用' : '未叠加' : `${scoreFor(a.id).toFixed(1)} / 10`}</span></button>)}</div>
      <ForecastEvidence forecast={forecast} selected={selected} axis={axis} manuscript={manuscript}/>
    </section>
    <details className="review-retention__method"><summary>这条曲线如何得出</summary><p>先识别正文与段落，排除明确标题、镜头备注和代码块，按每秒4.5个中文字/英文词粗估时间。每个节点绑定原稿范围；前20秒使用各团开头评价，后续按内容兑现、段落衔接与商业融合分段计算持续观看比例。综合稿面总分不参与换算。</p><p>同一团的相关维度按原维度权重汇总，再按各团侧重加权；重复意见不按条数叠加。衔接与内容融合局部引文和全文评价；商业只在对应引文段或明确推广线索段增加阻力，单独出现品牌/模型名称不算广告。</p><p>这是未校准的启发式模型：20秒留存基准为44%＋开头维度分×4.8%；后续每分钟流失强度为 内容[0.02＋0.09×(1−内容分/10)]＋衔接[0.005＋0.04×(1−衔接分/10)]＋商业[有商业段时0.25×(1−融合分/10)，否则0]。持续比例按指数衰减。局部衔接占35%、局部内容占25%，其余为全文参考。上述系数是可审计的设计假设，不是平台统计。</p><p>浅蓝带同时改变规则强度±20%和语速3.8–5.2字词/秒，属于敏感性范围，不是统计置信区间。广告评价不适用时不额外增加商业阻力；无有效依据不生成数字。模型版本：{forecast.version}。</p></details>
    <p className="review-retention__note">稿面预测，非实测留存。时间点为口播粗估，镜头、表演与实际流量可能改变结果；未接入账号数据校准。</p>
  </section>;
}
