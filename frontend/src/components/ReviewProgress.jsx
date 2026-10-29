import { useEffect, useRef, useState } from 'react';
import { reviewFeedback, reviewProgress } from '../utils/reviewProgress.js';
import ReviewBrainstorm from './ReviewBrainstorm.jsx';
import { roundComments } from '../utils/reviewPresentation.js';

export default function ReviewProgress(props) {
  const progress = reviewProgress(props);
  const [notice, setNotice] = useState(null);
  const last = useRef(null);
  const clearTimer = useRef(null);
  const { personas = [], isRunning, currentRound, phase } = props;
  const signature = JSON.stringify({ ...progress, running:Boolean(isRunning) });
  useEffect(() => {
    const current = JSON.parse(signature);
    const event = reviewFeedback(last.current, current, personas);
    last.current = current;
    let frame;
    if (event) {
      frame = requestAnimationFrame(() => {
        clearTimeout(clearTimer.current);
        setNotice(event);
        clearTimer.current = setTimeout(() => setNotice(null), event.kind === 'complete' ? 9000 : 5000);
      });
    } else if (current.stopped || (!current.running && !current.completed)) {
      frame = requestAnimationFrame(() => setNotice(null));
    }
    return () => cancelAnimationFrame(frame);
  }, [signature, personas]);
  useEffect(() => () => clearTimeout(clearTimer.current), []);
  const steps = ['稿件就绪','各团审阅','主编汇总',progress.incomplete ? '部分结果已保存' : '审阅完成'];
  const stageIndex = {preparing:0,reviewing:1,chair:2,complete:3}[progress.stage];
  const liveIndex=(props.rounds || []).findIndex(r=>(r.round_number || r.round)===currentRound);
  const liveRound=(props.rounds || [])[liveIndex >= 0 ? liveIndex : currentRound-1];
  const comments=roundComments(personas,liveRound || {},liveIndex >= 0 ? liveIndex : currentRound-1);

  return <>
    {(isRunning || progress.completed) && !progress.stopped && <ol className="review-journey" aria-label="审阅阶段">{steps.map((step,i)=>{
      const done = progress.completed || i < stageIndex;
      const active = !progress.completed && i === stageIndex;
      return <li key={step} className={`${done ? 'is-done' : ''} ${active ? 'is-active' : ''}`} aria-current={active ? 'step' : undefined}><span aria-hidden="true">{done ? '✓' : active ? '•••' : '○'}</span><strong>{step}</strong></li>;
    })}</ol>}
    {isRunning && !progress.stopped && <section className={`review-progress ${progress.chair ? 'is-chair' : ''}`} aria-label="评审进度">
      {!progress.chair && <ReviewBrainstorm personas={personas} returned={progress.returned} failed={progress.failed} preparing={phase === 'initializing' || !currentRound} comments={comments} commentTarget={props.commentTarget} onCommentSelect={props.onCommentSelect}/>}
      <div className="review-progress__heading"><span className="review-progress__pulse" aria-hidden="true"/><strong>{progress.message}</strong><span className="review-progress__hint">返回一团，先看一团</span></div>
      <div className="review-progress__track" aria-label="各团返回状态">{personas.map(p => <span key={p.id} className={progress.returned.includes(p.id) ? 'is-returned' : progress.failed.includes(p.id) ? 'is-failed' : 'is-reading'} title={p.name}><strong>{p.name.replace('评审团','团')}</strong><span><i/>{progress.returned.includes(p.id) ? '已返回' : progress.failed.includes(p.id) ? '未完成' : phase === 'initializing' ? '准备中' : progress.chair ? '待核对' : '读稿中'}</span></span>)}</div>
      <p className="review-progress__caption">{phase === 'initializing' ? '连接模型后开始读稿，返回前不会生成模拟进度。' : progress.chair ? '汇总需要核对原文；五团意见仍可先行查看。' : `正在进行第 ${currentRound} 轮，等待中的评审团会在返回后亮起。`}</p>
    </section>}
    <div className={`review-feedback ${notice ? 'is-visible' : ''} ${notice?.kind === 'complete' ? 'is-complete' : ''}`} role="status" aria-live="polite" aria-atomic="true">
      {notice && <><span className="review-feedback__stamp" aria-hidden="true">{notice.kind==='partial'?'!':<img src="/yuanbao-ip-cat-256.png" alt="" width="48" height="48"/>}</span><div><strong>{notice.kind === 'partial' ? '已保存部分审阅结果' : notice.kind === 'complete' ? '审阅结果已就位' : notice.kind === 'returned' ? '收到新的评审意见' : notice.kind === 'chair' ? '主编接棒汇总' : '稿件已送达'}</strong><p>{notice.text}</p>{['returned','complete','partial'].includes(notice.kind) && <a href={`#${notice.kind === 'complete' ? props.editorTarget : props.teamTarget}`}>{notice.kind === 'complete' ? '查看主编结论' : '查看各团意见'} <span aria-hidden="true">↗</span></a>}</div><button aria-label="关闭进度提示" onClick={()=>setNotice(null)}>×</button></>}
    </div>
  </>;
}
