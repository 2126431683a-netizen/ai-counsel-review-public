export default function ReviewScoreChecks({ checks = [] }) {
  if (!checks.length) return null;
  return <section className="review-score-checks" aria-label="画像评分明细">
    <h5>评分明细</h5>
    {checks.map(check=><div className="review-score-check" key={check.id}>
      <div><strong>{check.name}</strong><span>{check.score}<small> / 5</small></span></div>
      {check.basis && <blockquote>{check.basis}</blockquote>}
      {check.rationale && <p>{check.rationale}</p>}
      {check.gap && <p className="review-score-check__gap"><strong>距更高档位：</strong>{check.gap}</p>}
    </div>)}
  </section>;
}
