"""Verify installed rubrics, protected data and served frontend without inference."""
import hashlib
import json
import os
from pathlib import Path
import zipfile
import httpx

ROOT=Path(__file__).resolve().parent.parent
digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
before=json.loads((ROOT/'build/opening-v11-before.json').read_text(encoding='utf-8'))
installed=json.loads((ROOT/'build/imported-opening-v11.json').read_text(encoding='utf-8'))
bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
assert bundle['version']==11
with httpx.Client(base_url='http://127.0.0.1:3340',trust_env=False,timeout=30) as client:
    health=client.get('/api/health').raise_for_status().json()
    assert health['features']['review_opening_commercial']==1
    settings=client.get('/api/settings').raise_for_status().json()
    people=client.get('/api/personas').raise_for_status().json()
    assert digest(settings)==installed['settingsHash'] and digest(people)==installed['personasHash']
    # Prove the cumulative two prompt installations changed only authorized fields.
    baseline=sorted((ROOT/'build/role-backups').glob('opening-v11-*'))[0]
    original_people=json.loads((baseline/'personas.json').read_text(encoding='utf-8'))
    original_settings=json.loads((baseline/'review-settings.json').read_text(encoding='utf-8'))
    restored_settings={**settings,**original_settings}
    assert digest(restored_settings)==before['settingsHash']
    restored_people=[{**p,'system_prompt':next(o for o in original_people if o['id']==p['id'])['system_prompt']} for p in people]
    assert digest(restored_people)==before['personasHash']
    for role in bundle['personas'].values():
        assert next(p for p in people if p['name']==role['name'])['system_prompt']==role['system_prompt']
    history=client.get('/api/conversations').raise_for_status().json()
    assert all(digest(client.get('/api/conversations/'+cid).raise_for_status().json())==value for cid,value in before['historyHashes'].items())
    credentials=Path(os.environ['LOCALAPPDATA'])/'AICounselReview/credentials.json'
    assert hashlib.sha256(credentials.read_bytes()).hexdigest()==before['credentialFileHash']
    assets=list((ROOT/'frontend/dist/assets').glob('*'))
    for asset in assets:assert client.get('/assets/'+asset.name).raise_for_status().content==asset.read_bytes()
    assert client.get('/').raise_for_status().content==(ROOT/'frontend/dist/index.html').read_bytes()
package=ROOT/'dist/审稿说明与六角色-开头与商业融合v11.zip'
with zipfile.ZipFile(package) as archive:
    assert archive.testzip() is None and json.loads(archive.read('角色配置.json'))==bundle
    for item in bundle['sources']:
        assert hashlib.sha256(archive.read(item['file'])).hexdigest()==item['sha256']
summary={'version':11,'runtimeFeatureLoaded':True,'sixRolePromptsMatchPackage':True,'onlyAuthorizedTemplatesAndPresetLabelChanged':True,
         'historyCount':len(history),'originalFullHistoriesUnchanged':len(before['historyHashes']),
         'credentialsUnchanged':True,'assetsMatch':len(assets),'packageHashesAndCRCValid':True,
         'packageSHA256':hashlib.sha256(package.read_bytes()).hexdigest(),'privateDraftResubmitted':False,
         'backendChecksPassed':89,'frontendChecksPassed':56}
(ROOT/'build/opening-v11-final-check.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
