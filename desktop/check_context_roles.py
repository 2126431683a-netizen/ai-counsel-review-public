"""Optional real-model checks use synthetic manuscripts only and save no history."""
import asyncio
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
os.environ['AI_COUNSEL_DATA_DIR']=str(Path(os.environ['LOCALAPPDATA'])/'AICounselReview')
from backend.council import query_model
from backend.settings import get_settings
from backend.review_scoring import group_config,consume_score

bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
assert bundle['version']==5
manuscript='''【虚构口播稿，待拍录屏，审核稿面安排；本期不做模型评测或安装部署课】
今天把一份已核实的读书笔记变成动画。先问：做出来以后还能改吗？后面会演示。
我们用Claude的Opus 5.5负责写动画代码，Remotion负责把代码渲染成视频。这次重点讲怎么写清提示词。熟悉的客户端可继续用；需要配置的观众可看随视频提供的入口教程。其他模型也能尝试，效果可能差一点，按各自输出调整。
提示词分五部分：负责什么、视频讲什么、章节内容、具体风格、输出规格。先让模型只写分镜，保留原文事实；确认内容和画面没有问题后再创建工程。
整条60秒，分3章，每章20秒。风格用简笔图形，字幕跟画面同步，中文，横屏，30帧。
【已规划待拍演示】展示本次客户端与接入入口，使用以上完整提示词；确认分镜，创建工程；在同一工程中打开预览，导出视频。接着把第二章字幕改一处，重新预览并导出，说明其他内容保留。本段由录屏承接，旁白不逐个念按钮。配套资料包含完整提示词、入口教程、示例工程。
所以开头问的能不能改：可以继续提出具体改动，回看预览确认再导出。先小处改，别盲目一次重做。今天先把这个流程看懂，下次自己换一份笔记试试。'''
contradiction=manuscript.replace('整条60秒，分3章，每章20秒','总时长140秒，分10章，每章固定20秒，不得调整每章时长')

async def main():
    settings=get_settings()
    model=settings.advisor_default_model
    if not model:raise RuntimeError('No configured model')
    output=ROOT/'build/context-v5-real-check'
    output.mkdir(exist_ok=True)
    semaphore=asyncio.Semaphore(4)
    async def call(label,pid,question,chair=False):
        template=bundle['settings']['advisor_verdict_prompt'] if chair else bundle['settings']['advisor_round1_prompt']
        prompt=template.format(search_context_block='',question=question,consensus_tag='最后附CONSENSUS_SCORE: 3',debate_arc='候选意见可能有误',transcript='技术团说“全文没给模型名称”，新手团说“完全没有操作和修改演示”，思考团说“作者把事实判断完全交给AI”。以上都只是待复核的模拟意见。')
        async with semaphore:
            result=await query_model(model,[{'role':'system','content':bundle['personas'][pid]['system_prompt']},{'role':'user','content':prompt}],temperature=0.2,conversation_id=None)
        if result.get('error') or not result.get('content'):raise RuntimeError(label+': model request failed')
        text=result['content']
        (output/(label+'.md')).write_text(text,encoding='utf-8')
        clean=text.split('<review-comments>')[0]
        record={'case':label,'chars':len(text),'visible':clean}
        if not chair:
            matches=re.findall(r'<review-comments>\s*([\s\S]*?)\s*</review-comments>',text)
            assert len(matches)==1,label+' missing comment protocol'
            comments=json.loads(matches[0])
            assert isinstance(comments,list)
            record['comments']=comments
            cfg=group_config(bundle['personas'][pid]['system_prompt'])
            _,rating=consume_score(text,cfg)
            record['rating']=rating
        print(label+' finished',flush=True)
        return record
    jobs=[call(pid+'-answered',pid,manuscript) for pid in bundle['personas'] if pid!='source-editor']
    jobs += [call('tech-real-contradiction','source-tech',contradiction),call('editor-reject-misreads','source-editor',manuscript,True)]
    if '--minimal-only' in sys.argv:
        minimal=manuscript.split('【已规划待拍演示】')[0]+'【演示待拍】接下来在同一案例里创建工程并演示，具体录屏还没拍。结尾说明允许回到工程提出具体改动，本期完整提示词与资料在评论区。'
        # Do not instantiate the unused coroutine jobs when running this case only.
        for job in jobs: job.close()
        jobs=[call('tech-minimal-demo','source-tech',minimal),call('editor-minimal-demo','source-editor',minimal,True)]
    records=await asyncio.gather(*jobs)
    result_file='minimal-results.json' if '--minimal-only' in sys.argv else 'results.json'
    (output/result_file).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'calls':len(records),'syntheticOnly':True,'historyWritten':False,'reviewerProtocolsParsed':sum('comments' in r for r in records)},ensure_ascii=False))

asyncio.run(main())
