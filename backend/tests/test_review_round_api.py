import json
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from backend import main, advisors, storage
from backend.model_preflight import ModelPreflightResult

@pytest.mark.parametrize('rounds',[1,2])
def test_fixed_round_api_passes_policy_and_persists_actual_count(tmp_path,monkeypatch,rounds):
    monkeypatch.setattr(storage,'DATA_DIR',str(tmp_path/'conversations'))
    monkeypatch.setattr(advisors,'preflight_models',AsyncMock(return_value=ModelPreflightResult()))
    async def review(pid,prompt,*args,**kwargs):return pid,'custom:fixture','针对全文的意见 CONSENSUS_SCORE: 5',None
    monkeypatch.setattr(advisors,'_query_advisor',review)
    monkeypatch.setattr(advisors,'_query_neutral',AsyncMock(return_value={'model':'custom:fixture','content':'汇总实际意见','error':None}))
    monkeypatch.setattr(main,'generate_conversation_title',AsyncMock(return_value='虚构检查'))
    with TestClient(main.app) as client:
        cid=client.post('/api/conversations',json={'mode':'advisors'}).json()['id']
        response=client.post(f'/api/conversations/{cid}/debate/stream',json={'question':'虚构原稿','persona_ids':['skeptic','pragmatist'],'default_model':'custom:fixture','max_rounds':rounds,'round_policy':'fixed'})
        assert response.status_code==200
        events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        assert len([e for e in events if e['type']=='advisor_round_start'])==rounds
        message=client.get(f'/api/conversations/{cid}').json()['messages'][-1]
        assert message['metadata']['round_policy']=='fixed'
        assert message['metadata']['rounds_executed']==rounds
        assert message['metadata']['max_rounds']==rounds

@pytest.mark.parametrize('count,policy',[(0,'fixed'),(11,'fixed'),(2,'adaptive')])
def test_round_api_rejects_before_writing_manuscript(tmp_path,monkeypatch,count,policy):
    monkeypatch.setattr(storage,'DATA_DIR',str(tmp_path/'conversations'))
    with TestClient(main.app) as client:
        cid=client.post('/api/conversations',json={'mode':'advisors'}).json()['id']
        response=client.post(f'/api/conversations/{cid}/debate/stream',json={'question':'不能写入','persona_ids':['skeptic','pragmatist'],'max_rounds':count,'round_policy':policy})
        assert response.status_code==400
        assert client.get(f'/api/conversations/{cid}').json()['messages']==[]


def test_failed_role_is_still_present_after_sse_completion_and_history_reload(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DATA_DIR',str(tmp_path/'conversations'))
    monkeypatch.setattr(advisors,'preflight_models',AsyncMock(return_value=ModelPreflightResult()))
    async def review(pid,*args,**kwargs):
        return pid,'custom:fixture',None,'Request timed out' if pid=='skeptic' else 'HTTP 401'
    monkeypatch.setattr(advisors,'_query_advisor',review)
    monkeypatch.setattr(advisors,'_query_neutral',AsyncMock(return_value={'model':'custom:fixture','content':'只根据现有材料汇总','error':None}))
    monkeypatch.setattr(main,'generate_conversation_title',AsyncMock(return_value='虚构失败检查'))
    with TestClient(main.app) as client:
        cid=client.post('/api/conversations',json={'mode':'advisors'}).json()['id']
        result=client.post(f'/api/conversations/{cid}/debate/stream',json={'question':'虚构原稿','persona_ids':['skeptic','pragmatist'],'default_model':'custom:fixture','max_rounds':1,'round_policy':'fixed'})
        assert result.status_code==200
        message=client.get(f'/api/conversations/{cid}').json()['messages'][-1]
        assert len(message['rounds'][0]['responses'])==2
        assert {r['error'] for r in message['rounds'][0]['responses']}=={'Request timed out','HTTP 401'}
