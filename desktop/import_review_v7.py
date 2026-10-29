"""Apply only five viewer prompts, two round templates and reviewer temperature."""
import hashlib
import json
from pathlib import Path
import re
import time
import httpx

ROOT=Path(__file__).resolve().parent.parent
bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
baseline=json.loads((ROOT/'build/voice-v7-before.json').read_text(encoding='utf-8'))
assert bundle['version']==7
keys=['advisor_round1_prompt','advisor_followup_prompt','advisor_temperature']
digest=lambda value:hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
with httpx.Client(base_url='http://127.0.0.1:3340',trust_env=False,timeout=30) as client:
    settings=client.get('/api/settings').raise_for_status().json()
    personas=client.get('/api/personas').raise_for_status().json()
    history=client.get('/api/conversations').raise_for_status().json()
    assert all(settings[k]==baseline['settings'][k] for k in keys),'Settings changed during evaluation; reconcile first'
    mapped=[]
    for pid,fields in bundle['personas'].items():
        matches=[p for p in personas if p.get('is_custom') and p['name']==fields['name']]
        assert len(matches)==1,'Role mapping must be unambiguous'
        original=matches[0]
        old=re.findall(r'<review-group-config>(.*?)</review-group-config>',original['system_prompt'])
        new=re.findall(r'<review-group-config>(.*?)</review-group-config>',fields['system_prompt'])
        assert [json.loads(x) for x in old]==[json.loads(x) for x in new],'Preserve scoring policy'
        if pid!='source-editor':
            initial=next(x for x in baseline['personas'] if x['id']==original['id'])
            assert initial['system_prompt']==original['system_prompt'],'Role edited during evaluation; reconcile first'
            mapped.append((original,fields['system_prompt']))
    backup=ROOT/'build/role-backups'/('viewer-v7-'+str(time.time_ns()))
    backup.mkdir(parents=True)
    (backup/'personas.json').write_text(json.dumps(personas,ensure_ascii=False,indent=2),encoding='utf-8')
    (backup/'settings-allowed-fields.json').write_text(json.dumps({k:settings[k] for k in keys},ensure_ascii=False,indent=2),encoding='utf-8')
    protected=digest({k:v for k,v in settings.items() if k not in keys})
    for original,prompt in mapped:
        result=client.patch('/api/personas/'+original['id'],json={'system_prompt':prompt}).raise_for_status().json()
        assert result['system_prompt']==prompt
        assert {k:v for k,v in original.items() if k!='system_prompt'}=={k:v for k,v in result.items() if k!='system_prompt'}
    client.put('/api/settings',json={k:bundle['settings'][k] for k in keys}).raise_for_status()
    after=client.get('/api/settings').raise_for_status().json()
    assert all(after[k]==bundle['settings'][k] for k in keys)
    assert protected==digest({k:v for k,v in after.items() if k not in keys})
    expected={x['id']:{**x,**({'system_prompt':p} if (p:=next((prompt for original,prompt in mapped if original['id']==x['id']),None)) else {})} for x in personas}
    actual={x['id']:x for x in client.get('/api/personas').raise_for_status().json()}
    assert all(actual[k]==v for k,v in expected.items()),'Protected persona fields changed'
    latest=client.get('/api/conversations').raise_for_status().json()
    assert {x['id'] for x in history}<={x['id'] for x in latest}
    report={'version':7,'reviewerPromptsUpdated':len(mapped),'roundTemplatesUpdated':2,
        'reviewerTemperatureBefore':settings['advisor_temperature'],'reviewerTemperatureAfter':after['advisor_temperature'],
        'chairAndOtherPersonaFieldsUnchanged':True,'otherSettingsUnchanged':True,
        'historyIdsPreserved':True,'historyCount':len(latest),'backup':str(backup),'serverRestarted':False}
    (ROOT/'build/imported-viewer-v7.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='backup'},ensure_ascii=False))
