import json
from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
import respx
from backend import local_models as local
from backend.providers.local_openai import LocalOpenAIProvider


@pytest.fixture
def state(monkeypatch):
    settings=SimpleNamespace(local_model_url='',custom_endpoint_url='https://cloud.invalid/v1',enabled_providers={'custom':True},advisor_default_model='custom:cloud')
    save=Mock();secret=Mock(return_value='local-fixture');set_secret=Mock();delete=Mock()
    monkeypatch.setattr(local,'get_settings',lambda:settings)
    monkeypatch.setattr(local,'update_settings',save)
    monkeypatch.setattr(local,'get_api_key',secret)
    monkeypatch.setattr(local,'set_secret',set_secret)
    monkeypatch.setattr(local,'delete_secret',delete)
    return settings,save,secret,set_secret,delete


@pytest.mark.asyncio
async def test_detection_normalizes_ollama_and_never_writes(state):
    with respx.mock as mock:
        mock.get('http://127.0.0.1:11434/api/tags').respond(200,json={'models':[{'name':'qwen:test'},{'name':'embed-only'},{'name':'qwen:test'}]})
        result=await local.check(local.LocalRequest(url='127.0.0.1:11434/api'))
    assert result['success'] and [m['id'] for m in result['models']]==['ollama:qwen:test']
    state[1].assert_not_called();state[2].assert_not_called();state[3].assert_not_called()


@pytest.mark.asyncio
async def test_local_use_is_separate_from_custom_cloud_and_sets_both_review_models(state):
    with respx.mock as mock:
        route=mock.get('http://127.0.0.1:1234/v1/models').respond(200,json={'data':[{'id':'qwen'}]})
        result=await local.use(local.LocalRequest(service='lmstudio',url='127.0.0.1:1234/v1/chat/completions',model='local:qwen'))
    assert result['success']
    assert 'authorization' not in route.calls[0].request.headers
    update=state[1].call_args.kwargs
    assert set(update)=={'enabled_providers','advisor_default_model','advisor_tiebreaker_model','local_model_url'}
    assert update['enabled_providers']=={'custom':True,'local':True}
    assert update['advisor_tiebreaker_model']=='local:qwen'
    state[2].assert_not_called()


@pytest.mark.asyncio
async def test_unknown_or_empty_model_cannot_save_connection(state):
    with respx.mock as mock:
        mock.get('http://127.0.0.1:1234/v1/models').respond(200,json={'data':[]})
        result=await local.use(local.LocalRequest(service='lmstudio',model='local:imagined'))
    assert not result['success'];state[1].assert_not_called()


@pytest.mark.asyncio
async def test_auth_failure_and_html_are_actionable_not_json_tracebacks(state):
    with respx.mock as mock:
        route=mock.get('http://127.0.0.1:1234/v1/models').respond(401)
        result=await local.check(local.LocalRequest(service='lmstudio'))
        assert not result['success'] and '密钥' in result['message']
        route.respond(200,text='<html>console</html>',headers={'content-type':'text/html'})
        result=await local.check(local.LocalRequest(service='lmstudio'))
        assert not result['success'] and 'JSONDecodeError' not in result['message']
    state[1].assert_not_called()


@pytest.mark.asyncio
async def test_local_token_is_reused_only_for_same_url(state):
    state[0].local_model_url='http://127.0.0.1:1234/v1'
    with respx.mock as mock:
        a=mock.get('http://127.0.0.1:1234/v1/models').respond(200,json={'data':[]})
        b=mock.get('http://127.0.0.1:4321/v1/models').respond(200,json={'data':[]})
        await local.check(local.LocalRequest(service='lmstudio'))
        await local.check(local.LocalRequest(service='lmstudio',url='http://127.0.0.1:4321'))
    assert a.calls[0].request.headers['authorization']=='Bearer local-fixture'
    assert 'authorization' not in b.calls[0].request.headers
    state[2].assert_called_once_with('local_model')


@pytest.mark.parametrize('url',['https://cloud.invalid/v1','http://127.0.0.1:1234?key=secret','http://user:secret@127.0.0.1:1234','http://192.168.1.2:1234'])
def test_quick_entry_is_loopback_only(url):
    with pytest.raises(ValueError):local.normalize_url(url,'lmstudio')


@pytest.mark.asyncio
async def test_local_provider_dispatch_strips_local_prefix_and_never_uses_cloud_secret(monkeypatch):
    import backend.providers.local_openai as provider
    from backend.council import get_provider_for_model
    monkeypatch.setattr(provider,'get_settings',lambda:SimpleNamespace(local_model_url='http://127.0.0.1:1234/v1'))
    token=Mock(return_value='');monkeypatch.setattr(provider,'get_api_key',token)
    assert isinstance(get_provider_for_model('local:qwen'),LocalOpenAIProvider)
    with respx.mock as mock:
        route=mock.post('http://127.0.0.1:1234/v1/chat/completions').respond(200,json={'choices':[{'message':{'content':'本地夹具OK'},'finish_reason':'stop'}]})
        result=await LocalOpenAIProvider().query('local:qwen',[{'role':'user','content':'虚构连接检查'}])
    assert result['content']=='本地夹具OK'
    assert json.loads(route.calls[0].request.content)['model']=='qwen'
    assert 'authorization' not in route.calls[0].request.headers
    token.assert_called_once_with('local_model')
