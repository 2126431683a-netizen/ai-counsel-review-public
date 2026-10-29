import { useState } from 'react';
import ReviewEditorialReport from './ReviewEditorialReport.jsx';
import ReviewEmblem from './ReviewEmblem.jsx';
import ReviewScoreSummary from './ReviewScoreSummary.jsx';
import { copyToClipboard } from '../utils/clipboard.js';
import { editorialDashboard } from '../utils/reviewEditorial.js';
import ReviewDataOverview from './ReviewDataOverview.jsx';
import ReviewRetention from './ReviewRetention.jsx';
import { finalPaperScore } from '../utils/reviewRetention.js';
import './ReviewEditorialDashboard.css';

export default function ReviewEditorial({ id, content = '', copyText = '', verdict, report, roundReports = [], notes = {}, manuscript = '', isRunning, phase, aborted, error, teamTarget }) {
  const [copied, setCopied] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const { title, summary, points } = editorialDashboard(content);
  const ready = Boolean(title && !verdict?.error);
  const summarizing = isRunning && phase === 'verdict';
  const stopped = aborted || error || phase === 'error';
  const paperScore=finalPaperScore(report);
  if (!ready && !summarizing && !verdict?.error) return <section id={id} className="review-editor-pending" aria-label="主编结论状态">
    <strong>主编结论</strong><span>{stopped ? '评审已停止，主编尚未给出结论。' : isRunning ? '各团先读稿，主编在最后核对并汇总。' : '这份记录没有主编结论，可继续查看各团意见。'}</span>
  </section>;
  return <section id={id} className={`review-editor-top editorial-dashboard ${summarizing && !ready ? 'is-summarizing' : ''}`} aria-label="主编审阅意见">
    <header className="review-editor-top__heading">
      <ReviewEmblem persona={{name:verdict?.persona_name || '主编',avatar_emoji:'review:editor'}} compact/>
      <div className="editorial-dashboard__identity"><h3>{ready ? '主编结论' : verdict?.error ? '主编汇总未完成' : '主编正在汇总'}</h3>{!ready && <p>{verdict?.error ? '各团已返回的意见仍可在下方查看。' : '回到原稿核对意见，整理结论与修改重点。'}</p>}{ready && <button className="review-editor-top__copy" onClick={async()=>{if(await copyToClipboard(copyText)){setCopied(true);setTimeout(()=>setCopied(false),1800);}}}>{copied ? '已复制' : '复制意见'}</button>}</div>
      {report && <div className={`editorial-paper-score ${paperScore===null ? 'is-missing' : ''}`} aria-label={paperScore===null ? '综合稿面分待评分' : `综合稿面分${paperScore.toFixed(1)}，满分10分`}><span>综合稿面分</span><div><strong>{paperScore===null ? '待评分' : paperScore.toFixed(1)}</strong>{paperScore!==null && <small>/ 10</small>}</div><svg viewBox="0 0 160 15" aria-hidden="true"><path d="M3 7Q70 1 154 5 M12 13Q83 7 157 11"/></svg></div>}
    </header>
    {verdict?.error ? <p className="review-board__error">{typeof verdict.error === 'string' ? verdict.error : '主编意见未能返回，请查看模型连接后重试。'}</p> : ready ? <>
      <div className="editorial-dashboard__overview">
        <div className="editorial-dashboard__judgment"><h4>{title.replace(/^主编(?:结论|意见)[：:]\s*/, '')}</h4>{summary && <p>{summary}</p>}<a href={`#${teamTarget}`}>查看各团评论</a></div>
      </div>
      {report && <ReviewDataOverview report={report} roundReports={roundReports}/>}
      <ReviewRetention manuscript={manuscript} report={report} notes={notes}/>
      {points.length>0 && <section className="editorial-dashboard__points" aria-label="主编关注点"><header><h4>主编关注点 <span>{points.length}</span></h4><span>摘自主编原文，点开看说明</span></header><div>{(showAll ? points : points.slice(0,3)).map((point,i)=><details key={`${i}-${point.title}`}><summary>{point.title}</summary><p>{point.body}</p></details>)}</div>{points.length>3 && <button className="editorial-dashboard__more" onClick={()=>setShowAll(v=>!v)} aria-expanded={showAll}>{showAll ? '收起其余关注点' : `再看 ${points.length-3} 项`}</button>}</section>}
      <div className="editorial-resources">
        <details className="review-editor-top__details editorial-dashboard__full"><summary><span className="editorial-resources__icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 3h10l4 4v14H5Z M14 3v5h5 M8 12h8 M8 16h6"/></svg></span><span><strong>主编完整意见</strong><small>可视化分析、判断依据与修改方向</small></span><i aria-hidden="true">＋</i></summary><ReviewEditorialReport content={content} report={report} notes={notes}/></details>
        {report && <details className="review-editor-top__details editorial-dashboard__scoring"><summary><span className="editorial-resources__icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 20h16 M6 16V9h3v7Z M11 16V4h3v12Z M16 16v-5h3v5Z"/></svg></span><span><strong>各团评分与侧重</strong><small>格子看权重，展开看维度</small></span><i aria-hidden="true">＋</i></summary><ReviewScoreSummary report={report}/></details>}
      </div>
    </> : <div className="review-editor-top__waiting" role="status"><span aria-hidden="true">• • •</span><p>汇总完成后，结论会显示在这里。</p></div>}
  </section>;
}
