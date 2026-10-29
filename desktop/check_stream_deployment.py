"""Read-only deployment integrity check; never submit a model request."""
import hashlib
import json
import os
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parent.parent
digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
before = json.loads((ROOT / 'build/stream-transport-before.json').read_text(encoding='utf-8'))
runtime = json.loads((ROOT / 'build/stream-transport-live-check.json').read_text(encoding='utf-8'))
with httpx.Client(base_url='http://127.0.0.1:3340', trust_env=False, timeout=30) as client:
    settings = client.get('/api/settings').raise_for_status().json()
    people = client.get('/api/personas').raise_for_status().json()
    history = client.get('/api/conversations').raise_for_status().json()
    histories = {item['id']: digest(client.get('/api/conversations/' + item['id']).raise_for_status().json()) for item in history}
    health = client.get('/api/health').raise_for_status().json()
    assets = list((ROOT / 'frontend/dist/assets').glob('*'))
    for asset in assets:
        assert client.get('/assets/' + asset.name).raise_for_status().content == asset.read_bytes(), asset.name
credential = Path(os.environ['LOCALAPPDATA']) / 'AICounselReview/credentials.json'
report = {
    'streamFeatureLoaded': health.get('features', {}).get('custom_stream_transport') == 1,
    'runtimeInferenceConfirmed': runtime['runtimeInferenceConfirmed'],
    'runtimeTransport': runtime['runtimeTransport'],
    'settingsAndRolesUnchanged': digest(settings) == before['settingsHash'] and digest(people) == before['personasHash'],
    'credentialFileUnchanged': hashlib.sha256(credential.read_bytes()).hexdigest() == before['credentialFileHash'],
    'allOriginalHistoryContentsUnchanged': all(histories.get(key) == value for key, value in before['historyHashes'].items()),
    'historyCount': len(history),
    'assetsMatch': len(assets),
    'privateDraftResubmitted': False,
}
assert all(report[key] for key in ['streamFeatureLoaded', 'runtimeInferenceConfirmed', 'settingsAndRolesUnchanged', 'credentialFileUnchanged', 'allOriginalHistoryContentsUnchanged'])
(ROOT / 'build/stream-transport-final-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
