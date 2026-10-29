"""Blind synthetic quality ordering + repeat scoring; no user draft/history writes."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['AI_COUNSEL_DATA_DIR'] = str(Path(os.environ['LOCALAPPDATA']) / 'AICounselReview')
os.environ.setdefault('NO_PROXY','localhost,127.0.0.1,::1')
os.environ.setdefault('CUSTOM_REQUEST_TIMEOUT','300')
from backend.council import query_model
from backend.settings import get_settings
from backend.review_scoring import group_config, consume_score

CONTEXT = '''【虚构待拍口播稿，检查稿面质量】
面向会用网页聊天、第一次想整理观众评论的普通创作者。体裁是体验方法分享，不是安装课。下面的工具、功能、样例数量与计时均为虚构设定，不是现实产品测评。只判断其稿面解释和证据是否支持自己的结论，不外推真实平台效果。
'''
DRAFTS = {
 'weak': CONTEXT + '''评论多了怎么办？今天这款AI整理工具真的太强了。AI很强，效率也很高，我们一定要拥抱AI。让AI帮忙，才能跟上时代。
我先打开自己电脑上的网页，填上远程模型API地址，再把评论发给这个API。因为页面在本地，所以评论文字绝不会离开电脑，也不用担心发到哪里。
接下来把评论复制进去，点击开始，它就会帮我们整理。这一步真的很方便，整理得特别清楚，各种评论都会变成我们想要的结果。大家只要按这个方法来就能学会。
【画面：展示一个有三栏的表格，文字不指定】我只放了二十条评论，它分成了三类。有了分类我也不知道还能做什么，但大家一定很需要这个功能。
整个过程非常简单，非常方便，特别适合所有人。虽然我只做过这一组例子，但任何账号的一万条评论都能立刻整理正确，完全不用人工检查，效果都一样。
这就是本期分享。工具的价值就是它很厉害，只要拥抱工具，我们的效率就一定会提高。你还有什么看法，欢迎评论区留言。''',
 'middle': CONTEXT + '''评论多了，我会担心把几种不同问题混在一起。这次试一个办法：让AI先把二十条公开样例按主题分组，再由我回去看原话。本期只分享一次整理的思路，不保证能替所有账号决定选题。
页面在本机打开，模型用我已有的远程API，因此这二十条文字会发给所选服务。这次不上传私信，也不替观众回复。
【演示：打开页面、粘贴二十条评论，点击整理，展示分组表】工具把评论归到几个主题里，标题旁边留着原文入口。我会检查分组是不是合理，有不合适的自己改，不直接拿分组数量当观众投票。
这次我觉得找原话方便了一些，不过没有做人工和AI的同组计时，也没有给所有分类逐项打正确率。这是一次体验，能不能省时间要看评论数量和检查花多久。
步骤就是先选公开样例，整理，再看原话。原话留着，有问题就回去看。回去看以后再判断，自己判断以后再决定用不用。这个过程大体不复杂。
如果只收到三五条，直接读可能就够了。有一批内容反复被问时，可以拿公开样例试试。我这次用已有API，不推荐为了整理几条评论专门买设备，入口说明放配套资料。''',
 'strong': CONTEXT + '''“打不开”和“在哪下载”，你会把这两条放一类吗？我以前都记成资源问题，回头才发现：一个人拿到了失效链接，另一个人连入口都没找到。今天只试一件小事：整理二十条公开样例，还能随时找到原话。
【画面并列两条原话，用不同颜色标出失效和找不到入口】我先把这两条标在不同小类，准备拿它检查AI有没有偷懒归并。工具先帮我找线索，不能替我决定下一期拍什么。
本机打开的是网页，模型用我已有的远程API；点整理会把这些文字发到所选服务。这里只用公开样例，不导入私信或个人联系方式。入口和基础配置放资料，本期只演示怎么整理和核对。
【录屏：粘贴二十条，要求按具体需求分组，每项保留原文编号；展示结果及原文入口】你看，它还是把刚才两条放进同一类了。我点回编号，拆成链接失效和找不到入口，其他主题不跟着改。长按标题不能证明分类对，能回到原话才有办法纠正。
【画面：同一组二十条计时，人工2分钟；AI生成35秒，核对与调整2分钟】这次AI加核对反而多花35秒，所以不能说省时。我留下它，是因为回查重复问题方便；如果只是想读完二十条，这次直接看更快。接口还会产生调用费用，值不值得继续用得看自己的频率。
最后把改过的分类和原文并排保存。它分出的三类不是粉丝比例，也没证明哪期选题会火。评论少就直接读；需要回查时，先用一小组公开样例，留着原话核对。开头那两个人真正要解决的问题，也别再被合成一句“资源问题”了。'''
}

async def main():
    import httpx
    with httpx.Client(base_url='http://127.0.0.1:3340',trust_env=False,timeout=20) as client:
        history=client.get('/api/conversations').raise_for_status().json()
        assert not any(client.get('/api/conversations/'+h['id']+'/progress').raise_for_status().json().get('active') for h in history), 'Wait until the user review finishes before synthetic API probes'
    bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
    assert bundle['version']==10
    settings=get_settings();model=settings.advisor_default_model
    assert model
    run=sys.argv[1] if len(sys.argv)>1 else 'run1'
    assert run.isalnum()
    out=ROOT/'build/anchored-v10-check'/run;out.mkdir(parents=True,exist_ok=True)
    semaphore=asyncio.Semaphore(2);started=time.monotonic();records=[]
    async def call(case,pid,draft,repeat=False,transcript=''):
        chair=pid=='source-editor'
        key='advisor_verdict_prompt' if chair else 'advisor_round1_prompt'
        prompt=bundle['settings'][key].format(question=draft,search_context_block='',consensus_tag='请在末尾附CONSENSUS_SCORE: 1至5的整数，和稿件评分独立。',debate_arc='仅汇总此稿本轮实际五团意见。',transcript=transcript)
        async with semaphore:
            result=await query_model(model,[{'role':'system','content':bundle['personas'][pid]['system_prompt']},{'role':'user','content':prompt}],temperature=.3 if chair else settings.advisor_temperature,conversation_id=None)
        content=result.get('content') or ''
        record={'case':case,'persona_id':pid,'repeat':repeat,'draft':draft,'content':content,'error':result.get('error_message') if result.get('error') else None,
                'promptSha256':hashlib.sha256(bundle['personas'][pid]['system_prompt'].encode()).hexdigest()}
        if not chair:
            _,rating=consume_score(content,group_config(bundle['personas'][pid]['system_prompt']),draft)
            record['review_rating']=rating
        records.append(record)
        label=case+'-'+pid+('-repeat' if repeat else '')
        (out/(label+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'returned':label,'score':record.get('review_rating',{}).get('score'),'status':record.get('review_rating',{}).get('status'),'error':bool(record['error'])},ensure_ascii=False),flush=True)
        return record
    ids=[pid for pid in bundle['personas'] if pid!='source-editor']
    final='--final' in sys.argv
    jobs=([('middle',pid) for pid in ids]+[('strong',pid) for pid in ['source-surfer','source-beginner']]) if final else [(case,pid) for case in DRAFTS for pid in ids]
    await asyncio.gather(*(call(case,pid,DRAFTS[case]) for case,pid in jobs))
    repeat_ids=[] if final else ids
    await asyncio.gather(*(call('middle',pid,DRAFTS['middle'],True) for pid in repeat_ids))
    transcript='\n\n'.join(bundle['personas'][r['persona_id']]['name']+'\n'+r['content'] for r in records if r['case']=='middle' and not r['repeat'])
    await call('chair-middle','source-editor',DRAFTS['middle'],transcript=transcript)
    matrix={case:{r['persona_id']:r['review_rating'].get('score') for r in records if r['case']==case and not r['repeat'] and 'review_rating' in r} for case in DRAFTS}
    repeat_deltas={pid:abs(matrix['middle'][pid]-next(r['review_rating']['score'] for r in records if r['persona_id']==pid and r['repeat'])) if matrix['middle'].get(pid) is not None and next(r['review_rating'].get('score') for r in records if r['persona_id']==pid and r['repeat']) is not None else None for pid in repeat_ids}
    weights={'source-tech':25,'source-practical':30,'source-surfer':15,'source-thinker':10,'source-beginner':20}
    totals={case:round(sum(values[p]*weights[p]/100 for p in ids),2) if all(values.get(p) is not None for p in ids) else None for case,values in matrix.items()}
    summary={'syntheticOnly':True,'historyWritten':False,'calls':len(records),'elapsedSeconds':round(time.monotonic()-started),'matrix':matrix,'weightedScores':totals,'repeatDeltas':repeat_deltas,
             'allNumericLedgerAuditsPassed':all(r['review_rating']['status']=='ok' for r in records if 'review_rating' in r),
             'limitations':'Designed contrast cases, not human-rated ground truth or evidence of universal objectivity. Case labels are not included in model prompts.'}
    (out/'results.json').write_text(json.dumps({'summary':summary,'records':records},ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':asyncio.run(main())
