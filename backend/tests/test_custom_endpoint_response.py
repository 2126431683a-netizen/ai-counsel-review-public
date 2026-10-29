"""A successful HTTP page is not a successful model response."""

import json

import httpx
import pytest
import respx

from backend.providers.custom_openai import CustomOpenAIProvider


@pytest.fixture
def provider(monkeypatch):
    value = CustomOpenAIProvider()
    monkeypatch.setattr(value, "_get_config", lambda: ("Fixture", "https://fixture.test/v1", "fixture-key"))
    return value


@pytest.mark.asyncio
@respx.mock
async def test_http_200_html_explains_api_base_instead_of_json_position(provider):
    respx.post("https://fixture.test/v1/chat/completions").mock(return_value=httpx.Response(200, text="<!doctype html><html>console</html>", headers={"content-type": "text/html"}))
    result = await provider.query("custom:fixture", [{"role": "user", "content": "OK"}])
    assert result["error"] is True
    assert "/v1" in result["error_message"]
    assert "网页" in result["error_message"]
    assert "line 1 column 1" not in result["error_message"]


@pytest.mark.asyncio
@respx.mock
async def test_chat_prefers_streaming_and_also_accepts_normal_json(provider):
    route = respx.post("https://fixture.test/v1/chat/completions").mock(return_value=httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}], "usage": {"total_tokens": 2}}))
    result = await provider.query("custom:fixture", [{"role": "user", "content": "OK"}])
    assert result["content"] == "OK"
    assert not result["error"]
    assert json.loads(route.calls.last.request.content)["stream"] is True
    assert result['transport']=='json'


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("body,expected", [("", "空响应"), ("not JSON", "有效 JSON"), ('{"choices":[]}', "choices"), ('{"choices":[{"message":{}}]}', "正文")])
async def test_malformed_success_responses_are_actionable(provider, body, expected):
    respx.post("https://fixture.test/v1/chat/completions").mock(return_value=httpx.Response(200, text=body))
    result = await provider.query("custom:fixture", [{"role": "user", "content": "OK"}])
    assert result["error"] is True
    assert expected in result["error_message"]


@pytest.mark.asyncio
@respx.mock
async def test_connection_test_rejects_html_model_page(provider):
    respx.get("https://fixture.test/v1/models").mock(return_value=httpx.Response(200, text="<html>console</html>", headers={"content-type": "text/html"}))
    result = await provider.validate_connection("https://fixture.test/v1")
    assert result["success"] is False
    assert "/v1" in result["message"]
