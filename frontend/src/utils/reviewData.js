// Read-only chart geometry. Never interpolate missing or differently scored rounds.
export function reportShape(report) {
  return JSON.stringify((report?.groups || []).map(g=>[g.group_id,g.weight,(g.dimensions || []).map(d=>[d.id,d.weight]).sort((a,b)=>String(a[0]).localeCompare(String(b[0])))]).sort((a,b)=>String(a[0]).localeCompare(String(b[0]))));
}

function compatibleReports(a,b) {
  if(!a || !b || a.groups.length!==b.groups.length) return false;
  return a.groups.every(g=>{
    const other=b.groups.find(row=>row.group_id===g.group_id);
    if(!other || other.weight!==g.weight) return false;
    // An invalid score may not carry dimensions; missing data is not a policy change.
    return !g.dimensions?.length || !other.dimensions?.length || reportShape({groups:[g]})===reportShape({groups:[other]});
  });
}

export function reviewSeries(roundReports = [], fallback) {
  const source=roundReports.length ? roundReports : fallback ? [{round:1,report:fallback}] : [];
  const reference=source.at(-1)?.report || fallback;
  return source.map((item,index)=>{
    const report=item.report;
    const compatible=compatibleReports(report,reference);
    const score=compatible && report.complete && Number.isFinite(report.score) && report.score>=0 && report.score<=10 ? report.score : null;
    return {round:item.round ?? index+1,report,compatible,score};
  });
}

export function reviewPlot(series) {
  const points=series.map((p,index)=>({...p,x:series.length===1 ? 190 : 32+index*316/Math.max(1,series.length-1),y:p.score===null ? null : 132-p.score*10}));
  const segments=[];
  let segment=[];
  for(const point of points) {
    if(point.score===null) {if(segment.length) segments.push(segment);segment=[];}
    else segment.push(point);
  }
  if(segment.length) segments.push(segment);
  return {points,segments};
}
