"""Install anchored prompts and four stage templates; preserve the user's API/data."""
import hashlib
import json
import os
from pathlib import Path
import time
import httpx
from sys import path

ROOT=Path(__file__).resolve().parent.parent
path.insert(0,str(ROOT))
from backend.review_scoring import group_config

bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
base=json.loads((ROOT/'desktop/role_bundle.v10.json').read_text(encoding='utf-8'))
first=json.loads((ROOT/'desktop/role_bundle.v11-first.json').read_text(encoding='utf-8')) if (ROOT/'desktop/role_bundle.v11-first.json').exists() else base
assert bundle['version']==11
keys=['advisor_round1_prompt','advisor_followup_prompt','advisor_cross_pollination_prompt','advisor_verdict_prompt']
digest=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
credential=Path(os.environ['LOCALAPPDATA'])/'AICounselReview/credentials.json'
cred_hash=hashlib.sha256(credential.read_bytes()).hexdigest()
with httpx.Client(base_url='http://127.0.0.1:3340',trust_env=False,timeout=30) as client:
    assert client.get('/api/health').raise_for_status().json().get('features',{}).get('review_opening_commercial')==1,'Load the compatible server while idle before installing v10'
    settings=client.get('/api/settings').raise_for_status().json()
    people=client.get('/api/personas').raise_for_status().json()
    history=client.get('/api/conversations').raise_for_status().json()
    active={}
    for item in history:
        progress=client.get('/api/conversations/'+item['id']+'/progress').raise_for_status().json()
        if progress.get('active'):active[item['id']]=progress.get('personas') or []
    mapped=[]
    for pid,role in bundle['personas'].items():
        matches=[p for p in people if p.get('is_custom') and p['name']==role['name']]
        assert len(matches)==1,'Ambiguous role mapping'
        p=matches[0]
        assert p['system_prompt'] in [base['personas'][pid]['system_prompt'],first['personas'][pid]['system_prompt'],role['system_prompt']],'Preserve edited prompt; reconcile first'
        old_cfg=group_config(base['personas'][pid]['system_prompt']);new_cfg=group_config(role['system_prompt'])
        if old_cfg:
            assert new_cfg and new_cfg['rubric_version']==2
            assert {k:old_cfg[k] for k in ['id','name','weight']}=={k:new_cfg[k] for k in ['id','name','weight']}
            assert [{k:d[k] for k in ['id','name']} for d in old_cfg['dimensions']]==[{k:d[k] for k in ['id','name']} for d in new_cfg['dimensions'][:3]] and all(abs(n['weight']-o['weight']*.6)<1e-8 for o,n in zip(old_cfg['dimensions'],new_cfg['dimensions'][:3]))
        mapped.append((p,role['system_prompt']))
    for key in keys:
        assert settings[key] in [base['settings'][key],bundle['settings'][key]],'Preserve custom stage template: '+key
    presets=json.loads(json.dumps(settings.get('advisor_presets') or []))
    preset=next((p for p in presets if p['id']=='source-review-v8'),None)
    assert preset and preset['name'] in ['源宝审稿团 v10（真实受众与锚点评分）','源宝审稿团 v11（开头与商业融合）']
    preset['name']='源宝审稿团 v11（开头与商业融合）'
    backup=ROOT/'build/role-backups'/('opening-v11-'+str(time.time_ns()));backup.mkdir(parents=True)
    (backup/'personas.json').write_text(json.dumps(people,ensure_ascii=False,indent=2),encoding='utf-8')
    (backup/'review-settings.json').write_text(json.dumps({**{k:settings[k] for k in keys},'advisor_presets':settings['advisor_presets']},ensure_ascii=False,indent=2),encoding='utf-8')
    hashes={p['id']:digest(client.get('/api/conversations/'+p['id']).raise_for_status().json()) for p in history if p['id'] not in active}
    expected={p['id']:dict(p) for p in people}
    changed=0
    for p,prompt in mapped:
        expected[p['id']]['system_prompt']=prompt
        if prompt!=p['system_prompt']:
            assert client.patch('/api/personas/'+p['id'],json={'system_prompt':prompt}).raise_for_status().json()==expected[p['id']]
            changed+=1
    client.put('/api/settings',json={**{k:bundle['settings'][k] for k in keys},'advisor_presets':presets}).raise_for_status()
    after=client.get('/api/settings').raise_for_status().json()
    allowed=set(keys+['advisor_presets'])
    assert {k:v for k,v in settings.items() if k not in allowed}=={k:v for k,v in after.items() if k not in allowed}
    final_people=client.get('/api/personas').raise_for_status().json()
    assert len(expected)==len(final_people) and all(expected[p['id']]==p for p in final_people)
    assert all(digest(client.get('/api/conversations/'+cid).raise_for_status().json())==value for cid,value in hashes.items())
    assert hashlib.sha256(credential.read_bytes()).hexdigest()==cred_hash
    checked=0
    for cid,people_snapshot in active.items():
        progress=client.get('/api/conversations/'+cid+'/progress').raise_for_status().json()
        if progress.get('active'):
            assert progress.get('personas')==people_snapshot;checked+=1
    report={'version':11,'promptsUpdated':changed,'stageTemplatesUpdated':keys,'onlyPresetNameChanged':True,
            'teamWeightsUnchanged':True,'contentOpeningCommercialWeights':[60,15,25],'otherPersonaFieldsUnchanged':True,'modelTemperatureApiAndOtherSettingsUnchanged':True,
            'credentialsUnchanged':True,'inactiveHistoryContentsUnchanged':True,'historyCount':len(history),
            'activeSnapshotsChecked':checked,'settingsHash':digest(after),'personasHash':digest(final_people),
            'historyHashes':hashes,'backup':str(backup),'privateDraftResubmitted':False}
    (ROOT/'build/imported-opening-v11.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['settingsHash','personasHash','historyHashes','backup']},ensure_ascii=False))
