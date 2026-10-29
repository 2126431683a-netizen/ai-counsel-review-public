"""Apply the six v9 prompts only; preserve settings, role identities and history."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import sys
import httpx

ROOT = Path(__file__).resolve().parent.parent
bundle = json.loads((ROOT / 'desktop/role_bundle.json').read_text(encoding='utf-8'))
base = json.loads((ROOT / 'desktop/role_bundle.v8.json').read_text(encoding='utf-8'))
assert bundle['version'] == 9
legacy_file = ROOT / 'desktop/role_bundle.v9-legacy-headings.json'
legacy = json.loads(legacy_file.read_text(encoding='utf-8')) if legacy_file.exists() else None
digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
credential = Path(os.environ['LOCALAPPDATA']) / 'AICounselReview/credentials.json'
credential_hash = hashlib.sha256(credential.read_bytes()).hexdigest()
with httpx.Client(base_url='http://127.0.0.1:3340', trust_env=False, timeout=30) as client:
    settings = client.get('/api/settings').raise_for_status().json()
    people = client.get('/api/personas').raise_for_status().json()
    history = client.get('/api/conversations').raise_for_status().json()
    active = {}
    for item in history:
        progress = client.get('/api/conversations/' + item['id'] + '/progress').raise_for_status().json()
        if progress.get('active'):
            # run_debate captures independent Persona models (including chair)
            # before its first await. PATCH changes future runs, not those models.
            active[item['id']] = progress.get('personas') or []
    mapped = []
    for pid, role in bundle['personas'].items():
        matches = [p for p in people if p.get('is_custom') and p['name'] == role['name']]
        assert len(matches) == 1, 'Ambiguous role mapping'
        person = matches[0]
        allowed = [base['personas'][pid]['system_prompt'], role['system_prompt']]
        # The initial title alignment left a space before this inherited colon.
        allowed.append(role['system_prompt'].replace('# 审稿团：', '# 审稿团 ：'))
        if legacy:
            allowed.append(legacy['personas'][pid]['system_prompt'])
        assert person['system_prompt'] in allowed, 'Preserve user-edited prompt; reconcile before applying'
        pattern = r'<review-group-config>(.*?)</review-group-config>'
        assert re.findall(pattern, person['system_prompt'], re.S) == re.findall(pattern, role['system_prompt'], re.S)
        mapped.append((person, role['system_prompt']))
    backup = ROOT / 'build/role-backups' / ('logic-v9-' + str(time.time_ns()))
    backup.mkdir(parents=True)
    (backup / 'personas.json').write_text(json.dumps(people, ensure_ascii=False, indent=2), encoding='utf-8')
    history_hashes = {x['id']: digest(client.get('/api/conversations/' + x['id']).raise_for_status().json()) for x in history if x['id'] not in active}
    expected = {p['id']: dict(p) for p in people}
    changed = 0
    for person, prompt in mapped:
        expected[person['id']]['system_prompt'] = prompt
        if person['system_prompt'] != prompt:
            updated = client.patch('/api/personas/' + person['id'], json={'system_prompt': prompt}).raise_for_status().json()
            assert expected[person['id']] == updated
            changed += 1
    after = client.get('/api/settings').raise_for_status().json()
    assert settings == after
    final_people = client.get('/api/personas').raise_for_status().json()
    assert len(final_people) == len(expected) and all(expected[p['id']] == p for p in final_people)
    assert hashlib.sha256(credential.read_bytes()).hexdigest() == credential_hash
    assert all(digest(client.get('/api/conversations/' + cid).raise_for_status().json()) == value for cid, value in history_hashes.items())
    active_snapshots_checked = 0
    for cid, snapshot in active.items():
        progress = client.get('/api/conversations/' + cid + '/progress').raise_for_status().json()
        if progress.get('active'):
            assert progress.get('personas') == snapshot
            active_snapshots_checked += 1
    final_ids = {item['id'] for item in client.get('/api/conversations').raise_for_status().json()}
    assert all(item['id'] in final_ids for item in history)
    report = {'version': 9, 'promptsUpdated': changed, 'settingsAndPresetUnchanged': True,
              'otherPersonaFieldsUnchanged': True, 'credentialsUnchanged': True,
              'inactiveHistoryContentsUnchanged': True, 'historyCount': len(history),
              'activeRunsAtInstall': len(active), 'activeSnapshotsChecked': active_snapshots_checked,
              'historyHashes': history_hashes, 'settingsHash': digest(after),
              'personasHash': digest(final_people), 'backup': str(backup),
              'privateDraftResubmitted': False, 'restartRequired': False}
    report_name = 'imported-logic-v9-headings.json' if '--align-headings' in sys.argv else 'imported-logic-v9.json'
    (ROOT / 'build' / report_name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['historyHashes','settingsHash','personasHash','backup']}, ensure_ascii=False))
