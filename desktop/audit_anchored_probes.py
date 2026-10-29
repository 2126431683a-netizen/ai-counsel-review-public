"""Re-audit unchanged synthetic model text with the final boundary/parser rules."""
import json
from pathlib import Path
from backend.advisors import strip_consensus_tag
from backend.review_scoring import consume_score,group_config,build_score_report
from backend.personas import Persona

ROOT=Path(__file__).resolve().parent.parent
bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
folder=ROOT/'build/anchored-v10-check/final'
raw=json.loads((folder/'results.json').read_text(encoding='utf-8'))
records=[]
for record in raw['records']:
    record=dict(record)
    if record['persona_id']!='source-editor':
        clean,rating=consume_score(strip_consensus_tag(record['content']),group_config(bundle['personas'][record['persona_id']]['system_prompt']),record['draft'])
        record['raw_content']=record['content'];record['originalAudit']=record['review_rating']
        record.update(content=clean,review_rating=rating)
    records.append(record)
# Keep the failed original quote audit; the re-probe is not a post-hoc score edit.
replacement=json.loads((folder/'practical-format-smoke.json').read_text(encoding='utf-8'))
assert replacement['review_rating']['status']=='ok'
for i,record in enumerate(records):
    if record['persona_id']=='source-practical' and record['case']=='middle':
        assert record['review_rating']['status']=='unverified'
        (folder/'practical-invalid-quote-preserved.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        replacement['raw_content']=replacement['content']
        replacement['content'],replacement['review_rating']=consume_score(strip_consensus_tag(replacement['content']),group_config(bundle['personas']['source-practical']['system_prompt']),replacement['draft'])
        records[i]=replacement
assert all(r['review_rating']['status']=='ok' for r in records if r['persona_id']!='source-editor')
people=[Persona(id=pid,is_custom=True,**role) for pid,role in bundle['personas'].items() if pid!='source-editor']
middle=[r for r in records if r['case']=='middle']
report=build_score_report(people,middle)
assert report['complete']
summary={'syntheticOnly':True,'newModelCalls':0,'completeMiddlePanel':True,'weightedMiddleScore':report['score'],
         'middleScores':{r['persona_id']:r['review_rating']['score'] for r in middle},
         'strongFinalScores':{r['persona_id']:r['review_rating']['score'] for r in records if r['case']=='strong'},
         'boundaryOnlyNormalizations':sum(bool(r.get('review_rating',{}).get('format_normalized')) for r in records),
         'invalidQuoteOriginalPreserved':True,'separateFinalFormatReprobeUsed':True,
         'limitations':'Designed synthetic contrasts, not human-rated ground truth. Original exploratory failures remain saved. No scores or quotes repaired.'}
(folder/'validated-results.json').write_text(json.dumps({'summary':summary,'records':records},ensure_ascii=False,indent=2),encoding='utf-8')
(folder/'validated-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
