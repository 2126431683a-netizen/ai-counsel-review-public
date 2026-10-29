"""Capture protected hashes and require no active run before a source reload."""
import hashlib
import json
import os
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parent.parent
digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
with httpx.Client(base_url='http://127.0.0.1:3340',trust_env=False,timeout=30) as client:
    settings=client.get('/api/settings').raise_for_status().json()
    personas=client.get('/api/personas').raise_for_status().json()
    history=client.get('/api/conversations').raise_for_status().json()
    active=[h['id'] for h in history if client.get('/api/conversations/'+h['id']+'/progress').raise_for_status().json().get('active')]
    assert not active,'Do not reload a server with active user reviews'
    credential=Path(os.environ['LOCALAPPDATA'])/'AICounselReview/credentials.json'
    report={'settingsHash':digest(settings),'personasHash':digest(personas),
            'historyHashes':{h['id']:digest(client.get('/api/conversations/'+h['id']).raise_for_status().json()) for h in history},
            'credentialFileHash':hashlib.sha256(credential.read_bytes()).hexdigest(),'historyCount':len(history),'active':active}
    (ROOT/'build/opening-v11-before.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'historyCount':len(history),'active':len(active),'snapshotted':True}))
