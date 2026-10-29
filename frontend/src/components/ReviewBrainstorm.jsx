import ReviewEmblem from './ReviewEmblem.jsx';
import { useEffect, useRef, useState } from 'react';
import { reviewGroupName } from '../utils/reviewPresentation.js';
import { discussionBubbles } from '../utils/reviewDiscussion.js';

export default function ReviewBrainstorm({ personas = [], returned = [], failed = [], chair = false, preparing = false, comments = [], commentTarget, onCommentSelect }) {
  const [tick,setTick]=useState(0);
  const [autoPlay,setAutoPlay]=useState(true);
  const paused=useRef({hover:false,focus:false});
  useEffect(()=>{
    const motion=matchMedia('(prefers-reduced-motion: reduce)');
    let timer;
    const update=()=>{clearInterval(timer);if(!motion.matches && autoPlay) timer=setInterval(()=>{if(!document.hidden && !paused.current.hover && !paused.current.focus)setTick(t=>t+1);},1100);};
    update();motion.addEventListener('change',update);
    return ()=>{clearInterval(timer);motion.removeEventListener('change',update);};
  },[autoPlay]);
  const actors = personas.length ? personas : [{id:'waiting',name:'评审团',avatar_emoji:'review:custom'}];
  return <div className={`review-brainstorm ${chair ? 'is-chair' : ''} ${preparing ? 'is-preparing' : ''} ${actors.length>5 ? 'has-many' : ''}`} onPointerEnter={()=>{paused.current.hover=true;}} onPointerLeave={()=>{paused.current.hover=false;}} onFocusCapture={()=>{paused.current.focus=true;}} onBlurCapture={e=>{if(!e.currentTarget.contains(e.relatedTarget))paused.current.focus=false;}} aria-label={preparing ? '评审团准备中' : chair ? '主编整理意见' : '评审团讨论中'}>
    <div className="review-brainstorm__intro"><strong>{preparing ? '稿件已送达，评审团准备就位' : chair ? '把各团意见带回原稿，再作判断' : '先读完整篇，再交换看法'}</strong><button type="button" className="review-brainstorm__pause" aria-pressed={!autoPlay} onClick={()=>setAutoPlay(value=>!value)}>{autoPlay ? '暂停气泡' : '继续轮换'}</button></div>
    <div className="review-brainstorm__actors" data-count={actors.length} style={{'--brain-count':actors.length}}>
      {actors.map((p,i)=>{const state=failed.includes(p.id)?'failed':returned.includes(p.id)?'returned':preparing?'preparing':'reading';const bubbles=discussionBubbles(p,comments,Math.floor((tick+i)/actors.length),state);return <div key={p.id} className={`review-brainstorm__actor ${returned.includes(p.id) ? 'has-returned' : failed.includes(p.id) ? 'has-failed' : ''}`} style={{'--seat':i}}>
        <div className="review-brainstorm__speech" aria-label={`${reviewGroupName(p)}${state==='returned'?'已返回评论':'状态气泡'}`}>
          {bubbles.map((bubble,index)=><div className={`review-brainstorm__bubble is-${bubble.type} ${index===bubbles.length-1?'is-current':'is-previous'}`} key={`${bubble.type}:${bubble.commentKey || bubble.text}`}>
            <small>{bubble.label}{state==='reading' && index===bubbles.length-1 && <i className="review-brainstorm__typing" aria-hidden="true"><b/><b/><b/></i>}</small>{bubble.type==='comment'?<a href={`#${commentTarget}`} onClick={()=>onCommentSelect?.(bubble.commentKey)} title={bubble.text}>{bubble.text}</a>:<span>{bubble.text}</span>}
          </div>)}
        </div>
        <ReviewEmblem persona={p} compact/><span className="review-brainstorm__name">{reviewGroupName(p).replace('评审团','团')}</span>
      </div>;})}
    </div>
    <div className="review-brainstorm__desk" aria-hidden="true">
      <svg viewBox="0 0 600 100" fill="none"><ellipse cx="300" cy="58" rx="280" ry="35" fill="#b8bcc2"/><ellipse cx="300" cy="49" rx="280" ry="35" fill="#ffe6b4" stroke="#252733" strokeWidth="3"/><path d="m220 23 100-5 28 44-100 5Z" fill="#fffdf5" stroke="#252733" strokeWidth="2.5"/><path className="review-brainstorm__scribble" d="m240 32 60-3m-55 12 64-3m-58 12 40-2" stroke="#505362" strokeWidth="3" strokeLinecap="round"/><path className="review-brainstorm__pencil" d="m360 39 25-19 5 5-25 19-9 3Z" fill="#93443b" stroke="#252733" strokeWidth="2"/><path d="M170 39q-10 12 2 18m247-19q12 9 0 18" stroke="#252733" strokeWidth="2"/></svg>
      {chair && <span className="review-brainstorm__chair"><ReviewEmblem persona={{name:'主编'}} compact/><span>主编收束中</span></span>}
    </div>
    <p className="review-brainstorm__footnote">{preparing ? '连接就绪后开始读稿。' : chair ? '先核对，再整理真正值得处理的意见。' : '状态气泡是关注点示意；已返回评论取自本轮实际输出，点击可看依据。'}</p>
  </div>;
}
