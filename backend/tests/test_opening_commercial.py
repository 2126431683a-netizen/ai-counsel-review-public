import copy
import json
from pathlib import Path
import pytest
from backend.review_scoring import group_config, consume_score, build_score_report

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))

def cfg():
    return group_config(BUNDLE['personas']['source-tech']['system_prompt'])

def rate(config, commercial, opening=8, content=8):
    scores={d['id']: commercial if d['id']=='commercial' else opening if d['id']=='opening' else content for d in config['dimensions']}
    return consume_score('<review-score>'+json.dumps({'scores':scores,'unrated_reasons':{'commercial':'不适用：未见推广依据'}})+'</review-score>',config)[1]

def test_integration_changes_actual_weighted_score_without_changing_team_weight():
    c=cfg()
    assert c['weight']==25
    assert rate(c,2)['score']==6.5
    assert rate(c,9)['score']==8.3
    assert rate(c,2,opening=2)['score']==5.6

def test_no_commercial_does_not_receive_free_full_marks():
    c=cfg()
    assert rate(c,None,opening=4)['score']==7.2  # 80% content + 20% opening.
    assert rate(c,10,opening=4)['score']==7.9
    assert rate(c,None,opening=4)['coverage']==75

@pytest.mark.parametrize('axis',['accuracy','evidence','scope','opening'])
def test_missing_required_axis_cannot_be_reweighted_away(axis):
    c=cfg();values={d['id']:8 for d in c['dimensions']};values[axis]=None
    _,result=consume_score('<review-score>'+json.dumps({'scores':values,'unrated_reasons':{axis:'未知'}})+'</review-score>',c)
    assert result['status']=='invalid' and result['score'] is None

def test_policy_weights_are_configuration_not_model_output():
    c=cfg();c['dimensions'][-1]['weight']=24;c['dimensions'][0]['weight']+=1
    assert group_config('<review-group-config>'+json.dumps(c)+'</review-group-config>') is None

def test_new_axes_require_evidence_and_anchor_sums():
    c=cfg();values={d['id']:8 for d in c['dimensions']}
    notes={d['id']:{'basis':'明确开场情境','rationale':'具体解释','deduction':'仍有重复','checks':[{'id':key,'score':4,'basis':'明确开场情境','rationale':'有具体解释','gap':'仍有重复'} for key in ['a','b']]} for d in c['dimensions']}
    def result():
        text='<review-comments>'+json.dumps({'dimension_notes':notes})+'</review-comments><review-score>'+json.dumps({'scores':values})+'</review-score>'
        return consume_score(text,c,'明确开场情境。')[1]
    assert result()['status']=='ok'
    notes['opening']['checks'][0]['basis']='臆想的开场'
    assert result()['status']=='unverified'

def test_legacy_v10_snapshots_keep_original_three_dimension_math():
    b=json.loads((ROOT/'desktop/role_bundle.v10.json').read_text(encoding='utf-8'))
    c=group_config(b['personas']['source-tech']['system_prompt'])
    assert len(c['dimensions'])==3 and rate(c,None)['score']==8

def test_all_five_groups_keep_weights_and_have_v11_schema_examples():
    from types import SimpleNamespace
    people=[];responses=[]
    for pid,role in BUNDLE['personas'].items():
        if pid=='source-editor':continue
        c=group_config(role['system_prompt']);assert c and len(c['dimensions'])==5
        assert sum(d['weight'] for d in c['dimensions'][:3])==60
        example=role['system_prompt'].split('<review-score>')[-1].split('</review-score>')[0]
        assert set(json.loads(example)['scores'])=={d['id'] for d in c['dimensions']}
        people.append(SimpleNamespace(id=pid,system_prompt=role['system_prompt']))
        responses.append({'persona_id':pid,'review_rating':rate(c,2)})
    report=build_score_report(people,responses)
    assert report['complete'] and report['score']==6.5
