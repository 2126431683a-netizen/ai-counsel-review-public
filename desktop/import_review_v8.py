"""Apply only five scoring-calibrated prompts; snapshot protected data hashes."""
import hashlib
import json
from pathlib import Path
import re
import time
import httpx

root=Path(__file__).resolve().parent.parent
bundle=json.loads((root/'desktop/role_bundle.json').read_text(encoding='utf-8'))
base=json.loads((root/'desktop/role_bundle.v7.json').read_text(encoding='utf-8'))
assert bundle['version']==8
hashval=lambda v:hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
with httpx.Client(base_url='http://127.0.0.1:3340',trust_env=False,timeout=30) as client:
    settings=client.get('/api/settings').raise_for_status().json()
    people=client.get('/api/personas').raise_for_status().json()
    history=client.get('/api/conversations').raise_for_status().json()
    assert not any(client.get('/api/conversations/'+x['id']+'/progress').raise_for_status().json().get('active') for x in history),'Active review: defer service reload'
    mapped=[]
    for pid,role in bundle['personas'].items():
        if pid=='source-editor':continue
        matches=[p for p in people if p.get('is_custom') and p['name']==role['name']]
        assert len(matches)==1
        p=matches[0]
        assert p['system_prompt']==base['personas'][pid]['system_prompt'],'User role changed: reconcile before applying'
        pattern=r'<review-group-config>(.*?)</review-group-config>'
        assert re.findall(pattern,p['system_prompt'])==re.findall(pattern,role['system_prompt'])
        mapped.append((p,role['system_prompt']))
    backup=root/'build/role-backups'/('reliability-v8-'+str(time.time_ns()))
    backup.mkdir(parents=True)
    (backup/'personas.json').write_text(json.dumps(people,ensure_ascii=False,indent=2),encoding='utf-8')
    history_hashes={x['id']:hashval(client.get('/api/conversations/'+x['id']).raise_for_status().json()) for x in history}
    expected={p['id']:dict(p) for p in people}
    for p,prompt in mapped:
        expected[p['id']]['system_prompt']=prompt
        updated=client.patch('/api/personas/'+p['id'],json={'system_prompt':prompt}).raise_for_status().json()
        assert expected[p['id']]==updated
    after=client.get('/api/settings').raise_for_status().json()
    assert settings==after
    final_people=client.get('/api/personas').raise_for_status().json()
    assert all(expected[p['id']]==p for p in final_people)
    report={'version':8,'promptsUpdated':5,'settingsUnchanged':True,'otherPersonaFieldsUnchanged':True,
            'historyHashes':history_hashes,'historyCount':len(history),'settingsHash':hashval(after),
            'personasHash':hashval(final_people),'backup':str(backup)}
    (root/'build/imported-reliability-v8.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['backup','historyHashes','settingsHash','personasHash']},ensure_ascii=False))
