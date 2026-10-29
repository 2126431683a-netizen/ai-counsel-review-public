import asyncio
from collections import Counter
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from backend import advisors
from backend.personas import Persona
from backend.settings import Settings
from backend.review_scoring import consume_score, group_config, build_score_report

DRAFT='先确认内容，再生成工程。改完回到预览检查。'


def panel():
    bundle=json.loads((Path(__file__).resolve().parents[2]/'desktop/role_bundle.json').read_text(encoding='utf-8'))
    ps={pid:Persona(id=pid,is_custom=True,**fields) for pid,fields in bundle['personas'].items()}
    return bundle, ps


def output(cfg, basis='先确认内容', score=8):
    meta={'comments':[], 'dimension_notes':{d['id']:{'basis':basis,'rationale':'先有内容控制点再制作','deduction':'本例仅为短流程，保留主观余地'} for d in cfg['dimensions']}}
    if cfg.get('rubric_version') == 2:
        for d in cfg['dimensions']:
            meta['dimension_notes'][d['id']]['checks'] = [{'id':c['id'],'score':score/2,'basis':basis,'rationale':'测试档位的具体控制点','gap':'短流程尚未展示控制点的具体内容'} for c in d['checks']]
    scores={'scores':{d['id']:score for d in cfg['dimensions']}, 'unrated_reasons':{}}
    return '先把内容定下来。\n<review-comments>'+json.dumps(meta,ensure_ascii=False)+'</review-comments>\n<review-score>'+json.dumps(scores)+'</review-score>\nCONSENSUS_SCORE: 5'


def test_scores_need_locatable_independent_notes_without_changing_model_numbers():
    _,ps=panel();cfg=group_config(ps['source-tech'].system_prompt)
    _,good=consume_score(output(cfg),cfg,DRAFT)
    assert good['status']=='ok' and good['evidence_status']=='located' and good['score']==8
    _,bad=consume_score(output(cfg,'稿里没有的话'),cfg,DRAFT)
    assert bad['status']=='unverified' and bad['score'] is None and bad['proposed_score']==8
    assert all(d['score']==8 for d in bad['dimensions'])
    _,missing=consume_score('<review-score>'+json.dumps({'scores':{d['id']:9 for d in cfg['dimensions']}})+'</review-score>',cfg,DRAFT)
    assert missing['status']=='unverified'


def test_report_recalculates_dimensions_instead_of_trusting_saved_total():
    _,ps=panel();people=[p for pid,p in ps.items() if pid!='source-editor'];responses=[]
    for p in people:
        cfg=group_config(p.system_prompt);_,rating=consume_score(output(cfg),cfg,DRAFT)
        rating.update(raw_score='999',score=999)
        responses.append({'persona_id':p.id,'review_rating':rating})
    report=build_score_report(people,responses)
    assert report['score']==8 and all(g['score']==8 for g in report['groups'])
    responses[0]['error']='接口返回失败'
    assert build_score_report(people,responses)['score'] is None


@pytest.mark.asyncio
async def test_failed_roles_persist_retry_is_bounded_concurrency_and_costs_are_true(monkeypatch):
    bundle,ps=panel();calls=Counter();active=0;peak=0
    async def query(pid,prompt,personas_map,model_assignments,default_model,temperature,**kwargs):
        nonlocal active,peak
        calls[pid]+=1;active+=1;peak=max(peak,active)
        await asyncio.sleep(.01)
        active-=1
        cfg=group_config(ps[pid].system_prompt)
        error='HTTP 401 invalid credential' if pid=='source-surfer' else 'Request timed out' if pid=='source-practical' and calls[pid]==1 else None
        return pid,default_model,None if error else output(cfg),error,None,{'model':default_model,'total_cost':None,'cost_status':'unknown'}
    neutral=AsyncMock(return_value={'content':'只汇总实际返回的四团意见。','error':None})
    monkeypatch.setattr(advisors,'get_settings',lambda:Settings(**bundle['settings']))
    monkeypatch.setattr(advisors,'get_persona',lambda pid:ps.get(pid))
    monkeypatch.setattr(advisors,'get_personas_by_ids',lambda ids:[ps[x] for x in ids])
    monkeypatch.setattr(advisors,'_query_advisor',query)
    monkeypatch.setattr(advisors,'_query_neutral',neutral)
    ids=[pid for pid in ps if pid!='source-editor']
    events=[e async for e in advisors.run_debate(DRAFT,ids,default_model='custom:test',max_rounds=1,round_policy='fixed')]
    result=next(e['data'] for e in events if e['type']=='advisor_complete')
    responses=result['rounds'][0]['responses']
    assert peak<=2 and calls['source-practical']==2 and calls['source-surfer']==1
    assert len(responses)==5 and next(r for r in responses if r['persona_id']=='source-surfer')['error']=='HTTP 401 invalid credential'
    assert next(r for r in responses if r['persona_id']=='source-practical')['attempts']==2
    assert result['verdict']['review_score_report']['score'] is None
    assert result['cost_report']['total_calls']==6  # chair double has no cost; all six reviewer attempts retained
    assert '未取得结果：玩梗冲浪党' in neutral.call_args.args[1]


@pytest.mark.asyncio
async def test_all_failed_preserves_errors_and_does_not_generate_fake_chair(monkeypatch):
    bundle,ps=panel()
    async def fail(pid,*args,**kwargs):return pid,'custom:test',None,'HTTP 401 invalid credential'
    neutral=AsyncMock()
    monkeypatch.setattr(advisors,'get_settings',lambda:Settings(**bundle['settings']))
    monkeypatch.setattr(advisors,'get_persona',lambda pid:ps.get(pid))
    monkeypatch.setattr(advisors,'get_personas_by_ids',lambda ids:[ps[x] for x in ids])
    monkeypatch.setattr(advisors,'_query_advisor',fail)
    monkeypatch.setattr(advisors,'_query_neutral',neutral)
    events=[e async for e in advisors.run_debate(DRAFT,list(ps)[:-1],default_model='custom:test',max_rounds=3,round_policy='fixed')]
    result=next(e['data'] for e in events if e['type']=='advisor_complete')
    assert len(result['rounds'])==1 and len(result['rounds'][0]['responses'])==5
    assert all(r['error'] for r in result['rounds'][0]['responses'])
    assert result['verdict']['error'] and not result['verdict']['content']
    neutral.assert_not_called()
