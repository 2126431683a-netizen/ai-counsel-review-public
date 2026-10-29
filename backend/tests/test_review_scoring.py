"""Ratings use configured weights and validated final-round dimensions, not prose."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.review_scoring import group_config, consume_score, build_score_report, score_markdown


@pytest.fixture
def groups():
    return json.loads((Path(__file__).resolve().parents[2] / 'desktop/review_groups.json').read_text(encoding='utf-8'))['groups']


def persona(cfg):
    return SimpleNamespace(id=cfg['id'], system_prompt='<review-group-config>' + json.dumps(cfg) + '</review-group-config>')


def rated(cfg, value):
    payload = {'scores': {d['id']: value for d in cfg['dimensions']}, 'unrated_reasons': {}}
    return consume_score('这步我能跟上。\n<review-score>' + json.dumps(payload) + '</review-score>', cfg)


def test_exact_two_level_weights_and_machine_payload_hidden(groups):
    scores = [8, 9, 6, 7, 5]
    responses = []
    for cfg, value in zip(groups, scores):
        text, rating = rated(cfg, value)
        assert '<review-score>' not in text
        assert rating['score'] == value
        responses.append({'persona_id': cfg['id'], 'review_rating': rating})
    report = build_score_report([persona(c) for c in groups], responses)
    # 8*.25 + 9*.30 + 6*.15 + 7*.10 + 5*.20 = 7.30
    assert report['score'] == 7.3 and report['complete']
    assert '7.3/10' in score_markdown(report)


def test_dimension_weighting_not_simple_mean(groups):
    cfg = groups[0]
    _, rating = consume_score('<review-score>' + json.dumps({'scores': {'accuracy': 10, 'evidence': 5, 'scope': 0}}) + '</review-score>', cfg)
    assert rating['score'] == 6.3  # 10*.45 + 5*.35 = 6.25, half-up rounding
    assert rating['raw_score'] == '6.25'


@pytest.mark.parametrize('bad', [True, -1, 11, '8', float('nan'), float('inf')])
def test_invalid_score_never_becomes_a_rating(groups, bad):
    cfg = groups[0]
    _, rating = rated(cfg, bad)
    assert rating['status'] == 'invalid' and rating['score'] is None


def test_na_requires_reason_and_only_normalizes_inside_team(groups):
    cfg = groups[0]
    scores = {'accuracy': 8, 'evidence': None, 'scope': 6}
    raw = {'scores': scores, 'unrated_reasons': {'evidence': '未提供对照数据'}}
    _, rating = consume_score('<review-score>' + json.dumps(raw) + '</review-score>', cfg)
    assert rating['status'] == 'ok' and rating['coverage'] == 65
    assert rating['score'] == 7.4
    raw['unrated_reasons'] = {}
    _, invalid = consume_score('<review-score>' + json.dumps(raw) + '</review-score>', cfg)
    assert invalid['status'] == 'invalid'
    raw = {'scores': {'accuracy': None, 'evidence': 8, 'scope': 6}, 'unrated_reasons': {'accuracy': '外部事实资料不足'}}
    _, unrated = consume_score('<review-score>' + json.dumps(raw) + '</review-score>', cfg)
    assert unrated['status'] == 'unrated' and unrated['coverage'] == 55


@pytest.mark.parametrize('raw', ['', '<review-score>{bad}</review-score>', '<review-score>{', '<review-score>{}</review-score><review-score>{}</review-score>'])
def test_missing_or_duplicate_payload_is_not_inferred_from_prose(groups, raw):
    text, rating = consume_score('本团9分，CONSENSUS_SCORE: 5\n' + raw, groups[0])
    assert rating['status'] == 'invalid'
    assert '<review-score>' not in text


def test_missing_group_does_not_reweight_other_groups(groups):
    responses = [{'persona_id': c['id'], 'review_rating': rated(c, 8)[1]} for c in groups[:-1]]
    report = build_score_report([persona(c) for c in groups], responses)
    assert not report['complete'] and report['score'] is None
    assert report['available_weight'] == 80
    assert '总分暂缺' in score_markdown(report)


def test_subset_and_invalid_config_do_not_silently_make_full_panel(groups):
    ps = [persona(c) for c in groups[:-1]]
    report = build_score_report(ps, [{'persona_id': c['id'], 'review_rating': rated(c, 8)[1]} for c in groups[:-1]])
    assert not report['complete']
    bad = dict(groups[0], dimensions=[{'id': 'a', 'name': '坏配置', 'weight': 50}])
    assert group_config(persona(bad).system_prompt) is None
    assert build_score_report([SimpleNamespace(id='generic', system_prompt='普通角色')], []) is None


def test_model_cannot_override_group_weight(groups):
    cfg = groups[0]
    raw = {'scores': {d['id']: 8 for d in cfg['dimensions']}, 'weight': 100, 'total': 10}
    _, rating = consume_score('<review-score>' + json.dumps(raw) + '</review-score>', cfg)
    responses = [{'persona_id': g['id'], 'review_rating': rating if g is cfg else rated(g, 8)[1]} for g in groups]
    report = build_score_report([persona(c) for c in groups], responses)
    assert report['groups'][0]['weight'] == 25 and report['score'] == 8


@pytest.mark.asyncio
async def test_debate_scores_final_round_and_chair_gets_program_table(monkeypatch):
    from backend import advisors
    from backend.personas import Persona
    from backend.settings import Settings
    root = Path(__file__).resolve().parents[2]
    bundle = json.loads((root / 'desktop/role_bundle.json').read_text(encoding='utf-8'))
    ps = {pid: Persona(id=pid, is_custom=True, **value) for pid, value in bundle['personas'].items()}
    settings = Settings(**bundle['settings'])
    seen = {}
    chair_calls = []

    async def query(model, messages, **kwargs):
        cfg = group_config(messages[0]['content']) if messages[0]['role'] == 'system' else None
        if cfg:
            n = seen.get(cfg['id'], 0) + 1
            seen[cfg['id']] = n
            raw = {'scores': {d['id']: 4 if n == 1 else 8 for d in cfg['dimensions']}, 'unrated_reasons': {}}
            notes = {'dimension_notes': {d['id']:{'basis':'合成测试稿','rationale':'测试评分数据保留可核对依据','deduction':'用作多轮计算反例的主观保留'} for d in cfg['dimensions']}, 'comments':[]}
            if cfg.get('rubric_version') == 2:
                for d in cfg['dimensions']:
                    notes['dimension_notes'][d['id']]['checks'] = [{'id':c['id'],'score':2 if n==1 else 4,'basis':'合成测试稿','rationale':'多轮检查保留已确认的内容','gap':'完整验证需进一步确认具体结果'} for c in d['checks']]
            return {'content': '这一步讲清楚了。\n<review-comments>'+json.dumps(notes)+'</review-comments>\n<review-score>' + json.dumps(raw) + '</review-score>\nCONSENSUS_SCORE: ' + ('2' if n == 1 else '4'), 'error': False}
        if messages[0]['role'] == 'system':
            chair_calls.append(messages)
        return {'content': '先保留有效案例，待拍画面在交付前确认。', 'error': False}

    monkeypatch.setattr(advisors, 'get_settings', lambda: settings)
    monkeypatch.setattr(advisors, 'get_persona', lambda pid: ps.get(pid))
    monkeypatch.setattr(advisors, 'get_personas_by_ids', lambda ids: [ps[x] for x in ids])
    monkeypatch.setattr(advisors, 'query_model', query)
    ids = [pid for pid in ps if pid != 'source-editor']
    events = [e async for e in advisors.run_debate('合成测试稿，不是用户原稿', ids, default_model='custom:fixture', max_rounds=3)]
    result = next(e['data'] for e in events if e['type'] == 'advisor_complete')
    assert len(result['rounds']) == 2
    assert result['verdict']['review_score_report']['score'] == 8
    assert '8.0/10' in result['verdict']['content']
    assert '4.0/10' not in result['verdict']['content']
    assert len(chair_calls) == 1 and '程序计算的稿面评分' in chair_calls[0][-1]['content']
    assert all('<review-score>' not in r['content'] for rd in result['rounds'] for r in rd['responses'])
