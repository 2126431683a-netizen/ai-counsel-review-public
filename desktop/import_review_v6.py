"""Update only authorized reviewer prompts, retaining model/credential/history data."""
import hashlib
import json
import re
from pathlib import Path
import time
import httpx

root=Path(__file__).resolve().parent.parent
bundle=json.loads((root/'desktop/role_bundle.json').read_text(encoding='utf-8'))
assert bundle['version']==6
prompt_keys=['advisor_round1_prompt','advisor_followup_prompt','advisor_cross_pollination_prompt','advisor_verdict_prompt','advisor_tiebreaker_prompt']
digest=lambda value:hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
with httpx.Client(base_url='http://127.0.0.1:3340',trust_env=False,timeout=30) as client:
    settings=client.get('/api/settings').raise_for_status().json()
    personas=client.get('/api/personas').raise_for_status().json()
    history=client.get('/api/conversations').raise_for_status().json()
    backup=root/'build/role-backups'/('discussion-v6-'+str(time.time_ns()))
    backup.mkdir(parents=True)
    (backup/'personas.json').write_text(json.dumps(personas,ensure_ascii=False,indent=2),encoding='utf-8')
    (backup/'workflow-prompts.json').write_text(json.dumps({k:settings.get(k) for k in prompt_keys},ensure_ascii=False,indent=2),encoding='utf-8')
    protected_settings=digest({k:v for k,v in settings.items() if k not in prompt_keys})
    # Fail before any writes if a user has changed a scoring policy since v5.
    for fields in bundle['personas'].values():
        matches=[p for p in personas if p.get('is_custom') and p['name']==fields['name']]
        assert len(matches)==1,'Ambiguous role mapping'
        old=re.findall(r'<review-group-config>(.*?)</review-group-config>',matches[0]['system_prompt'])
        new=re.findall(r'<review-group-config>(.*?)</review-group-config>',fields['system_prompt'])
        assert [json.loads(x) for x in old]==[json.loads(x) for x in new],'Scoring policy changed: preserve it before import'
    saved_prompts={}
    for fields in bundle['personas'].values():
        matches=[p for p in personas if p.get('is_custom') and p['name']==fields['name']]
        assert len(matches)==1,'Ambiguous role mapping; no new role creation authorized.'
        original=matches[0]
        result=client.patch('/api/personas/'+original['id'],json={'system_prompt':fields['system_prompt']}).raise_for_status().json()
        assert result['system_prompt']==fields['system_prompt']
        assert {k:v for k,v in original.items() if k!='system_prompt'}=={k:v for k,v in result.items() if k!='system_prompt'}
        saved_prompts[original['id']]=digest(result['system_prompt'])
    client.put('/api/settings',json={k:bundle['settings'][k] for k in prompt_keys}).raise_for_status()
    after=client.get('/api/settings').raise_for_status().json()
    assert all(after[k]==bundle['settings'][k] for k in prompt_keys)
    assert protected_settings==digest({k:v for k,v in after.items() if k not in prompt_keys})
    latest=client.get('/api/conversations').raise_for_status().json()
    assert {x['id'] for x in history}<={x['id'] for x in latest}
    report={'version':6,'rolesUpdated':len(saved_prompts),'workflowTemplatesUpdated':5,'protectedSettingsUnchanged':True,'avatarsAndRoleFieldsUnchanged':True,'historyIdsPreserved':True,'historyCount':len(latest),'promptHashes':saved_prompts,'backup':str(backup),'usesModel':False}
    (root/'build/imported-discussion-v6.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['backup','promptHashes']},ensure_ascii=False))
