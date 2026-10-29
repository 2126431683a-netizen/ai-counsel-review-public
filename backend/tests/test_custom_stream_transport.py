import asyncio
import json
import httpx
import pytest
import respx
from backend.providers.custom_openai import CustomOpenAIProvider


@pytest.fixture
def provider(monkeypatch):
    value=CustomOpenAIProvider()
    monkeypatch.setattr(value,'_get_config',lambda:('Fixture','https://fixture.test/v1','fixture-key'))
    return value


class Pieces(httpx.AsyncByteStream):
    def __init__(self,values,broken=False):self.values=values;self.broken=broken
    async def __aiter__(self):
        for value in self.values:yield value
        if self.broken:raise httpx.RemoteProtocolError('connection closed')


def chunk(content='',finish=None):
    return ('data: '+json.dumps({'choices':[{'index':0,'delta':{'content':content},'finish_reason':finish}]},ensure_ascii=False)+'\n\n').encode()


@pytest.mark.asyncio
@respx.mock
async def test_complete_sse_merges_text_handles_byte_splits_and_preserves_usage(provider):
    body=b': keep-alive\n\n'+chunk('原文')+chunk('已核对','stop')+b'data: {"choices":[],"usage":{"total_tokens":23}}\n\ndata: [DONE]\n\n'
    respx.post('https://fixture.test/v1/chat/completions').mock(return_value=httpx.Response(200,headers={'content-type':'text/event-stream'},stream=Pieces([body[:84],body[84:87],body[87:]])))
    result=await provider.query('custom:fixture',[{'role':'user','content':'虚构稿'}])
    assert result['content']=='原文已核对' and result['usage']['total_tokens']==23 and not result['error']


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize('broken',[False,True])
async def test_half_reply_is_not_accepted_as_complete_review(provider,broken):
    respx.post('https://fixture.test/v1/chat/completions').mock(return_value=httpx.Response(200,headers={'content-type':'text/event-stream'},stream=Pieces([chunk('半截评论')],broken=broken)))
    result=await provider.query('custom:fixture',[{'role':'user','content':'虚构稿'}])
    assert result['error'] and not result.get('content')


@pytest.mark.asyncio
@respx.mock
async def test_completed_finish_is_sufficient_even_if_gateway_closes_before_done(provider):
    respx.post('https://fixture.test/v1/chat/completions').mock(return_value=httpx.Response(200,headers={'content-type':'text/event-stream'},stream=Pieces([chunk('完整回复','stop')],broken=True)))
    result=await provider.query('custom:fixture',[{'role':'user','content':'虚构稿'}])
    assert result['content']=='完整回复' and not result['error']


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize('message,expected_stream',[('Unsupported parameter: stream_options',True),('Streaming is not supported',False)])
async def test_only_explicit_unsupported_options_trigger_compatibility_fallback(provider,message,expected_stream):
    route=respx.post('https://fixture.test/v1/chat/completions').mock(side_effect=[httpx.Response(400,json={'error':{'message':message}}),httpx.Response(200,json={'choices':[{'message':{'content':'OK'}}]})])
    result=await provider.query('custom:fixture',[{'role':'user','content':'虚构稿'}])
    assert not result['error'] and len(route.calls)==2
    assert json.loads(route.calls.last.request.content)['stream'] is expected_stream
    assert 'stream_options' not in json.loads(route.calls.last.request.content)


@pytest.mark.asyncio
@respx.mock
async def test_auth_failure_is_not_retried_or_hidden_by_stream_negotiation(provider):
    route=respx.post('https://fixture.test/v1/chat/completions').mock(return_value=httpx.Response(401,json={'error':{'message':'Unauthorized'}}))
    result=await provider.query('custom:fixture',[{'role':'user','content':'虚构稿'}])
    assert result['error'] and result['http_status']==401 and len(route.calls)==1


@pytest.mark.asyncio
@respx.mock
async def test_stream_error_and_truncation_do_not_become_normal_comments(provider):
    route=respx.post('https://fixture.test/v1/chat/completions')
    for body in [b'data: {"error":{"message":"service temporarily unavailable"}}\n\n',chunk('截断输出','length'),b'data: not-json\n\n']:
        route.mock(return_value=httpx.Response(200,headers={'content-type':'text/event-stream'},content=body))
        result=await provider.query('custom:fixture',[{'role':'user','content':'虚构稿'}])
        assert result['error'] and not result.get('content')


@respx.mock
def test_connection_probe_can_check_model_without_saving_a_conversation():
    from fastapi.testclient import TestClient
    from backend.main import app
    respx.get('https://fixture.test/v1/models').mock(return_value=httpx.Response(200,json={'data':[{'id':'fixture'}]}))
    respx.post('https://fixture.test/v1/chat/completions').mock(return_value=httpx.Response(200,headers={'content-type':'text/event-stream'},content=chunk('OK','stop')))
    with TestClient(app) as client:
        result=client.post('/api/settings/test-custom-endpoint',json={'name':'Fixture','url':'https://fixture.test/v1','api_key':'fixture-key','model':'custom:fixture'}).json()
    assert result['success'] and result['transport']=='stream'


@pytest.mark.asyncio
@respx.mock
async def test_stream_heartbeats_cannot_extend_total_request_budget_forever(provider):
    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b': keep-alive\n\n'
            await asyncio.sleep(.08)
            yield chunk('late','stop')
    respx.post('https://fixture.test/v1/chat/completions').mock(return_value=httpx.Response(200,headers={'content-type':'text/event-stream'},stream=Slow()))
    result=await provider.query('custom:fixture',[{'role':'user','content':'虚构稿'}],timeout=.02)
    assert result['error'] and 'timed out' in result['error_message']


@pytest.mark.asyncio
@respx.mock
async def test_done_marker_finishes_without_waiting_for_proxy_to_close_socket(provider):
    class StaysOpen(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield chunk('OK','stop')+b'data: [DONE]\n\n'
            raise AssertionError('Do not read beyond the terminal DONE marker')
    respx.post('https://fixture.test/v1/chat/completions').mock(return_value=httpx.Response(200,headers={'content-type':'text/event-stream'},stream=StaysOpen()))
    result=await provider.query('custom:fixture',[{'role':'user','content':'虚构稿'}])
    assert not result['error'] and result['content']=='OK'


@pytest.mark.asyncio
@respx.mock
async def test_json_fallback_also_rejects_explicitly_truncated_reply(provider):
    respx.post('https://fixture.test/v1/chat/completions').mock(return_value=httpx.Response(200,json={'choices':[{'message':{'content':'半截内容'},'finish_reason':'length'}]}))
    result=await provider.query('custom:fixture',[{'role':'user','content':'虚构稿'}])
    assert result['error'] and not result.get('content')
