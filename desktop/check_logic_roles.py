"""Bounded real v9 logic probes on synthetic paragraphs; no history writes."""
import asyncio
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['AI_COUNSEL_DATA_DIR'] = str(Path(os.environ['LOCALAPPDATA']) / 'AICounselReview')
os.environ.setdefault('NO_PROXY', 'localhost,127.0.0.1,::1')
os.environ.setdefault('CUSTOM_REQUEST_TIMEOUT', '300')
from backend.council import query_model
from backend.review_scoring import consume_score, group_config
from backend.settings import get_settings

GOOD = '''【虚构口播稿，体验分享，稿面已规划演示】
第一段：我想把一篇已核实的短笔记变成动画，还想改一句字幕时不用从头来。这期只演示一份工程的小改动，不做工具横评，也不承诺复杂视频都能一键改好。
第二段：先不急着解释分镜是什么，等会给你看它长什么样。这里用Opus 5.5写动画代码，Remotion负责渲染，两个工具的分工不同。
第三段：【画面展示三格草图】分镜就是拍之前的镜头计划，这三格分别写开头、例子、结尾。看懂这张计划后，我再确认每格的内容与画面，然后生成工程。
第四段：【演示】打开工程预览，把第二格字幕改成核实后的表述，再次预览，导出。画面并排展示修改前后，其余两格保留。模型入口和基础安装放在配套资料。
第五段：这一次的例子说明，这份工程能局部修改；不能据此保证所有题材都不用重做。最初的问题在这一份工程里有了答案：改完要预览核对，先拿短稿试一处修改。'''
BAD = GOOD.replace('这一次的例子说明，这份工程能局部修改；不能据此保证所有题材都不用重做。', '这一次只试了一份工程改一句字幕，就证明任何题材、任何复杂度的视频都不需要重做，而且使用者从来不用检查结果。')
ORDER = '''【虚构口播稿，面向从未用过该工具的人，承诺可以按正片顺序跟做】
第一段：今天按这三步完成第一次动画导出，基础安装已经准备好。
第二段：第一步直接打开后台，填入刚才拿到的项目令牌。第二步绑定项目。第三步点导出。按顺序做到这里就完成了。
第三段：还没拿到项目令牌的人，现在才到前置步骤：必须先新建项目，再在项目页面申请令牌；没有令牌就不能绑定项目和导出。
第四段：这就是第一次导出的完整流程，按我刚才的顺序操作即可。'''

async def main():
    bundle = json.loads((ROOT / 'desktop/role_bundle.json').read_text(encoding='utf-8'))
    assert bundle['version'] == 9
    model = get_settings().advisor_default_model
    assert model
    out = ROOT / 'build/logic-v9-check'
    out.mkdir(exist_ok=True)
    started = time.monotonic()
    semaphore = asyncio.Semaphore(2)
    async def review(label, pid, draft, transcript=None):
        chair = pid == 'source-editor'
        key = 'advisor_verdict_prompt' if chair else 'advisor_round1_prompt'
        prompt = bundle['settings'][key].format(question=draft, search_context_block='', consensus_tag='CONSENSUS_SCORE: 3', debate_arc='一次虚构稿定向检查。', transcript=transcript or '')
        async with semaphore:
            result = await query_model(model, [{'role':'system','content':bundle['personas'][pid]['system_prompt']}, {'role':'user','content':prompt}], temperature=0.3 if chair else 0.85, conversation_id=None)
        assert not result.get('error') and result.get('content'), label + ': model did not return'
        content = result['content']
        (out / (label + '.md')).write_text(content, encoding='utf-8')
        record = {'case':label, 'persona':pid, 'draft':draft, 'content':content}
        if not chair:
            _, rating = consume_score(content, group_config(bundle['personas'][pid]['system_prompt']), draft)
            record['rating'] = rating
        print(json.dumps({'returned':label,'chars':len(content)}, ensure_ascii=False), flush=True)
        return record
    records = await asyncio.gather(review('resolved-later', 'source-thinker', GOOD), review('unsupported-conclusion', 'source-thinker', BAD), review('late-prerequisite', 'source-beginner', ORDER))
    transcript = '深度思考派的实际意见：\n' + records[1]['content'] + '\n\n候选误读（待复核，未证实）：第二段没有解释分镜，所以全文都没有解释分镜，也没有交代模型。'
    records.append(await review('chair-adjudication', 'source-editor', BAD, transcript))
    report = {'syntheticOnly':True, 'historyWritten':False, 'calls':len(records), 'elapsedSeconds':round(time.monotonic()-started), 'records':records}
    (out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'records'}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    asyncio.run(main())
