"""Isolated full-app local-service fixture, without access to production data."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib,json,os,socket,subprocess,threading,time
import httpx

ROOT=Path(__file__).resolve().parent.parent
profile=ROOT/'build'/('local-connect-profile-'+str(time.time_ns()))
profile.mkdir()
calls=[]
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        calls.append({'path':self.path,'auth':self.headers.get('Authorization','')})
        if self.path.startswith('/empty'):data={'data':[]}
        elif self.path.startswith('/auth'):
            self.send_response(401);self.end_headers();return
        elif self.path=='/api/tags':data={'models':[{'name':'qwen-fixture'},{'name':'embed-only'}]}
        elif self.path.startswith('/cloud'):data={'data':[{'id':'cloud-fixture'}]}
        else:data={'data':[{'id':'qwen-fixture'},{'id':'embed-only'}]}
        payload=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
        calls.append({'path':self.path,'auth':self.headers.get('Authorization',''),'model':body.get('model')})
        data={'choices':[{'message':{'content':'本地连接夹具OK'},'finish_reason':'stop'}],'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}
        payload=json.dumps(data,ensure_ascii=False).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)

mock=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=mock.serve_forever,daemon=True).start()
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
process=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-X','utf8',str(ROOT/'desktop/server.py'),'--port',str(port),'--data-dir',str(profile)],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
stop=ROOT/'build/local-connect-preview.stop';assert not stop.exists()
try:
    with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=25) as c:
        deadline=time.monotonic()+60
        while True:
            try:
                if c.get('/api/health').status_code==200:break
            except httpx.HTTPError:pass
            assert time.monotonic()<deadline;time.sleep(.2)
        cloud=f'http://127.0.0.1:{mock.server_port}/cloud/v1'
        c.put('/api/settings',json={'custom_endpoint_name':'虚构云服务','custom_endpoint_url':cloud,'custom_endpoint_api_key':'fixture-cloud-only','enabled_providers':{'custom':True},'advisor_default_model':'custom:cloud-fixture'}).raise_for_status()
        info={'url':f'http://127.0.0.1:{port}','localUrl':f'http://127.0.0.1:{mock.server_port}/v1','profile':str(profile),'pid':process.pid,'syntheticOnly':True}
        (ROOT/'build/local-connect-preview.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(info,ensure_ascii=False),flush=True)
        while not stop.exists():time.sleep(.5)
        settings=c.get('/api/settings').raise_for_status().json()
        assert settings['custom_endpoint_url']==cloud and settings['custom_endpoint_api_key_set']
        local_calls=[x for x in calls if not x['path'].startswith('/cloud')]
        assert not any('fixture-cloud-only' in x['auth'] for x in local_calls)
        assert settings['advisor_default_model']=='local:qwen-fixture'
        response=c.post('/api/ask',json={'content':'虚构连接验收，不含用户稿件','models':['local:qwen-fixture'],'execution_mode':'chat_only'})
        response.raise_for_status()
        assert any(x.get('model')=='qwen-fixture' and x['path']=='/v1/chat/completions' for x in calls)
        result={'cloudConnectionPreserved':True,'localModelSelectedForReview':True,'cloudKeyNotForwardedToLocal':True,'realLocalHTTPInferenceSucceeded':True,'usesActualModel':False,'syntheticOnly':True,'modelCalls':len([x for x in calls if 'model' in x])}
        (ROOT/'build/local-connect-end-to-end.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
finally:
    process.terminate();process.wait(timeout=15);mock.shutdown()
