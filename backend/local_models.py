"""Explicit local discovery and use, with no writes during detection."""
import ipaddress
from urllib.parse import urlsplit, urlunsplit
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal, Optional
from .settings import get_settings, update_settings
from .credentials import get_api_key, set_secret, delete_secret
from .providers.custom_openai import CustomOpenAIProvider

router = APIRouter(prefix='/api/local-models', tags=['Local models'])


class LocalRequest(BaseModel):
    service: Literal['ollama', 'lmstudio', 'openai'] = 'ollama'
    url: str = ''
    api_key: Optional[str] = None
    model: Optional[str] = None


def normalize_url(raw, service):
    value = raw.strip() or ('http://127.0.0.1:11434' if service == 'ollama' else 'http://127.0.0.1:1234/v1')
    if '://' not in value:
        value = 'http://'+value
    parsed = urlsplit(value)
    if parsed.scheme not in ['http', 'https'] or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('请填写本机服务地址，不要在地址中放密钥或参数。')
    host = parsed.hostname or ''
    if host != 'localhost':
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError()
        except ValueError:
            raise ValueError('此入口连接本机服务，请使用localhost或127.0.0.1；其他服务仍可在API设置中配置。') from None
    _ = parsed.port  # Reject malformed port numbers.
    path = parsed.path.rstrip('/')
    if service == 'ollama':
        if path in ['/api', '/api/tags', '/api/chat']:
            path = ''
        if path:
            raise ValueError('Ollama只需服务根地址，例如http://127.0.0.1:11434。')
    else:
        for suffix in ['/chat/completions', '/models']:
            if path.endswith(suffix):
                path = path[:-len(suffix)]
        path = path or '/v1'
    return urlunsplit((parsed.scheme, parsed.netloc, path, '', ''))


def token_for(request, url):
    if request.service == 'ollama':
        return ''
    if request.api_key is not None:
        return request.api_key.strip()
    return get_api_key('local_model') if get_settings().local_model_url == url else ''


async def inspect(request):
    try:
        url = normalize_url(request.url, request.service)
        headers = {}
        token = token_for(request, url)
        if token:
            headers['Authorization'] = 'Bearer '+token
        endpoint = '/api/tags' if request.service == 'ollama' else '/models'
        async with httpx.AsyncClient(timeout=5, trust_env=False, follow_redirects=False) as client:
            response = await client.get(url+endpoint, headers=headers)
        if response.status_code in [401, 403]:
            return {'success': False, 'message': '本地服务要求访问密钥，请在“修改地址或填写密钥”中填写后重试。', 'models': []}
        if response.status_code != 200:
            return {'success': False, 'message': '服务没有返回模型列表，请检查地址，以及是否已打开本地API服务。', 'models': []}
        data = CustomOpenAIProvider._read_json(response)
        values = data.get('models' if request.service == 'ollama' else 'data')
        if not isinstance(values, list):
            raise ValueError('服务返回的模型列表格式不兼容，请确认选择了对应的软件。')
        models = []
        seen = set()
        prefix = 'ollama:' if request.service == 'ollama' else 'local:'
        for item in values:
            if not isinstance(item, dict):
                continue
            name = item.get('name') if request.service == 'ollama' else item.get('id')
            if not isinstance(name, str) or not name.strip() or name in seen:
                continue
            if any(word in name.lower() for word in ['embed', 'whisper', 'tts', 'dall-e', 'transcribe']):
                continue
            seen.add(name)
            models.append({'id': prefix+name, 'name': name, 'provider': 'Ollama' if request.service == 'ollama' else '本地模型'})
        return {'success': True, 'url': url, 'models': models, 'message': f'找到{len(models)}个聊天模型。' if models else '服务已打开，但还没有聊天模型。请先在本地软件中下载一个聊天模型。'}
    except (httpx.ConnectError, httpx.TimeoutException):
        name = 'Ollama' if request.service == 'ollama' else 'LM Studio' if request.service == 'lmstudio' else '本地模型软件'
        return {'success': False, 'models': [], 'message': f'暂时连接不上。请先打开{name}的本地服务，再点检测。'}
    except (ValueError, httpx.HTTPError):
        return {'success': False, 'models': [], 'message': '地址或服务响应不正确。请使用本机地址；LM Studio需开启Developer中的服务。'}


@router.post('/check')
async def check(request: LocalRequest):
    return await inspect(request)


@router.post('/use')
async def use(request: LocalRequest):
    result = await inspect(request)
    if not result['success']:
        return result
    if request.model not in {m['id'] for m in result['models']}:
        return {'success': False, 'message': '请先检测，再选择列表中的一个聊天模型。', 'models': result['models']}
    # Refresh settings after the network await; don't overwrite concurrent edits.
    settings = get_settings()
    provider = 'ollama' if request.service == 'ollama' else 'local'
    updates = {'enabled_providers': {**settings.enabled_providers, provider: True},
               'advisor_default_model': request.model, 'advisor_tiebreaker_model': request.model}
    if provider == 'ollama':
        updates['ollama_base_url'] = result['url']
    else:
        token = token_for(request, result['url'])
        if token:
            set_secret('api:local_model', token)
        else:
            delete_secret('api:local_model')
        updates['local_model_url'] = result['url']
    update_settings(**updates)
    return {**result, 'model': request.model, 'message': '已用于当前审稿团和主编，可以返回开始审稿。列表连接正常，实际推理会在审稿时检查。'}


@router.get('')
async def saved_models():
    settings = get_settings()
    if not settings.local_model_url or not settings.enabled_providers.get('local'):
        return {'models': []}
    # Revalidate the stored address before a model-list request.
    return await inspect(LocalRequest(service='openai', url=settings.local_model_url))
