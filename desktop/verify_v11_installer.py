"""Install the final EXE in an isolated Chinese path; protect the live profile."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import zipfile
import httpx

ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('--installer',type=Path,default=ROOT/'dist/AI审稿团-v11-Windows-x64-安装包.exe')
parser.add_argument('--payload',type=Path,default=ROOT/'dist/payload-roles-v11-20261018.zip')
parser.add_argument('--report',type=Path,default=ROOT/'build/v11-installer-verification.json')
parser.add_argument('--frontend-dir',type=Path,default=ROOT/'frontend/dist')
parser.add_argument('--cat-release',action='store_true')
parser.add_argument('--release-label',default='')
parser.add_argument('--ip-release',action='store_true')
args=parser.parse_args()
INSTALLER=args.installer.resolve()
PAYLOAD=args.payload.resolve()
QA=ROOT/'build'/('安装验收-v11-'+str(time.time_ns()))
DEST=QA/'程序';DATA=QA/'独立数据'
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def files(directory):
    return {str(p.relative_to(directory)):digest(p) for p in directory.rglob('*') if p.is_file() and p.name not in ['server.log','desktop-server.pid','launcher-check.json']}
env=dict(os.environ,AI_COUNSEL_DATA_DIR=str(DATA))
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
env['AI_COUNSEL_PORT']=str(port)
run=lambda args,check=True:subprocess.run([str(x) for x in args],env=env,check=check,creationflags=subprocess.CREATE_NO_WINDOW)
run([INSTALLER,'--verify'])
run([INSTALLER,'--silent','--no-shortcuts','--dir',DEST])
with zipfile.ZipFile(PAYLOAD) as z:
    assert z.testzip() is None
    for item in z.infolist():
        target=DEST/item.filename
        assert target.resolve().is_relative_to(DEST.resolve())
        assert target.read_bytes()==z.read(item)
    payload_count=len(z.infolist())
bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
assert json.loads((DEST/'server/_internal/desktop/role_bundle.json').read_text(encoding='utf-8'))==bundle
build_info=json.loads((DEST/'build-info.json').read_text(encoding='utf-8'))
assert build_info['reviewVersion']==11 and not build_info['apiKeysIncluded'] and not build_info['profileIncluded']
launcher=DEST/'AI审稿团.exe'
try:
    run([launcher,'--smoke-test'])
    with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=20) as c:
        assert c.get('/api/health').raise_for_status().json()['features']['review_opening_commercial']==1
        if args.release_label:
            assert build_info['releaseLabel']==args.release_label
        if args.ip_release:
            for name in ['yuanbao-ip-cat-64.png','yuanbao-ip-cat-180.png','yuanbao-ip-cat-256.png','yuanbao-ip-cat-512.png','yuanbao-ip-cat.ico']:
                assert c.get('/'+name).raise_for_status().content==(ROOT/'frontend/public'/name).read_bytes()
            assert (DEST/'assets/yuanbao-ip/yuanbao-ip-cat.ico').read_bytes()==(ROOT/'desktop/assets/yuanbao-ip/yuanbao-ip-cat.ico').read_bytes()
            assert (DEST/'详细教程/使用教程.html').is_file()
            assert (DEST/'详细教程/AI审稿团-v11.2-详细教程.pdf').is_file()
        if args.cat_release:
            health=c.get('/api/health').raise_for_status().json()
            assert health['features']['local_model_quick_connect']==1 and health['features']['review_score_ledger_recovery']==1
            for name in ['review-cat-64.png','review-cat-180.png','review-cat-256.png','review-cat-512.png','review-cat.ico']:
                assert c.get('/'+name).raise_for_status().content==(ROOT/'frontend/public'/name).read_bytes()
            assert build_info['releaseLabel']=='v11.1'
            assert (DEST/'assets/review-cat.ico').read_bytes()==(ROOT/'desktop/assets/review-cat.ico').read_bytes()
        settings=c.get('/api/settings').raise_for_status().json()
        people=c.get('/api/personas').raise_for_status().json()
        assert settings['advisor_chair_persona_id']=='source-editor'
        assert settings['advisor_presets'][0]['name']==bundle['name']
        assert len(people)==6
        for p in people:assert p['system_prompt']==bundle['personas'][p['id']]['system_prompt']
        assert c.get('/api/conversations').raise_for_status().json()==[]
        assets=list((args.frontend_dir/'assets').glob('*'))
        for p in assets:assert c.get('/assets/'+p.name).raise_for_status().content==p.read_bytes()
        assert c.get('/').raise_for_status().content==(args.frontend_dir/'index.html').read_bytes()
    protected=files(DATA)
    assert run([INSTALLER,'--silent','--no-shortcuts','--dir',DEST],check=False).returncode==1,'Running installation must be protected'
    assert files(DATA)==protected
finally:
    run([launcher,'--stop'])
with socket.socket() as sock:
    assert sock.connect_ex(('127.0.0.1',port))!=0
protected=files(DATA)
run([INSTALLER,'--silent','--no-shortcuts','--dir',DEST])
assert files(DATA)==protected
run([launcher,'--smoke-test'])
run([launcher,'--stop'])
assert files(DATA)==protected
result={'installer':str(INSTALLER),'bytes':INSTALLER.stat().st_size,'sha256':digest(INSTALLER),
        'payloadEntriesByteMatched':payload_count,'payloadCRCValid':True,'chinesePathInstallation':True,
        'launcherStartsAndStopsInstalledRuntime':True,'runningInstallUpdateBlocked':True,
        'offlineUpdatePreservesIndependentProfile':True,'freshProfileHasSixV11Prompts':True,
        'freshHistoryEmpty':True,'frontendAssetsByteMatched':len(assets),'reviewVersion':11,
        'testPortReleased':True,'desktopShortcutsOrRegistryChanged':False,'profile':str(DATA),
        'includesCredentialsOrPrivateDrafts':False,'modelCalls':0,'usesRealModel':False}
result['catReleaseValidated']=args.cat_release
result['ipReleaseValidated']=args.ip_release
result['releaseLabel']=args.release_label
args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['profile','installer']},ensure_ascii=False))
