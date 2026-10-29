"""Six bounded real-model calls on a synthetic draft; no user history is changed."""
import asyncio
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
os.environ['AI_COUNSEL_DATA_DIR'] = str(Path(os.environ['LOCALAPPDATA']) / 'AICounselReview')
sys.path.insert(0, str(ROOT))
import httpx
from backend.council import get_provider_for_model
from backend.advisors import strip_consensus_tag
from backend.review_scoring import group_config, consume_score, build_score_report, score_markdown, combine_verdict

DRAFT = '''【合成测试稿，非用户正式文稿；含待拍画面】
标题：让AI替我看评论之前，我先让它做件小事

评论一多，我最怕的不是有人骂，是好几个不同的问题挤在一块，我看过了却没记住。
所以这次我不让AI冒充粉丝，也不让它替我决定选题。先做个小试验：把二十条公开样例评论分成几个主题，重复的问题收在一起，让我自己回去看原话。

打开这个本机页面，粘贴评论，点击整理。模型可以用已经装好的本地服务，也可以自己填兼容的API地址。选API时文本会发给你选择的服务；只有页面在自己电脑上，不代表模型也在本地。我这次用的是自己已有的服务，不推荐为了这件事先买电脑。
[录屏待拍：展示地址填写位置、整理按钮、分组结果和每条结果对应的原评论。]

我最想保留的是原话入口。比如“打不开”和“在哪下载”不一定是一个问题，一个可能是链接失效，一个可能压根没找到入口。它如果把两句都塞进“资源问题”，我还得点回去看，不能拿这个分类直接当观众结论。
[实测待补：相同二十条样例，记录人工整理和工具整理分别花多久、改了几处分类；未测完前不宣称省时比例。]

如果你只偶尔收到几条评论，直接看可能更快。我也不想把一个两分钟能做完的事折腾成半天工作流。等这次试完，真的能帮我少漏几个问题，我再决定要不要继续加功能。

你们来留言不是来给我训练一个听话的替身。工具先帮我把桌子收拾干净，最后该听谁的、下一期拍什么，还是我自己想。'''


async def main():
    bundle = json.loads((ROOT / 'desktop/role_bundle.json').read_text(encoding='utf-8'))
    with httpx.Client(base_url='http://127.0.0.1:3340', trust_env=False, timeout=20) as client:
        settings = client.get('/api/settings').json()
    model = settings['advisor_default_model']
    provider = get_provider_for_model(model)
    semaphore = asyncio.Semaphore(2)
    responses = []
    results = []
    personas = []
    for pid, persona in bundle['personas'].items():
        if pid != 'source-editor':
            personas.append(SimpleNamespace(id=pid, system_prompt=persona['system_prompt']))

    async def run(pid, persona):
        prompt = bundle['settings']['advisor_round1_prompt'].format(search_context_block='', question=DRAFT, consensus_tag='')
        prompt += '\n本次验证正文控制在450中文字以内；先给模拟短评，再给短备忘，仍附完整机器评分块。'
        async with semaphore:
            result = await provider.query(model, [{'role': 'system', 'content': persona['system_prompt']}, {'role': 'user', 'content': prompt}], timeout=150, temperature=0.6)
        if result.get('error'):
            raise RuntimeError(persona['name'] + ': ' + result.get('error_message', 'request failed'))
        clean, rating = consume_score(strip_consensus_tag(result['content']), group_config(persona['system_prompt']))
        responses.append({'persona_id': pid, 'review_rating': rating})
        results.append({'id': pid, 'name': persona['name'], 'content': clean, 'rating': rating})
        print(persona['name'] + ': ' + rating['status'], flush=True)

    await asyncio.gather(*(run(pid, p) for pid, p in bundle['personas'].items() if pid != 'source-editor'))
    report = build_score_report(personas, responses)
    transcript = '\n\n'.join(x['name'] + '\n' + x['content'] for x in results)
    prompt = bundle['settings']['advisor_verdict_prompt'].format(question=DRAFT, debate_arc='一轮合成样稿抽查，不是正式多轮审稿。', transcript=transcript)
    prompt += '\n\n程序计算表（无需重算，最终附表）：\n' + score_markdown(report)
    prompt += '\n主编正文控制在450中文字内。'
    chair = await provider.query(model, [{'role': 'system', 'content': bundle['personas']['source-editor']['system_prompt']}, {'role': 'user', 'content': prompt}], timeout=150, temperature=0.3)
    if chair.get('error'):
        raise RuntimeError(chair.get('error_message', 'chair failed'))
    chair_text = combine_verdict(chair['content'], report)
    final = {'usesRealModel': True, 'scope': 'five one-call simulated groups plus chair; synthetic draft only, not a full multi-round benchmark',
             'model': model, 'draft': DRAFT, 'results': results, 'scoreReport': report, 'chair': chair_text}
    (ROOT / 'build/group-voice-v4-real-check.json').write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding='utf-8')
    output = '合成样稿试审：用于查看新版语气，不是对用户正式文稿的审阅。\n\n' + DRAFT + '\n\n'
    output += '\n\n'.join(x['name'] + '\n' + x['content'] for x in results) + '\n\n主编\n' + chair_text
    (ROOT / 'dist/五团人味v4-合成稿试审.txt').write_text(output, encoding='utf-8')
    print(json.dumps({'calls': 6, 'completeScore': report['complete'], 'totalScore': report['score'], 'syntheticOnly': True}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
