"""Keep the current six manuscript roles; back up before authorized removal."""
import json
from pathlib import Path
import time
import httpx

ROOT = Path(__file__).resolve().parent.parent
bundle = json.loads((ROOT / 'desktop/role_bundle.json').read_text(encoding='utf-8'))
names = {p['name'] for p in bundle['personas'].values()}
with httpx.Client(base_url='http://127.0.0.1:3340', trust_env=False, timeout=25) as client:
    roles = client.get('/api/personas').raise_for_status().json()
    settings = client.get('/api/settings').raise_for_status().json()
    keep = {p['id'] for p in roles if p['name'] in names and p['is_custom']}
    assert len(keep) == 6, 'Expected five manuscript groups and the chair before cleanup'
    backup = ROOT / 'build/role-backups' / ('review-only-' + str(time.time_ns()))
    backup.mkdir(parents=True)
    (backup / 'personas.json').write_text(json.dumps(roles, ensure_ascii=False, indent=2), encoding='utf-8')
    (backup / 'advisor-settings.json').write_text(json.dumps({k:v for k,v in settings.items() if k.startswith('advisor_')}, ensure_ascii=False, indent=2), encoding='utf-8')
    removed = []
    for role in roles:
        if role['is_custom'] and role['id'] not in keep:
            client.delete('/api/personas/' + role['id']).raise_for_status()
            removed.append(role['name'])
    # Drop presets for removed personas, preserving all complete review presets.
    latest = client.get('/api/settings').raise_for_status().json()
    presets = [p for p in latest['advisor_presets'] if p.get('persona_ids') and set(p['persona_ids']) <= keep]
    assert presets and any(p.get('is_default') for p in presets)
    client.put('/api/settings', json={'advisor_presets':presets}).raise_for_status()
    print(json.dumps({'retainedCustomRoles':len(keep), 'removedCustomRoles':removed, 'presets':len(presets), 'historyUntouched':True}, ensure_ascii=False))
