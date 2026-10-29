"""One synthetic real-model call; verifies comment/detail pairing without saving history."""
import asyncio
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
os.environ['AI_COUNSEL_DATA_DIR'] = str(Path(os.environ['LOCALAPPDATA']) / 'AICounselReview')
sys.path.insert(0, str(ROOT))
import httpx
from backend.council import get_provider_for_model


async def main():
    bundle = json.loads((ROOT / 'desktop/role_bundle.json').read_text(encoding='utf-8'))
    with httpx.Client(base_url='http://127.0.0.1:3340', trust_env=False, timeout=20) as client:
        model = client.get('/api/settings').json()['advisor_default_model']
    draft = '''【独立合成测试稿，非正式文稿】
我想让AI替我整理读书笔记。打开本机页面，把笔记粘进去，点整理，结果会按主题列出来。
第一次使用需要先配置模型：本地服务与自定义API都能用，选择API会把笔记发到你选的服务。
我会保留每条结果对应的原文，分类拿不准就回去核对，不把AI标签当成原书结论。
[录屏待拍：模型设置入口、整理按钮、分类结果与原文跳转。]
[实测待补：同一批二十条笔记，分别记录人工与工具处理耗时；测完前不宣称省时比例。]
如果你只有三两条笔记，直接整理可能更快。这个小工具先替我收拾桌面，最后哪些内容值得留，还是我自己挑。'''
    prompt = bundle['settings']['advisor_round1_prompt'].format(search_context_block='', question=draft, consensus_tag='')
    prompt += '\n本次为界面协议抽查：输出至多2条自然短评，备忘简短；仍遵守逐条说明块和评分块协议。'
    response = await get_provider_for_model(model).query(model, [
        {'role': 'system', 'content': bundle['personas']['source-beginner']['system_prompt']},
        {'role': 'user', 'content': prompt},
    ], timeout=150, temperature=0.5)
    if response.get('error'):
        raise RuntimeError('Synthetic review request failed; inspect provider status locally.')
    content = response['content']
    blocks = re.findall(r'<review-comments>\s*([\s\S]*?)\s*</review-comments>', content)
    assert len(blocks) == 1, 'Expected one comment-details block'
    comments = json.loads(blocks[0])
    assert isinstance(comments, list) and comments, 'Expected at least one paired comment'
    visible = content.split('<review-comments>')[0]
    normalize = lambda s: re.sub(r'[\s*_`“”"‘\u2019\u0027]', '', s)
    assert all(c.get('text') and normalize(c['text']) in normalize(visible) for c in comments)
    assert all(isinstance(c.get(k), str) for c in comments for k in ('basis', 'rationale', 'limits', 'next_step'))
    result = {'scope': 'one synthetic call, no user manuscript/history', 'content': content,
              'comments': comments, 'pairsValid': True, 'calls': 1}
    (ROOT / 'build/review-details-real-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'calls': 1, 'pairedComments': len(comments), 'pairsValid': True, 'syntheticOnly': True}))


if __name__ == '__main__':
    asyncio.run(main())
