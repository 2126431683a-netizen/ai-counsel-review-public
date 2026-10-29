"""Read-only audit of saved ratings; no manuscript/model data is written out."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from backend.review_scoring import consume_score,group_config,build_score_report
from types import SimpleNamespace


def main():
    profile=Path(os.environ['LOCALAPPDATA'])/'AICounselReview'
    paths=sorted(profile.rglob('*.json'))
    before={str(p.relative_to(profile)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    fixtures=[];backend=[];recovered=[];unchanged=0
    for p in (profile/'conversations').glob('*.json'):
        data=json.loads(p.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or not data.get('messages'):continue
        draft=data['messages'][0].get('content','')
        for message in data['messages']:
            if message.get('role')!='assistant' or not message.get('personas'):continue
            people=message['personas'];by_id={x['id']:x for x in people}
            for rnd in message.get('rounds',[]):
                responses=[]
                for response in rnd.get('responses',[]):
                    cfg=group_config(by_id[response['persona_id']]['system_prompt'])
                    saved=response.get('review_rating') or {}
                    text=response.get('content') or ''
                    if saved.get('dimensions'):
                        payload={'scores':{d['id']:d['score'] for d in saved['dimensions']},
                                 'unrated_reasons':{d['id']:d['reason'] for d in saved['dimensions'] if d['score'] is None}}
                        text+='\n<review-score>'+json.dumps(payload)+'</review-score>'
                    rating=consume_score(text,cfg,draft)[1]
                    responses.append({**response,'review_rating':rating})
                    if saved.get('status')=='ok':
                        assert rating['status']=='ok' and rating['score']==saved['score']
                        unchanged+=1
                    elif rating['status']=='ok':
                        recovered.append({'round':rnd['round_number'],'group':cfg['id'],'score':rating['score']})
                    backend.append({'status':rating['status'],'score':rating['score']})
                fixtures.append({'question':draft,'personas':people,'responses':rnd['responses'],
                                 'backendTotal':build_score_report([SimpleNamespace(**p) for p in people],responses)['score']})
    module=(ROOT/'frontend/src/utils/reviewScoring.js').as_uri()
    code=f"""import {{consumeScore,groupConfig,buildScoreReport}} from {json.dumps(module)};
let input='';for await(const b of process.stdin)input+=b;
const fixtures=JSON.parse(input),ratings=[];
for(const f of fixtures){{
 for(const r of f.responses){{const p=f.personas.find(p=>p.id===r.persona_id);const v=consumeScore(r.content,groupConfig(p.system_prompt),r.review_rating,f.question).rating;ratings.push({{status:v.status,score:v.score}});}}
 if(buildScoreReport(f.personas,f.responses,f.question).score!==f.backendTotal)throw Error('total mismatch');
}}
process.stdout.write(JSON.stringify(ratings));"""
    result=subprocess.run(['node','--input-type=module','-e',code],input=json.dumps(fixtures),capture_output=True,text=True,encoding='utf-8',check=True)
    assert json.loads(result.stdout)==backend
    after={str(p.relative_to(profile)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before==after
    report={'readOnly':True,'existingValidScoresUnchanged':unchanged,'recovered':recovered,
            'frontendBackendAgreement':True,'profileJsonUnchanged':len(before),'modelCalls':0,
            'roundTotals':[f['backendTotal'] for f in fixtures]}
    (ROOT/'build/score-ledger-history-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
