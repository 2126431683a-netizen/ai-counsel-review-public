"""Frozen release: local quick connect plus ledger recovery, with mock models only."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import httpx

ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser();parser.add_argument('--server',required=True);parser.add_argument('--output',default='build/cat-release-feature-verification.json');args=parser.parse_args()
bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
draft='先展示分镜，再生成工程。最后打开预览检查结果。'
calls=[]


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send_json(self,data):
        raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(200)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
        self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        calls.append({'path':self.path,'auth':self.headers.get('Authorization','')})
        self.send_json({'data':[{'id':'review-fixture'}]})
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
        system='\n'.join(m.get('content','') for m in body.get('messages',[]) if m.get('role')=='system')
        user='\n'.join(m.get('content','') for m in body.get('messages',[]) if m.get('role')=='user')
        role=next((pid for pid,p in bundle['personas'].items() if p['system_prompt']==system),None)
        content='OK'
        if role and role!='source-editor':
            import re
            cfg=json.loads(re.search(r'<review-group-config>(.*?)</review-group-config>',system,re.S)[1])
            comment='这个顺序我能跟上。'
            notes={d['id']:{'basis':'先展示分镜','context':'最后打开预览检查结果','rationale':'有控制点，但缺少入口示例','deduction':'需要具体入口',
                           'checks':[{'id':c['id'],'score':3.5,'basis':'先展示分镜','rationale':'顺序基本可用','gap':'未展开具体入口'} for c in d['checks']]} for d in cfg['dimensions']}
            notes['commercial'].update(deduction='不适用：未见足够推广依据',checks=[])
            content=comment+'\n<review-comments>'+json.dumps({'comments':[{'text':comment,'basis':'先展示分镜','rationale':'顺序已明确'}],'dimension_notes':notes},ensure_ascii=False)+'</review-comments>'
            if role!='source-beginner':
                content+='<review-score>'+json.dumps({'scores':{d['id']:None if d['id']=='commercial' else 7 for d in cfg['dimensions']},'unrated_reasons':{'commercial':'不适用：没有推广'}})+'</review-score>'
            content+='\nCONSENSUS_SCORE: 4'
        elif role=='source-editor':
            assert '7.0/10' in user
            content='已按实际返回的五团意见收束。本例是协议夹具，不是模型质量测试。'
        calls.append({'path':self.path,'auth':self.headers.get('Authorization',''),'role':role,'model':body.get('model')})
        self.send_json({'choices':[{'message':{'content':content},'finish_reason':'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30}})


mock=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=mock.serve_forever,daemon=True).start()
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
profile=ROOT/'build'/('cat-features-profile-'+str(time.time_ns()))
env={**os.environ,'NO_PROXY':'127.0.0.1,localhost,::1','LLM_COUNCIL_PRICING_SOURCE_URL':f'http://127.0.0.1:{mock.server_port}/pricing','LLM_COUNCIL_LITELLM_PRICING_URL':f'http://127.0.0.1:{mock.server_port}/pricing'}
process=subprocess.Popen([str(Path(args.server).resolve()),'--port',str(port),'--data-dir',str(profile)],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
try:
    with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=45) as c:
        deadline=time.monotonic()+60
        while True:
            try:
                if c.get('/api/health',timeout=1).status_code==200:break
            except httpx.HTTPError:pass
            assert time.monotonic()<deadline and process.poll() is None;time.sleep(.2)
        health=c.get('/api/health').json()
        assert health['features']['local_model_quick_connect']==1 and health['features']['review_score_ledger_recovery']==1
        url=f'http://127.0.0.1:{mock.server_port}/v1';cloud=url.replace('/v1','/cloud/v1')
        c.put('/api/settings',json={'custom_endpoint_url':cloud,'custom_endpoint_api_key':'fixture-cloud-not-for-local','enabled_providers':{'custom':True}}).raise_for_status()
        before=c.get('/api/settings').json()
        check=c.post('/api/local-models/check',json={'service':'lmstudio','url':url}).raise_for_status().json()
        assert check['models'][0]['id']=='local:review-fixture'
        assert c.get('/api/settings').json()==before
        used=c.post('/api/local-models/use',json={'service':'lmstudio','url':url,'model':'local:review-fixture'}).raise_for_status().json()
        settings=c.get('/api/settings').json();assert settings['custom_endpoint_url']==cloud and settings['custom_endpoint_api_key_set']
        assert settings['advisor_default_model']=='local:review-fixture'
        ids=[pid for pid in bundle['personas'] if pid!='source-editor']
        conversation=c.post('/api/conversations',json={'mode':'advisors'}).raise_for_status().json()
        response=c.post('/api/conversations/'+conversation['id']+'/debate/stream',json={'question':draft,'persona_ids':ids,'default_model':'local:review-fixture','max_rounds':1,'round_policy':'fixed'}).raise_for_status()
        events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        result=next(e['data'] for e in events if e['type']=='advisor_complete')
        beginner=next(r for r in result['rounds'][0]['responses'] if r['persona_id']=='source-beginner')
        assert beginner['review_rating']['score']==7 and beginner['review_rating']['calculation_source']=='validated_check_ledger'
        assert result['verdict']['review_score_report']['score']==7
        saved=c.get('/api/conversations/'+conversation['id']).raise_for_status().json()
        assert saved['messages'][1]['rounds'][0]['responses']==result['rounds'][0]['responses']
        assert not any('fixture-cloud-not-for-local' in x['auth'] for x in calls if not x['path'].startswith('/cloud'))
        roles=[x for x in calls if x.get('role')]
        assert len(roles)==6 and len([x for x in roles if x['role']=='source-beginner'])==1
        report={'frozenRuntime':True,'localCheckReadOnly':True,'localUseAndCloudPreservation':True,'cloudSecretNeverForwarded':True,'fiveGroupsAndChair':True,'missingSummaryRecoveredBeforeChair':True,'checkpointNumbersPreserved':True,'savedRatingMetadataPreserved':True,'reviewerAndChairCalls':len(roles),'usesRealModel':False}
        (ROOT/args.output).write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
finally:
    process.terminate();process.wait(timeout=15);mock.shutdown()
