// Presentation helpers shared with the evidence-based automatic forecast.
export function finalPaperScore(report) {
  return report?.complete && typeof report.score==='number' && Number.isFinite(report.score) && report.score>=0 && report.score<=10 ? report.score : null;
}

export function retentionTime(seconds) {
  const whole=Math.round(seconds);
  return `${Math.floor(whole/60)}:${String(whole%60).padStart(2,'0')}`;
}
