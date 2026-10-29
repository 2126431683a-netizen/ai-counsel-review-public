"""Custom OpenAI-compatible endpoint provider."""

import asyncio
import json
import httpx

from .errors import describe_exception
from typing import List, Dict, Any
from .base import LLMProvider
from .temperature import add_temperature_if_supported
from ..settings import get_settings


class CustomOpenAIProvider(LLMProvider):
    """Provider for any OpenAI-compatible API endpoint."""
    model_prefix = 'custom:'

    def _http_options(self):
        return {}

    @staticmethod
    def _read_json(response: httpx.Response) -> Dict[str, Any]:
        """Reject web-console pages without exposing their body as a JSON error."""
        body = response.text.lstrip("\ufeff \t\r\n")
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" in content_type or body.lower().startswith(("<!doctype html", "<html")):
            raise ValueError("接口返回了网页（HTML），不是模型响应。请检查 Base URL，通常需要以 /v1 结尾，不要填写控制台首页。")
        if not body:
            raise ValueError("接口返回了空响应，请检查 API 地址和服务状态。")
        try:
            data = response.json()
        except ValueError:
            raise ValueError("接口没有返回有效 JSON，请检查 API 地址、代理配置和服务状态。") from None
        if not isinstance(data, dict):
            raise ValueError("接口响应格式不兼容：需要 OpenAI 兼容的 JSON 对象。")
        return data

    def _get_config(self) -> tuple[str, str, str]:
        """Get custom endpoint configuration."""
        settings = get_settings()
        name = settings.custom_endpoint_name or "Custom"
        url = settings.custom_endpoint_url or ""
        from ..credentials import get_api_key
        api_key = get_api_key("custom_endpoint")
        return name, url, api_key

    @staticmethod
    def _completion(data: Dict[str, Any]) -> Dict[str, Any]:
        if data.get('error'):
            error=data['error']
            detail=error.get('message','模型服务报错') if isinstance(error,dict) else str(error)
            return {'error':True,'error_message':detail}
        choices=data.get('choices')
        if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict):
            return {'error':True,'error_message':'接口返回的 JSON 缺少 choices，请确认该地址支持 /chat/completions。'}
        if choices[0].get('finish_reason') in {'length','content_filter'}:
            return {'error':True,'usage':data.get('usage'),'error_message':'模型回复被长度上限或内容限制截断，审稿未完整生成。'}
        message=choices[0].get('message')
        if not isinstance(message,dict) or not isinstance(message.get('content'),str) or not message['content'].strip():
            return {'error':True,'error_message':'模型没有返回可显示的正文，请检查模型和接口兼容性。'}
        return {'content':message['content'],'usage':data.get('usage'),'error':False}

    @staticmethod
    async def _read_chat_stream(response: httpx.Response) -> Dict[str, Any]:
        parts=[]
        usage=None
        finished=False
        done_marker=False
        finish_reason=None
        def event(raw):
            nonlocal usage,finished,finish_reason,done_marker
            if raw=='[DONE]':
                finished=True
                done_marker=True
                return
            try:
                value=json.loads(raw)
            except json.JSONDecodeError:
                raise ValueError('模型接口返回了无法解析的流式数据') from None
            if not isinstance(value,dict):raise ValueError('模型接口返回了无效的流式数据')
            if value.get('error'):
                error=value['error']
                raise ValueError(error.get('message','模型流式回复报错') if isinstance(error,dict) else str(error))
            if isinstance(value.get('usage'),dict):usage=value['usage']
            for choice in value.get('choices') or []:
                if choice.get('index',0)!=0:continue
                delta=choice.get('delta') or {}
                content=delta.get('content')
                if isinstance(content,str):parts.append(content)
                if choice.get('finish_reason'):
                    finish_reason=choice['finish_reason']
                    finished=True
        pending=[]
        try:
            async for line in response.aiter_lines():
                if line.startswith('data:'):
                    pending.append(line[5:].lstrip())
                elif not line and pending:
                    event('\n'.join(pending));pending=[]
                    if done_marker:break
            if pending:event('\n'.join(pending))
        except httpx.RemoteProtocolError:
            if not finished:
                return {'error':True,'error_code':'connection_closed','usage':usage,
                        'error_message':f'模型接口连接意外中断（已收到{sum(map(len,parts))}字符，回复未完成），尚未形成可用审稿。'}
        except ValueError as exc:
            return {'error':True,'usage':usage,'error_message':str(exc)}
        if not finished:
            return {'error':True,'error_code':'incomplete_stream','usage':usage,
                    'error_message':'模型接口连接提前结束，缺少回复完成标记，未将半截内容作为审稿结果。'}
        if finish_reason in {'length','content_filter'}:
            return {'error':True,'usage':usage,'error_message':'模型回复被长度上限或内容限制截断，审稿未完整生成。'}
        content=''.join(parts)
        if not content.strip():
            return {'error':True,'usage':usage,'error_message':'模型没有返回可显示的正文，请检查模型和接口兼容性。'}
        return {'content':content,'usage':usage,'error':False,'transport':'stream'}

    async def query(self, model_id: str, messages: List[Dict[str, str]], timeout: float = 120.0, temperature: float = 0.7) -> Dict[str, Any]:
        name, base_url, api_key = self._get_config()

        if not base_url:
            return {"error": True, "error_message": f"{name} endpoint URL not configured"}

        # Strip prefix if present
        model = model_id.removeprefix(self.model_prefix)

        # Normalize URL
        if base_url.endswith('/'):
            base_url = base_url[:-1]

        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with asyncio.timeout(timeout), httpx.AsyncClient(timeout=timeout, **self._http_options()) as client:
                payload = add_temperature_if_supported(
                    {
                        "model": model,
                        "messages": messages,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    },
                    model,
                    "custom",
                    temperature,
                )
                # Only negotiate explicit unsupported stream options. Never resend
                # an accepted or partly generated reply inside the provider.
                for _ in range(3):
                    async with client.stream('POST',f'{base_url}/chat/completions',headers=headers,json=payload) as response:
                        if response.status_code!=200:
                            await response.aread()
                            detail=response.text
                            if response.status_code in {400,422}:
                                if 'stream_options' in detail.lower() and 'stream_options' in payload:
                                    payload.pop('stream_options');continue
                                if payload.get('stream') and 'stream' in detail.lower() and any(x in detail.lower() for x in ['unsupported','not support','not allowed','不支持']):
                                    payload['stream']=False;payload.pop('stream_options',None);continue
                            return {'error':True,'http_status':response.status_code,'error_message':f'{name} API error: {response.status_code} - {detail}'}
                        if 'text/event-stream' in response.headers.get('content-type','').lower():
                            return await self._read_chat_stream(response)
                        await response.aread()
                        result=self._completion(self._read_json(response))
                        result['transport']='json'
                        return result
                return {'error':True,'error_message':'接口不支持当前回复格式，请检查其 OpenAI 兼容性。'}

        except (httpx.TimeoutException, TimeoutError):
            return {"error": True, "error_message": f"Request timed out after {int(timeout)}s — {name} did not respond"}
        except httpx.ConnectError:
            return {"error": True, "error_message": f"Connection failed — check the {name} endpoint URL"}
        except httpx.RemoteProtocolError:
            return {'error':True,'error_code':'connection_closed',
                    'error_message':'模型接口在回复前意外断开连接，未取得审稿结果；可能是中转服务或网络暂时异常。'}
        except Exception as e:
            return {"error": True, "error_message": describe_exception(e, timeout)}

    async def get_models(self) -> List[Dict[str, Any]]:
        name, base_url, api_key = self._get_config()

        if not base_url:
            return []

        # Normalize URL
        if base_url.endswith('/'):
            base_url = base_url[:-1]

        try:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=10.0, **self._http_options()) as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers=headers
                )

                if response.status_code != 200:
                    return []

                data = self._read_json(response)
                models = []

                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    if not model_id:
                        continue

                    mid = model_id.lower()
                    # Filter out non-chat models
                    if any(x in mid for x in ["embed", "whisper", "tts", "dall-e", "audio", "transcribe"]):
                        continue

                    models.append({
                        "id": f"{self.model_prefix}{model_id}",
                        "name": f"{model_id} [{name}]",
                        "provider": name
                    })

                return sorted(models, key=lambda x: x["name"])

        except Exception:
            return []

    async def validate_connection(self, url: str, api_key: str = "") -> Dict[str, Any]:
        """Validate connection to a custom endpoint."""
        if not url:
            return {"success": False, "message": "URL is required"}

        # Normalize URL
        if url.endswith('/'):
            url = url[:-1]

        try:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{url}/models",
                    headers=headers
                )

                if response.status_code == 200:
                    data = self._read_json(response)
                    if not isinstance(data.get("data"), list):
                        return {"success": False, "message": "接口未返回兼容的模型列表，请检查 Base URL（通常以 /v1 结尾）。"}
                    model_count = len(data["data"])
                    return {
                        "success": True,
                        "message": f"Connected successfully. Found {model_count} models."
                    }
                elif response.status_code == 401:
                    return {"success": False, "message": "Authentication failed. Check your API key."}
                else:
                    return {"success": False, "message": f"API error: {response.status_code}"}

        except httpx.ConnectError:
            return {"success": False, "message": "Connection failed. Check the URL."}
        except httpx.TimeoutException:
            return {"success": False, "message": "Connection timed out."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def validate_key(self, api_key: str) -> Dict[str, Any]:
        """Validate using stored URL."""
        _, base_url, _ = self._get_config()
        return await self.validate_connection(base_url, api_key)
