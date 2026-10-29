"""Bounded v6 checks: five reviewers, chair and one contradiction; synthetic only."""
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

DRAFT='''【虚构待拍口播稿，只评稿面，本期讲方法不讲安装，不做模型评测】
我手上有一份已经核过事实的读书笔记，想把它做成60秒动画。可做完发现一句字幕不对，难道又得整条重来？今天就沿着同一个工程改一处给你看。
这次用Opus 5.5写动画代码，Remotion负责把代码渲染成视频。模型和渲染工具各干一件事。熟悉的客户端继续用，入口配置教程放在配套资料；正片只讲如何把要求说清楚，其他模型也能试，按各自输出调整。
以前只丢一句做得有科技感，结果全是文字飞来飞去。这次我先给具体任务：把已核实的笔记分成三章，每章20秒，总共60秒。先列每章讲什么，再要求用简笔图形表示关系；字幕、画面、配色、30帧横屏规格分别写清。
先让模型只出分镜，确认内容与画面后再生成工程；有不合适的先改分镜，别渲染完再从头推倒。
【待拍演示】展示接入位置，使用完整提示词；确认分镜，再生成工程、打开预览、导出。随后把第二章一处字幕改掉，展示同工程里其他内容保留，重新预览导出。旁白不挨个念按钮。资料含提示词、入口教程和示例工程。
所以最初那个问题，不用为了改一句话就默认重做整片，但每次修改后都要回预览确认。先从一条短动画的小改动做起，别把这个例子理解成任何复杂视频都能一句话改完。
如果你已经有讲清楚的稿，可以直接复用内容。只有两句想法时先写清楚，别期待工具替你证明事实。本期给的是一条可以检查、可以修改的方法，是否继续用由你决定。'''

async def main():
    bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
    assert bundle['version']==6
    output=ROOT/'build/discussion-v6-real-check';output.mkdir(exist_ok=True)
    model=get_settings().advisor_default_model
    assert model,'Configured model required'
    semaphore=asyncio.Semaphore(3)
    async def call(label,pid,draft,transcript=None):
        chair=pid=='source-editor'
        key='advisor_verdict_prompt' if chair else 'advisor_round1_prompt'
        prompt=bundle['settings'][key].format(question=draft,search_context_block='',consensus_tag='CONSENSUS_SCORE: 3',debate_arc='一次独立虚构稿抽查，以下为本轮实际生成意见。',transcript=transcript or '')
        async with semaphore:
            r=await query_model(model,[{'role':'system','content':bundle['personas'][pid]['system_prompt']},{'role':'user','content':prompt}],temperature=0.5,conversation_id=None)
        if r.get('error') or not r.get('content'):raise RuntimeError(label+': model call failed')
        text=r['content'];(output/(label+'.md')).write_text(text,encoding='utf-8')
        report={'case':label,'chars':len(text)}
        if not chair:
            blocks=re.findall(r'<review-comments>\s*([\s\S]*?)\s*</review-comments>',text)
            assert len(blocks)==1,label+' comments block'
            p=json.loads(blocks[0]);assert isinstance(p,dict) and isinstance(p['comments'],list)
            comments=p['comments'];cfg=group_config(bundle['personas'][pid]['system_prompt'])
            _,rating=consume_score(text,cfg);assert rating['status']=='ok',label+' rating'
            assert set(p['dimension_notes'])=={d['id'] for d in cfg['dimensions']}
            visible=text.split('<review-comments>')[0]
            assert all(c['text'] in visible for c in comments),'Unmatched comment text'
            ids=[]
            for c in comments:
                assert not c.get('reply_to') or c['reply_to'] in ids,'Invalid reply reference'
                ids.append(c['id'])
            norm=lambda s:re.sub(r'[\s“”"‘’*`_]','',s)
            report.update(commentCount=len(comments),replyCount=sum(bool(c.get('reply_to')) for c in comments),dimensionCount=len(p['dimension_notes']),score=rating['score'],allCommentQuotesPresent=all(norm(c.get('basis','')) in norm(draft) and c.get('basis') for c in comments),allDimensionQuotesPresent=all(norm(n.get('basis','')) in norm(draft) and n.get('basis') for n in p['dimension_notes'].values()),comments=comments,dimensionNotes=p['dimension_notes'])
        else:report['hasOpinionSelection']='各团意见的取舍' in text
        print(label+' finished',flush=True)
        return report,text
    if '--voice-only' in sys.argv:
        records=[r for r,_ in await asyncio.gather(*(call(pid+'-voice',pid,DRAFT) for pid in ['source-surfer','source-beginner']))]
        (output/'voice-results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'calls':len(records),'syntheticOnly':True,'historyWritten':False,'finalVoiceRefinement':True},ensure_ascii=False))
        return
    reviewed=await asyncio.gather(*(call(pid,pid,DRAFT) for pid in bundle['personas'] if pid!='source-editor'))
    transcript='\n\n'.join(bundle['personas'][r['case']]['name']+'\n'+text for r,text in reviewed)
    # Add an explicitly labelled erroneous candidate to verify the chair rejects it.
    transcript+='\n\n候选误读（待复核，不是事实）：技术团有人说全文没有交代模型名称，新手团有人说完全没安排修改演示。'
    chair,contradiction=await asyncio.gather(call('editor-selection','source-editor',DRAFT,transcript),call('tech-contradiction','source-tech',DRAFT.replace('每章20秒，总共60秒','每章固定30秒，总共60秒，章时长不能调整')))
    records=[r for r,_ in reviewed]+[chair[0],contradiction[0]]
    (output/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'calls':len(records),'syntheticOnly':True,'historyWritten':False,'commentCounts':[r['commentCount'] for r in records if 'commentCount' in r],'allProtocolsParsed':True},ensure_ascii=False))

if __name__=='__main__':asyncio.run(main())
