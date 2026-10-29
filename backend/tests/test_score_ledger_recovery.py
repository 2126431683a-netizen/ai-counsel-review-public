"""Broken summary JSON must not discard complete, validated checkpoint scores."""
import copy
import json
from pathlib import Path

import pytest
from backend.review_scoring import consume_score, group_config

ROOT = Path(__file__).resolve().parents[2]
DRAFT = '先展示分镜，再生成工程。最后打开预览检查结果。'


def fixture():
    bundle = json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
    cfg = group_config(bundle['personas']['source-beginner']['system_prompt'])
    notes = {d['id']: {'basis': '先展示分镜', 'context': '最后打开预览检查结果',
        'rationale': '已有明确控制点，但缺少具体操作示例', 'deduction': '未给具体操作入口',
        'checks': [{'id': c['id'], 'score': 3.5, 'basis': '先展示分镜',
                    'rationale': '基本顺序能跟上', 'gap': '未展示具体入口'} for c in d['checks']]}
        for d in cfg['dimensions']}
    notes['commercial'].update(deduction='不适用：没有商业推广依据', checks=[])
    return cfg, {'comments': [], 'dimension_notes': notes}


def content(notes, tail=''):
    return '这一步我能跟上。\n<review-comments>'+json.dumps(notes, ensure_ascii=False)+'</review-comments>\n'+tail


@pytest.mark.parametrize('tail', ['', '<review-score>{bad}</review-score>',
    '<review-score>{"scores":{}}}</review-score>'])
def test_complete_ledger_survives_missing_or_malformed_summary(tail):
    cfg, notes = fixture()
    clean, rating = consume_score(content(notes, tail), cfg, DRAFT)
    assert rating['status']=='ok' and rating['score']==7
    assert rating['coverage']==75 and rating['evidence_status']=='located'
    assert rating['calculation_source']=='validated_check_ledger'
    assert rating['dimensions'][-1]['score'] is None
    assert '未重新评价稿件' in clean and '<review-score>' not in clean


@pytest.mark.parametrize('change', ['quote','reason','gap','missing_dimension','missing_check',
    'duplicate_check','quarter_point','text_score','boolean','no_na_reason','no_na_quote','foreign_dimension'])
def test_incomplete_or_untraceable_ledgers_never_create_scores(change):
    cfg, notes = fixture(); first=notes['dimension_notes']['clarity']; check=first['checks'][0]
    if change=='quote':check['basis']='不存在的原文'
    elif change=='reason':check['rationale']=''
    elif change=='gap':check['gap']=''
    elif change=='missing_dimension':del notes['dimension_notes']['opening']
    elif change=='missing_check':first['checks'].pop()
    elif change=='duplicate_check':first['checks'][1]['id']=first['checks'][0]['id']
    elif change=='quarter_point':check['score']=3.25
    elif change=='text_score':check['score']='3.5'
    elif change=='boolean':check['score']=True
    elif change=='no_na_reason':notes['dimension_notes']['commercial']['deduction']='未见广告'
    elif change=='no_na_quote':notes['dimension_notes']['commercial']['basis']='稿里没有这句'
    else:notes['dimension_notes']['surprise']=copy.deepcopy(first)
    result=consume_score(content(notes),cfg,DRAFT)[1]
    assert result['status']=='invalid' and result['score'] is None


@pytest.mark.parametrize('tail', ['<review-score>{', '<review-score>{}</review-score>',
    '<review-score>null</review-score>', '<review-score>{}</review-score><review-score>{}</review-score>'])
def test_truncated_ambiguous_or_semantically_invalid_summary_is_not_overridden(tail):
    cfg,notes=fixture();rating=consume_score(content(notes,tail),cfg,DRAFT)[1]
    assert rating['status']=='invalid' and rating['ledger_recovery_blocked']


def test_parseable_conflict_is_preserved_as_unverified_instead_of_regraded():
    cfg,notes=fixture()
    summary={'scores':{d['id']:None if d['id']=='commercial' else 10 for d in cfg['dimensions']},
             'unrated_reasons':{'commercial':'不适用：没有推广'}}
    result=consume_score(content(notes,'<review-score>'+json.dumps(summary)+'</review-score>'),cfg,DRAFT)[1]
    assert result['status']=='unverified' and result['proposed_score']==10
    assert 'calculation_source' not in result


def test_no_recovery_without_manuscript_or_from_legacy_rules():
    cfg,notes=fixture()
    assert consume_score(content(notes),cfg)[1]['status']=='invalid'
    cfg.pop('rubric_version')
    assert consume_score(content(notes),cfg,DRAFT)[1]['status']=='invalid'


@pytest.mark.asyncio
async def test_full_round_chair_gets_recovered_total_without_additional_model_calls(monkeypatch):
    from backend import advisors
    from backend.personas import Persona
    from backend.settings import Settings
    bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
    people={pid:Persona(id=pid,is_custom=True,**role) for pid,role in bundle['personas'].items()}
    cfg,base=fixture();calls=[]
    async def query(pid,*args,**kwargs):
        calls.append(pid)
        c=group_config(people[pid].system_prompt)
        notes={'comments':[], 'dimension_notes':{}}
        for d in c['dimensions']:
            notes['dimension_notes'][d['id']]=copy.deepcopy(base['dimension_notes']['commercial' if d['id']=='commercial' else 'clarity'])
        return pid,'custom:fixture',content(notes)+'\nCONSENSUS_SCORE: 4',None,None,{}
    async def neutral(model,prompt,**kwargs):
        calls.append('chair');assert '7.0/10' in prompt
        return {'content':'按实际返回的意见收束。','error':None}
    monkeypatch.setattr(advisors,'get_settings',lambda:Settings(**bundle['settings']))
    monkeypatch.setattr(advisors,'get_persona',people.get)
    monkeypatch.setattr(advisors,'get_personas_by_ids',lambda ids:[people[p] for p in ids])
    monkeypatch.setattr(advisors,'_query_advisor',query)
    monkeypatch.setattr(advisors,'_query_neutral',neutral)
    events=[e async for e in advisors.run_debate(DRAFT,list(people)[:-1],default_model='custom:fixture',max_rounds=1,round_policy='fixed')]
    result=next(e['data'] for e in events if e['type']=='advisor_complete')
    assert result['verdict']['review_score_report']['score']==7
    assert len(calls)==6

