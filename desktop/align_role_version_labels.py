"""Verify rule bodies, update only the installed preset label, and audit packaging."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import zipfile
import httpx

ROOT = Path(__file__).resolve().parent.parent
bundle = json.loads((ROOT / 'desktop/role_bundle.json').read_text(encoding='utf-8'))
old = json.loads((ROOT / 'desktop/role_bundle.v9-legacy-headings.json').read_text(encoding='utf-8'))
digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
body = lambda text: [line for line in text.splitlines() if line.strip() and not re.match(r'^#{1,6}\s', line)]
for pid, role in bundle['personas'].items():
    assert body(role['system_prompt']) == body(old['personas'][pid]['system_prompt']), 'Rule text changed'
    assert 'v9' in role['system_prompt'].splitlines()[0]
    assert not re.search(r'(?m)^#{1,6} .*\bv[1-8]\b', role['system_prompt'])
package = ROOT / 'dist/审稿说明与六角色-逻辑衔接v9.zip'
with zipfile.ZipFile(package) as archive:
    assert archive.testzip() is None
    assert json.loads(archive.read('角色配置.json')) == bundle
    for source in bundle['sources']:
        assert hashlib.sha256(archive.read(source['file'])).hexdigest() == source['sha256']
        assert hashlib.sha256((ROOT / 'desktop/role-guides-v9' / source['file']).read_bytes()).hexdigest() == source['sha256']
credential = Path(os.environ['LOCALAPPDATA']) / 'AICounselReview/credentials.json'
credential_hash = hashlib.sha256(credential.read_bytes()).hexdigest()
with httpx.Client(base_url='http://127.0.0.1:3340', trust_env=False, timeout=30) as client:
    people = client.get('/api/personas').raise_for_status().json()
    for pid, role in bundle['personas'].items():
        matches = [p for p in people if p.get('is_custom') and p['name'] == role['name']]
        assert len(matches) == 1 and matches[0]['system_prompt'] == role['system_prompt']
    settings = client.get('/api/settings').raise_for_status().json()
    presets = settings.get('advisor_presets') or []
    expected = json.loads(json.dumps(presets))
    preset = next((p for p in expected if p['id'] == 'source-review-v8'), None)
    assert preset and preset['name'] in ['源宝审稿团 v8（全文细读与评分核对）', '源宝审稿团 v9（全文逻辑与段落衔接）'], 'Preserve user custom labels'
    changed = preset['name'] != '源宝审稿团 v9（全文逻辑与段落衔接）'
    preset['name'] = '源宝审稿团 v9（全文逻辑与段落衔接）'
    backup = ROOT / 'build/role-backups' / ('v9-labels-' + str(time.time_ns()))
    backup.mkdir(parents=True)
    (backup / 'advisor-presets.json').write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding='utf-8')
    history = client.get('/api/conversations').raise_for_status().json()
    inactive = [p['id'] for p in history if not client.get('/api/conversations/' + p['id'] + '/progress').raise_for_status().json().get('active')]
    hashes = {cid: digest(client.get('/api/conversations/' + cid).raise_for_status().json()) for cid in inactive}
    if changed:
        client.put('/api/settings', json={'advisor_presets': expected}).raise_for_status()
    after = client.get('/api/settings').raise_for_status().json()
    assert after['advisor_presets'] == expected
    assert {k:v for k,v in settings.items() if k != 'advisor_presets'} == {k:v for k,v in after.items() if k != 'advisor_presets'}
    assert client.get('/api/personas').raise_for_status().json() == people
    assert all(digest(client.get('/api/conversations/' + cid).raise_for_status().json()) == value for cid, value in hashes.items())
    assert hashlib.sha256(credential.read_bytes()).hexdigest() == credential_hash
    report = {'version': 9, 'sixLiveHeadingsAligned': True, 'ruleParagraphsUnchanged': True,
              'legacyChapterVersionLabelsRemoved': True, 'presetNameChanged': changed,
              'presetIdsSelectionsModelsRoundsUnchanged': True, 'otherSettingsUnchanged': True,
              'credentialsUnchanged': True, 'inactiveHistoryContentsUnchanged': len(hashes),
              'historyCount': len(history), 'zipAndGuideHashesValid': True,
              'packageSHA256': hashlib.sha256(package.read_bytes()).hexdigest(),
              'settingsHash': digest(after), 'personasHash': digest(people),
              'historyHashes': hashes, 'backup': str(backup), 'newModelCalls': 0}
    (ROOT / 'build/role-version-labels-v9.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['settingsHash','personasHash','historyHashes','backup']}, ensure_ascii=False))
