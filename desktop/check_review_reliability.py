"""Real complete synthetic round via production orchestration, no history writes."""
import asyncio
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
os.environ['AI_COUNSEL_DATA_DIR']=str(Path(os.environ['LOCALAPPDATA'])/'AICounselReview')
os.environ.setdefault('CUSTOM_REQUEST_TIMEOUT','300')
os.environ.setdefault('NO_PROXY','localhost,127.0.0.1,::1')
from backend import advisors
from backend.personas import Persona
from backend.settings import get_settings
from backend.review_scoring import group_config, consume_score
from desktop.check_discussion_roles import DRAFT

async def main():
    bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
    assert bundle['version'] in (8,9,10)
    people={pid:Persona(id=pid,is_custom=True,**fields) for pid,fields in bundle['personas'].items()}
    settings=get_settings().model_copy(update={'advisor_chair_persona_id':'source-editor'})
    assert settings.advisor_default_model
    advisors.get_settings=lambda:settings
    advisors.get_persona=lambda pid:people.get(pid)
    advisors.get_personas_by_ids=lambda ids:[people[pid] for pid in ids]
    long_stream='--longstream' in sys.argv
    path = ('build/stream-connection-real' if bundle['version']==8 else f"build/stream-connection-v{bundle['version']}-real") if long_stream else f"build/reliability-v{bundle['version']}-real"
    out=ROOT/path;out.mkdir(exist_ok=True)
    draft=(DRAFT+'\n【虚构背景重复记录，仅做等长连接检查】\n'+('笔记已核对，先确认分镜，再生成工程，修改后查看预览。\n'*150))[:3347] if long_stream else DRAFT
    if '--contradiction' in sys.argv:
        broken=DRAFT.replace('每章20秒，总共60秒','每章固定30秒，总共60秒，章时长不能调整')
        prompt=settings.advisor_round1_prompt.format(question=broken,search_context_block='',consensus_tag='CONSENSUS_SCORE: 1-5')
        pid='source-tech'
        result=await advisors._query_advisor(pid,prompt,people,None,settings.advisor_default_model,settings.advisor_temperature)
        assert not result[3] and result[2], 'No usable contradiction result'
        clean,rating=consume_score(advisors.strip_consensus_tag(result[2]),group_config(people[pid].system_prompt),broken)
        assert rating['status']=='ok' and rating['score']<10
        record={'content':clean,'review_rating':rating,'syntheticOnly':True,'historyWritten':False}
        (out/'contradiction.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'case':'time-contradiction','score':rating['score'],'status':rating['status'],'historyWritten':False},ensure_ascii=False),flush=True)
        return
    ids=[pid for pid in people if pid!='source-editor']
    started=time.monotonic();events=[]
    async for event in advisors.run_debate(draft,ids,default_model=settings.advisor_default_model,max_rounds=1,round_policy='fixed',conversation_id=None):
        events.append(event)
        if event['type']=='advisor_response':
            r=event['data'];print(json.dumps({'returned':r['persona_id'],'hasContent':bool(r.get('content')),'failed':bool(r.get('error')),'attempts':r['attempts'],'rating':r.get('review_rating',{}).get('status')},ensure_ascii=False),flush=True)
    result=next(e['data'] for e in events if e['type']=='advisor_complete')
    if long_stream:result['sample_question']=draft
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    responses=result['rounds'][0]['responses']
    assert len(responses)==5 and len({r['persona_id'] for r in responses})==5
    successful=[r for r in responses if r.get('content') and not r.get('error')]
    report=result['verdict']['review_score_report']
    assert report['complete']==all(r.get('review_rating',{}).get('status')=='ok' for r in responses)
    summary={'syntheticOnly':True,'historyWritten':False,'returned':len(successful),'failed':5-len(successful),
        'allFiveOutcomesPreserved':True,'scoreComplete':report['complete'],'score':report['score'],
        'ratingStatuses':{r['persona_id']:r.get('review_rating',{}).get('status','failed') for r in responses},
        'chairHasContent':bool(result['verdict'].get('content')),'elapsedSeconds':round(time.monotonic()-started),
        'totalCalls':result['cost_report']['total_calls'],'manuscriptChars':len(draft),'desktopNetworkEnvironment':True}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':asyncio.run(main())
