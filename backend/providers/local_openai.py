"""A separate local OpenAI-compatible connection; never inherits cloud secrets."""
from .custom_openai import CustomOpenAIProvider
from ..settings import get_settings
from ..credentials import get_api_key


class LocalOpenAIProvider(CustomOpenAIProvider):
    model_prefix = 'local:'

    def _http_options(self):
        return {'trust_env': False, 'follow_redirects': False}

    def _get_config(self):
        settings = get_settings()
        return '本地模型', settings.local_model_url or '', get_api_key('local_model')
