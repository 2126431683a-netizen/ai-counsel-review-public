"""v2 ledgers reject unsupported/mismatched scores, without grading prose itself."""
import copy
import json
import pytest
from backend.review_scoring import consume_score, group_config, normalize_review_blocks

DRAFT = '先展示两条原话，再对照分组结果。'
CFG = {'id':'source-tech','name':'技术团','weight':25,'rubric_version':2,
       'dimensions':[{'id':'accuracy','name':'技术表述','weight':100,
                      'checks':[{'id':'a','name':'对象'},{'id':'b','name':'关系'}]}]}

def payload():
    return {'comments':[], 'dimension_notes':{'accuracy':{'basis':'先展示两条原话','rationale':'从原话对应到结果','deduction':'未展开对照结果的具体差异',
        'checks':[{'id':key,'score':3,'basis':'先展示两条原话','rationale':'有基本对照安排，但较概括','gap':'具体结果差异未展开'} for key in ['a','b']]}}}

def grade(notes=None,score=6,cfg=None):
    text='<review-comments>'+json.dumps(notes if notes is not None else payload())+'</review-comments><review-score>'+json.dumps({'scores':{'accuracy':score}})+'</review-score>'
    return consume_score(text,cfg or CFG,DRAFT)[1]

def test_basic_completion_is_six_without_becoming_an_automatic_ten():
    assert grade()['score']==6
    result=grade(score=10)
    assert result['status']=='unverified' and result['score'] is None
    assert result['proposed_score']==10
    assert any('明细之和不一致' in error for error in result['evidence_issues'])

@pytest.mark.parametrize('change', ['missing','duplicate','foreign','invented_quote','no_gap','quarter_point','bool'])
def test_bad_check_ledgers_never_enter_the_total(change):
    p=payload();note=p['dimension_notes']['accuracy']
    if change=='missing':note.pop('checks')
    elif change=='duplicate':note['checks'][1]['id']='a'
    elif change=='foreign':note['checks'][1]['id']='unknown'
    elif change=='invented_quote':note['checks'][0]['basis']='实际没有演示'
    elif change=='no_gap':note['checks'][0]['gap']=''
    elif change=='quarter_point':note['checks'][0]['score']=3.25
    else:note['checks'][0]['score']=True
    r=grade(p)
    assert r['status']=='unverified' and r['score'] is None
    assert r['dimensions'][0]['score']==6

def test_exact_maximum_is_allowed_and_quote_match_is_not_truth_validation():
    p=payload()
    for check in p['dimension_notes']['accuracy']['checks']:
        check.update(score=5,gap='')
    assert grade(p,10)['score']==10
    old=copy.deepcopy(CFG);old.pop('rubric_version')
    p['dimension_notes']['accuracy'].pop('checks')
    assert grade(p,10,old)['score']==10  # Existing saved rule snapshots keep their semantics.

def test_invalid_config_cannot_disable_anchor_validation():
    c=copy.deepcopy(CFG);c['dimensions'][0]['checks'][1]['id']='a'
    assert group_config('<review-group-config>'+json.dumps(c)+'</review-group-config>') is None

def test_complete_json_without_end_tags_is_not_confused_with_truncated_data():
    raw='<review-comments>'+json.dumps(payload())+'\n<review-score>'+json.dumps({'scores':{'accuracy':6}})+'\nCONSENSUS_SCORE: 4'
    normalized=normalize_review_blocks(raw)
    assert '</review-comments>' in normalized and '</review-score>' in normalized
    _,rating=consume_score(raw,CFG,DRAFT)
    assert rating['score']==6 and rating['format_normalized']
    incomplete='<review-score>{"scores":{"accuracy":6'
    assert normalize_review_blocks(incomplete)==incomplete
    assert consume_score(incomplete,CFG,DRAFT)[1]['score'] is None
    ambiguous='<review-score>{"scores":{"accuracy":6}} unexpected text'
    assert normalize_review_blocks(ambiguous)==ambiguous

@pytest.mark.asyncio
async def test_json_in_manuscript_reaches_reviewers_and_chair_without_rewriting(monkeypatch):
    from backend import advisors
    from backend.personas import Persona
    from backend.settings import Settings
    draft='请看这个JSON：{"model":"例子","input":{"count":2}}，不要改变原文。'
    people=[Persona(id=pid,name=pid,role='阅读',description='阅读',system_prompt='审稿',avatar_emoji='📝',color='#111111') for pid in ['a','b']]
    seen=[]
    async def query(pid,prompt,*args,**kwargs):
        seen.append(prompt)
        return pid,'custom:fixture','示例原文可读。\nCONSENSUS_SCORE: 3',None,None,{}
    async def neutral(model,prompt,**kwargs):
        seen.append(prompt)
        return {'content':'原文已保留','error':None}
    monkeypatch.setattr(advisors,'get_settings',lambda:Settings(advisor_default_model='custom:fixture',advisor_chair_persona_id=''))
    monkeypatch.setattr(advisors,'get_personas_by_ids',lambda ids:people)
    monkeypatch.setattr(advisors,'_query_advisor',query)
    monkeypatch.setattr(advisors,'_query_neutral',neutral)
    events=[event async for event in advisors.run_debate(draft,['a','b'],default_model='custom:fixture',max_rounds=1,round_policy='fixed')]
    assert any(event['type']=='advisor_complete' for event in events)
    assert len(seen)==3 and all(draft in prompt for prompt in seen)
