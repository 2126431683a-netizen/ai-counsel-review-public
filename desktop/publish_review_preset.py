"""Publish the installed v8 panel as a selectable preset, without touching prompts."""
import hashlib
import json
from pathlib import Path
import time
import httpx

ROOT=Path(__file__).resolve().parent.parent
bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
assert bundle['version']==8
digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
with httpx.Client(base_url='http://127.0.0.1:3340',trust_env=False,timeout=30) as client:
    settings=client.get('/api/settings').raise_for_status().json()
    personas=client.get('/api/personas').raise_for_status().json()
    history=client.get('/api/conversations').raise_for_status().json()
    panel=[]
    for pid,role in bundle['personas'].items():
        matches=[p for p in personas if p.get('is_custom') and p['name']==role['name']]
        assert len(matches)==1,'Role mapping is ambiguous'
        person=matches[0]
        assert person['system_prompt']==role['system_prompt'],'Install current role rules before publishing preset'
        if pid=='source-editor':
            assert settings['advisor_chair_persona_id']==person['id'],'Preserve the selected chair; reconcile first'
        else:
            panel.append(person['id'])
    assert len(panel)==5
    old=settings.get('advisor_presets') or []
    backup=ROOT/'build/role-backups'/('preset-v8-'+str(time.time_ns()))
    backup.mkdir(parents=True)
    (backup/'advisor-presets.json').write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
    history_hashes={item['id']:digest(client.get('/api/conversations/'+item['id']).raise_for_status().json()) for item in history}
    preset_id='source-review-v8'
    preset={'id':preset_id,'name':'源宝审稿团 v8（全文细读与评分核对）',
            'persona_ids':panel,'mode':'simple','default_model':'','tiebreaker_model':'',
            'model_assignments':None,'max_rounds':settings['advisor_default_rounds'],
            'search_provider':None,'is_default':True,'last_used_at':None}
    current=next((p for p in old if p['id']==preset_id),None)
    if current:
        preset['last_used_at']=current.get('last_used_at')
    updated=[{**p,'is_default':False} for p in old if p['id']!=preset_id]+[preset]
    client.put('/api/settings',json={'advisor_presets':updated}).raise_for_status()
    after=client.get('/api/settings').raise_for_status().json()
    assert {k:v for k,v in settings.items() if k!='advisor_presets'}=={k:v for k,v in after.items() if k!='advisor_presets'}
    assert digest(client.get('/api/personas').raise_for_status().json())==digest(personas)
    published=next(p for p in after['advisor_presets'] if p['id']==preset_id)
    assert published['persona_ids']==panel and published['is_default']
    assert sum(bool(p.get('is_default')) for p in after['advisor_presets'])==1
    assert all(digest(client.get('/api/conversations/'+cid).raise_for_status().json())==value for cid,value in history_hashes.items())
    report={'preset':published,'presetCount':len(after['advisor_presets']),'otherSettingsUnchanged':True,
            'rolesUnchanged':True,'historyContentsUnchanged':True,'historyCount':len(history),
            'modelInheritedFromCurrentSettings':True,'settingsHashAfter':digest(after),
            'personasHash':digest(personas),'historyHashes':history_hashes,'backup':str(backup)}
    (ROOT/'build/published-review-preset-v8.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['backup','historyHashes','personasHash','settingsHashAfter']},ensure_ascii=False))
