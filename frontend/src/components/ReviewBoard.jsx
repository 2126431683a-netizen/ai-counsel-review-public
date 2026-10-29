import { useMemo, useRef, useState, useEffect, useId } from 'react';
import MarkdownContent from './MarkdownContent';
import CostReport from './CostReport';
import { groupConfig, buildScoreReport, combineVerdict, reviewRatingLabel } from '../utils/reviewScoring.js';
import { reviewGroupName, parseReviewResponse, roundComments, reviewQuoteStatus } from '../utils/reviewPresentation.js';
import { reviewIdentity } from '../utils/reviewIdentity.js';
import ReviewEmblem from './ReviewEmblem';
import ReviewScoreChecks from './ReviewScoreChecks.jsx';
import ReviewProgress from './ReviewProgress.jsx';
import ReviewWeightCells from './ReviewWeightCells.jsx';
import ReviewEditorial from './ReviewEditorial.jsx';
import { reviewAvailability, reviewFailureMessage } from '../utils/reviewAvailability.js';
import './ReviewBoard.css';
import './ReviewReliabilityTheme.css';

const EMPTY_ROUND = Object.freeze({});

export default function ReviewBoard({ personas = [], rounds = [], verdict, tiebreaker,
  currentRound = 1, maxRounds = 3, roundPolicy = 'adaptive', isRunning = false, phase, question = '', error, costReport, aborted = false }) {
  const [roundChoice, setRoundChoice] = useState(null);
  const [group, setGroup] = useState('all');
  const [query, setQuery] = useState('');
  const [selectedKey, setSelectedKey] = useState(null);
  const detailRef = useRef(null);
  const commentRefs = useRef(new Map());
  const evidenceId = useId();
  const teamTarget = useId();
  const editorTarget = useId();
  const commentTarget = useId();
  const index = Math.max(0, Math.min(roundChoice ?? rounds.length - 1, rounds.length - 1));
  const round = rounds[index] || EMPTY_ROUND;
  const all = useMemo(() => roundComments(personas, round, index, question), [personas, round, index, question]);
  const comments = all.filter(c => (group === 'all' || c.persona.id === group) && (!query || c.text.toLowerCase().includes(query.toLowerCase())));
  const selected = comments.find(c => c.key === selectedKey);
  const score = useMemo(() => buildScoreReport(personas, round.responses || [], question), [personas, round, question]);
  const finalScore = useMemo(() => buildScoreReport(personas, rounds[rounds.length - 1]?.responses || [], question), [personas, rounds, question]);
  const roundReports = useMemo(() => rounds.map((r,i)=>({round:r.round_number || i+1,report:buildScoreReport(personas,r.responses || [],question)})),[personas,rounds,question]);
  const finalNotes = useMemo(()=>Object.fromEntries(personas.map(p=>[p.id,parseReviewResponse(rounds.at(-1)?.responses?.find(r=>r.persona_id===p.id),p,question).dimensionNotes || {}])),[personas,rounds,question]);
  const verdictText = combineVerdict((verdict?.content || '').replace(/<review-comments>[\s\S]*?<\/review-comments>/g, '').split('<review-comments>')[0], finalScore);
  const verdictBody = finalScore ? (verdict?.content || '').replace(/<review-comments>[\s\S]*?<\/review-comments>/g, '').split(/(?:^|\n)#{1,6}\s*审稿团加权评分/)[0].trim() : verdictText;
  const responded = (round.responses || []).filter(r => r.content && !r.error).length;
  const dimensions = selected?.parsed.rating?.dimensions || [];
  const missingRatings = (score?.groups || []).filter(g=>g.score===null && (round.responses || []).some(r=>r.persona_id===g.persona_id && r.content && !r.error));
  const closeDetail = () => {
    const trigger = commentRefs.current.get(selectedKey);
    setSelectedKey(null);
    if (detailRef.current && getComputedStyle(detailRef.current).position !== 'sticky') trigger?.scrollIntoView({ block: 'center' });
    trigger?.focus({ preventScroll: true });
  };
  const failures = (round.responses || []).filter(r => r.error);
  const sharedFailure = failures.length>1 && new Set(failures.map(r=>r.error)).size===1;
  const reviewing = isRunning && (!rounds.length || index === rounds.length-1) && !round.complete && !['verdict', 'tiebreaker', 'error', 'complete'].includes(phase);
  const unavailable = personas.filter(p=>!(round.responses || []).some(r=>r.persona_id===p.id && r.content && !r.error));
  const status = error || phase === 'error' ? '评审中断' : aborted ? '评审已停止' : isRunning ? (phase === 'initializing' || !currentRound ? '评审团准备中' : phase === 'verdict' ? '主编正在汇总' : `${responded}/${personas.length} 个评审团已返回`) : unavailable.length ? `本轮收到 ${responded}/${personas.length} 团意见` : '本轮评审已完成';

  useEffect(() => {
    if (selectedKey && detailRef.current && getComputedStyle(detailRef.current).position !== 'sticky') {
      detailRef.current?.scrollIntoView({ block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
      detailRef.current?.focus({ preventScroll: true });
    }
  }, [selectedKey]);

  return <section className={`review-board ${isRunning ? 'is-running' : ''}`} aria-label="评审工作台">
    <header className="review-board__header">
      <div className="ip-result-heading"><img src="/yuanbao-ip-cat-256.png" alt="" width="64" height="64"/><div><span>源宝审稿室</span><h2>稿件审阅</h2><p>先看主编结论，再听各团意见。</p></div></div>
      <div className="review-board__status"><span className={isRunning ? 'is-running' : ''}>{status}</span>
        <label>评审轮次 <select aria-label="查看评审轮次" value={index} onChange={e => { setRoundChoice(Number(e.target.value)); setSelectedKey(null); }} disabled={!rounds.length}>
          {rounds.length ? rounds.map((r, i) => <option key={i} value={i}>第 {r.round_number || i + 1} 轮{isRunning && i === rounds.length - 1 ? ' · 进行中' : ''}</option>) : <option value={0}>第 {currentRound} 轮</option>}
        </select></label></div>
    </header>
    <p className="review-round-record">{roundPolicy==='fixed' ? `计划${maxRounds}轮审阅，主编最后汇总一次` : `原设最多${maxRounds}轮，可因意见一致提前结束`}{!isRunning && rounds.length>0 ? ` · 实际完成${rounds.filter(r=>r.complete || r.responses?.length).length}轮` : ''}</p>

    {error && <div className="review-board__error" role="alert">{error}</div>}
    <ReviewEditorial id={editorTarget} content={verdictBody} copyText={verdictText} verdict={verdict} report={finalScore} roundReports={roundReports} notes={finalNotes} manuscript={question} isRunning={isRunning} phase={phase} aborted={aborted} error={error} teamTarget={teamTarget}/>
    <ReviewProgress personas={personas} rounds={rounds} currentRound={currentRound} maxRounds={maxRounds} isRunning={isRunning} phase={phase} error={error} aborted={aborted} verdict={verdict} editorTarget={editorTarget} teamTarget={teamTarget} commentTarget={commentTarget} onCommentSelect={key=>{setRoundChoice(null);setGroup('all');setQuery('');setSelectedKey(key);}}/>

    <div className="review-teams-heading" id={teamTarget}><h3>各团意见</h3><p>点选评审团筛选评论，点击评论查看依据。</p></div>
    <div className="review-board__teams" aria-label="评审团筛选与本轮评分">
      {personas.map(p => {
        const response = (round.responses || []).find(r => r.persona_id === p.id);
        const parsed = parseReviewResponse(response, p, question);
        const cfg = groupConfig(p.system_prompt);
        const value = parsed.rating?.status === 'ok' ? parsed.rating.score : cfg ? null : parsed.legacyScore;
        const count = all.filter(c => c.persona.id === p.id).length;
        const identity = reviewIdentity(p);
        const availability = reviewAvailability(response,{running:reviewing,count});
        return <button key={p.id} className={`review-team ${group === p.id ? 'is-active' : ''} ${availability.state === 'failed' || availability.state === 'missing' ? 'is-failed' : response?.content ? 'has-response' : reviewing ? 'is-reading' : ''}`} style={{ '--team-color': identity.accent, '--team-tint': identity.tint }} aria-pressed={group === p.id} onClick={() => { setGroup(group === p.id ? 'all' : p.id); setSelectedKey(null); }}>
          <span className="review-team__top"><ReviewEmblem persona={p}/><span className="review-team__weight">{cfg ? <><span>侧重</span><ReviewWeightCells weight={cfg.weight} label={`${reviewGroupName(p)}权重`} color={identity.accent}/></> : '历史评审'}</span></span>
          <strong>{reviewGroupName(p)}</strong><span className="review-team__focus">{identity.focus}</span><span className="review-team__score">{value === null || value === undefined ? '—' : Number(value).toFixed(1)}{value !== null && value !== undefined && <small>/ 10</small>}</span>
          <span className="review-team__meter" aria-hidden="true"><i style={{ width: `${value === null || value === undefined ? 0 : value * 10}%` }}/></span>
          <span className="review-team__audit" title={parsed.rating?.reason || undefined}>{reviewRatingLabel(parsed.rating,Boolean(response?.content))}</span>
          <span className="review-team__foot">{availability.label}{response?.attempts>1 ? ' · 已重试' : ''}<span>{group === p.id ? '已筛选' : '查看'}</span></span>
        </button>;
      })}
    </div>
    <p className="review-weight-legend">亮格越多，对综合评分的影响越大。</p>
    {personas.some(p=>groupConfig(p.system_prompt)?.scoring_policy==='opening-commercial-v1') && <details className="review-disclosure review-score-policy"><summary>本轮评分：内容、开头与商业融合</summary><div className="review-score-policy__axes">{[['内容质量',60],['开头15–20秒',15],['商业信息融合',25]].map(([name,weight])=><span key={name}><strong>{name}</strong><ReviewWeightCells weight={weight} label={`${name}团内权重`} color="#36587b"/></span>)}</div><p>广告越挤占内容、越打断叙事，融合分越低；产品自然参与解题、有具体依据，融合分越高。无推广时商业项不适用，只计算内容与开头。开头评估是稿面风险，实际跳出率需发布后的留存数据。</p></details>}
    <p className="review-rating-scope">单团分由维度分加权后保留一位小数。引文可定位表示有出处，不代表模型的判断一定正确。</p>
    {missingRatings.length>0 && <details className="review-disclosure review-results-note"><summary>{missingRatings.length} 团已有评论，但评分暂缺 · 查看原因</summary><p>评论正常保留。只有完整、可核对的评分明细才会计入总分；不把缺分当零分。</p>{missingRatings.map(g=><p key={g.persona_id}><strong>{g.name}：</strong>{g.reason}</p>)}</details>}
    {!reviewing && unavailable.length>0 && <div className="review-results-note" role="status"><strong>本轮缺少 {unavailable.length} 团结果</strong><p>{unavailable.map(p=>reviewGroupName(p)).join('、')}未取得可用意见。{unavailable.some(p=>(round.responses||[]).find(r=>r.persona_id===p.id)?.error) ? '返回失败的原因见下方；缺团不计作零分。' : '旧记录未保存失败原因，刷新不能恢复未返回的评论。'}缺少有效团分时不生成加权总分。</p></div>}

    <div className="review-board__toolbar"><button className={group === 'all' ? 'is-active' : ''} onClick={() => { setGroup('all'); setSelectedKey(null); }}>全部评审团 <span>{all.length}</span></button>
      <label className="review-board__search"><span aria-hidden="true">⌕</span><input type="search" value={query} onChange={e => { setQuery(e.target.value); setSelectedKey(null); }} placeholder="查找评论关键词" aria-label="查找评论关键词"/></label>
      <div className="review-board__total">本轮加权分 <strong>{score?.complete ? `${score.score.toFixed(1)}` : '—'}</strong><small>{score ? score.complete ? '/ 10 · 模型主观分' : `${score.groups.filter(r=>r.score!==null).length}/${score.groups.length} 团评分可用` : '旧记录未加权'}</small></div>
    </div>

    <div className="review-board__feed-heading" id={commentTarget}><h3>{group === 'all' ? '评审团的声音' : reviewGroupName(personas.find(p => p.id === group))}</h3><span>模拟观众讨论 · 点击评论查看依据</span></div>
    <div className={`review-board__body ${selected ? 'has-detail' : ''}`}>
      <div className="review-board__feed" aria-label="评审团评论">
        {!comments.length && <div className="review-board__empty">{query ? '没有匹配的评论，试试其他关键词。' : reviewing ? '评审团正在读稿，评论会在各团返回后陆续出现。' : failures.length===personas.length && failures.length ? '模型接口未返回完整回复，本轮尚未产生评论或评分。请查看下方连接错误。' : group!=='all' ? reviewAvailability((round.responses||[]).find(r=>r.persona_id===group)).reason || '本团已返回完整审阅，但没有可展示的短评。可在下方展开原始输出。' : '本轮没有可提取的短评，可在下方查看完整审阅输出。'}</div>}
        {comments.map(c => <button key={c.key} ref={node => { if (node) commentRefs.current.set(c.key, node); else commentRefs.current.delete(c.key); }} className={`review-comment ${selected?.key === c.key ? 'is-selected' : ''}`} onClick={() => setSelectedKey(c.key)} aria-expanded={selected?.key === c.key} aria-controls={evidenceId} style={{ '--team-color': reviewIdentity(c.persona).accent, '--team-tint': reviewIdentity(c.persona).tint }}>
          <ReviewEmblem persona={c.persona} className="review-comment__emblem" compact/><span className="review-comment__main"><span className="review-comment__meta"><strong>{reviewGroupName(c.persona)}</strong><span>{c.reply ? '团内回应' : c.kind === '观众反应' ? '看完想说' : c.kind}</span></span>{c.reply && <span className="review-comment__reply">回应：{c.reply.text}</span>}<span className="review-comment__text">{c.text.replace(/^[-*]\s*/, '').replace(/^“([\s\S]*)”$/, '$1')}</span><span className="review-comment__open">{selected?.key === c.key ? '正在查看评论依据' : '查看评论依据'} <span aria-hidden="true">↗</span></span></span>
        </button>)}
        {sharedFailure ? <div className="review-board__error is-shared"><strong>{failures.length} 个评审团遇到相同接口错误</strong><p>{reviewFailureMessage(failures[0].error)}</p><small>{failures.map(r=>reviewGroupName(personas.find(p=>p.id===r.persona_id))).join('、')}</small></div> : failures.map(r => <div className="review-board__error" key={r.persona_id}>{reviewGroupName(personas.find(p => p.id === r.persona_id))}：{reviewFailureMessage(r.error)}</div>)}
      </div>

      <aside hidden={!selected} id={evidenceId} className={`review-evidence ${selected ? 'has-selection' : ''}`} ref={detailRef} tabIndex={-1} aria-label="所选评论的审阅详情">
        {selected ? <><div className="review-evidence__top"><span>审阅详情</span><button onClick={closeDetail} aria-label="关闭详情并返回评论">×</button></div>
          <div className="review-evidence__identity"><ReviewEmblem persona={selected.persona} compact/><div><h3>{reviewGroupName(selected.persona)}</h3><span>{reviewIdentity(selected.persona).focus}</span></div></div><blockquote>{selected.text}</blockquote>
          {selected.association === 'group' && <p className="review-evidence__notice">这份记录没有逐条关联的说明。下方是该评审团的共用备忘，可结合评论核对。</p>}
          {selected.parsed.skippedComments>0 && <p className="review-evidence__notice">另有 {selected.parsed.skippedComments} 条评论的正文关联不一致，未补造对应关系；可展开该团完整输出核对。</p>}
          {selected.reply && <section className="review-evidence__reply"><h4>回应的评论</h4><p>{selected.reply.text}</p></section>}
          {selected.detail.basis && <p className={`review-quote-status is-${reviewQuoteStatus(selected.detail.basis,question)}`} title="只确认引文文字匹配，不表示已经核验外部事实。">{reviewQuoteStatus(selected.detail.basis,question)==='matched' ? '引文已在原稿中定位' : '引文仍需回原稿核对'}</p>}
          {selected.detail.basis && <section><h4>对应原文</h4><MarkdownContent>{selected.detail.basis}</MarkdownContent></section>}
          {selected.detail.context && <section className="review-evidence__context"><h4>全文中的相关解释</h4><MarkdownContent>{selected.detail.context}</MarkdownContent></section>}
          {selected.detail.rationale && <section><h4>为什么这样判断</h4><MarkdownContent>{selected.detail.rationale}</MarkdownContent></section>}
          {selected.detail.limits && <section><h4>限定与待确认</h4><MarkdownContent>{selected.detail.limits}</MarkdownContent></section>}
          {selected.detail.next_step && <section><h4>可以怎么处理</h4><MarkdownContent>{selected.detail.next_step}</MarkdownContent></section>}
          {selected.detail.content && <section><h4>该条原始审阅说明</h4><MarkdownContent>{selected.detail.content}</MarkdownContent></section>}
          {selected.association === 'group' && <section><h4>评审团备忘</h4><MarkdownContent>{selected.parsed.memo || '原始记录未提供额外备忘。请展开完整输出查看上下文。'}</MarkdownContent></section>}
          {selected.association === 'comment' && !Object.values(selected.detail).some(Boolean) && <p>这条记录未提供额外的判断说明。</p>}
          {selected.parsed.rating && selected.parsed.rating.status!=='ok' && <p className="review-results-note">{selected.parsed.rating.reason}。已返回的评论与明细仍可查看，本团暂不计入总分。</p>}
          {selected.parsed.rating?.calculation_source==='validated_check_ledger' && <p className="review-rating-scope">评分汇总格式异常，已按校验通过的子项明细重新计算，没有重新评价稿件或改写评论。</p>}
          {dimensions.length > 0 && <details className="review-disclosure review-dimensions"><summary>本团评分依据与侧重</summary><p className="review-rating-scope">模型对稿面完成度的判断，不代表成片效果或真实观众比例。</p>{dimensions.map(d => {const note=selected.parsed.dimensionNotes[d.id];return <div className="review-dimension" key={d.id}><span>{d.name}<small><ReviewWeightCells weight={d.weight} label={`${d.name}团内权重`} color={reviewIdentity(selected.persona).accent}/></small></span><strong>{d.score === null ? (d.id==='commercial' && groupConfig(selected.persona.system_prompt)?.scoring_policy==='opening-commercial-v1' ? '不适用' : '待定') : `${d.score}/10`}</strong>{d.score !== null && <meter min="0" max="10" value={d.score} aria-label={`${d.name}评分`} />}{d.score === null && <p>{d.reason}</p>}{note && Object.keys(note).length ? <div className="review-dimension__notes">{note.basis && <><h5>稿件依据</h5><blockquote>{note.basis}</blockquote><small>{reviewQuoteStatus(note.basis,question)==='matched'?'已定位原文':'引文待核对'}</small></>}{note.context && <><h5>全文相关解释</h5><p>{note.context}</p></>}{note.rationale && <><h5>为什么给这个分</h5><p>{note.rationale}</p></>}<ReviewScoreChecks checks={note.checks}/>{note.deduction && <><h5>分数的边界</h5><p>{note.deduction}</p></>}</div>:<p>这份记录未保存本维度的独立评分说明，不补造理由。</p>}</div>;})}</details>}
          <details className="review-disclosure"><summary>查看该团完整输出</summary><MarkdownContent>{selected.parsed.fullText}</MarkdownContent></details>
          <p className="review-evidence__footnote">展示已有的依据与判断摘要；模拟意见仍需回到原稿核查。</p>
        </> : null}
      </aside>
    </div>

    <div className="review-board__archive">
      {question && <details className="review-disclosure"><summary>查看原稿 <span>{question.length.toLocaleString()} 字符</span></summary><MarkdownContent>{question}</MarkdownContent></details>}
      <details className="review-disclosure"><summary>查看本轮完整记录</summary>{(round.responses || []).map(r => <section key={r.persona_id}><h3>{reviewGroupName(personas.find(p => p.id === r.persona_id))}</h3><MarkdownContent>{parseReviewResponse(r, personas.find(p => p.id === r.persona_id)).fullText || r.error || '等待返回'}</MarkdownContent></section>)}</details>
      {tiebreaker?.content && <details className="review-disclosure"><summary>分歧复核</summary><MarkdownContent>{tiebreaker.content}</MarkdownContent></details>}
      {costReport && <details className="review-disclosure"><summary>本次评审用量</summary><CostReport report={costReport} title="Advisor Debate Cost"/></details>}
    </div>
  </section>;
}
