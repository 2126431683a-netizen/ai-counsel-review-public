"""Small real-model contrast, synthetic material only; no conversation writes."""
import asyncio
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
os.environ['AI_COUNSEL_DATA_DIR']=str(Path(os.environ['LOCALAPPDATA'])/'AICounselReview')
os.environ.setdefault('NO_PROXY','localhost,127.0.0.1,::1')
from backend.council import query_model
from backend.settings import get_settings
from backend.review_scoring import consume_score,group_config

CONTEXT='''【虚构待拍口播稿与明确时间段】
观众是会用聊天工具、需要整理公开反馈的小创作者。小舟为完全虚构的AI分组工具，以下价格、计时与功能均为虚构设定，不核验真实产品。是方法体验分享，不是安装教程。品牌合作仅在明确标注时成立。时间段为本次测试给定，不是预测。按实际稿面评价。
'''
BODY='''
【20–50秒】我选了二十条自造公开反馈，先把昵称删掉。提示词要求按“听不懂术语、想看完整例子、没找到入口”分组，不确定的单放，必须保留每条编号。画面同时展示原句：“节点是什么？”、“能把从头做完那次留下吗？”、“入口在哪一页？”。
【50–80秒】画面把第一句放到术语组，第二句放到完整案例组，第三句放到入口组，再显示编号与原句对照。它把“入口在哪一页”错放进了案例组，我按编号改回入口组，没有删掉这个错例。分组只是初筛，不能据此说多数观众都不喜欢这期。
【80–110秒】我据此决定下一期先演示一次完整案例，术语在第一次出现时解释，入口留画面标记。为了检查这不是多此一举，我安排对同样二十句手动分一遍，画面并排显示两次计时和修改次数；这里的具体计时在拍摄时再填，不预先说省了百分之多少。
【110–140秒】本例只演示小舟的分组方案，不代表其他工具更差。二十条自己扫一眼可能更快，量大且要反复找原句时编号对照才有用。若你需要处理私密客户资料，先看自己所选服务的数据流向，别把本机网页当成离线保证。结尾留下分组规则，不购买也能手工照着整理。
'''
OPEN_GOOD='''【0–15秒】同一句“没看懂”，有人缺术语解释，有人想看完整操作。混成一类，下期就容易改错方向。我拿二十条样例演示怎么保留原句再分组。
【15–20秒】先看这两句：节点是什么？能把从头做完那次留下吗？它们需要的补充不是一回事。
'''
OPEN_BAD='''【0–15秒】大家好欢迎来到我的频道。今天给大家分享一个非常实用的内容。现在AI发展越来越快，各种工具层出不穷，我们要跟上这个时代。
【15–20秒】今天这个方法非常值得关注，真的很方便。记得看到最后，我们接下来慢慢讲。
'''
NATIVE='''【合作说明】本期为虚构小舟品牌合作，保留真实局限与错例。中段演示使用小舟，分组规则与原句对照方法可手工复用；没有优惠倒计时和必须购买的要求。
'''
HARD='''【合作说明】本期为虚构小舟品牌合作。
【插入50秒与80秒之间的30秒推广段】小舟就是最强选择，所有创作者都离不开！效率革命，效果炸裂，不需要考虑别的选择。限时最后一天，马上去链接购买，错过就亏了。为什么强？就是领先，就是快，就是人人必备！记住小舟，认准小舟，下单小舟，别再犹豫！
'''

async def main():
    import httpx
    with httpx.Client(base_url='http://127.0.0.1:3340',trust_env=False,timeout=20) as c:
        hs=c.get('/api/conversations').raise_for_status().json()
        assert not any(c.get('/api/conversations/'+h['id']+'/progress').raise_for_status().json().get('active') for h in hs)
    b=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'));assert b['version']==11
    out=ROOT/'build/opening-v11-probes';out.mkdir(exist_ok=True)
    settings=get_settings();sem=asyncio.Semaphore(2);started=time.monotonic()
    async def call(label,opening,ad):
        draft=CONTEXT+opening+BODY+ad
        pid='source-surfer';role=b['personas'][pid]
        prompt=b['settings']['advisor_round1_prompt'].format(question=draft,search_context_block='',consensus_tag='最后附CONSENSUS_SCORE: 3（共识信号，与稿分无关）')
        async with sem:
            r=await query_model(settings.advisor_default_model,[{'role':'system','content':role['system_prompt']},{'role':'user','content':prompt}],temperature=settings.advisor_temperature,conversation_id=None)
        text=r.get('content') or '';_,rating=consume_score(text,group_config(role['system_prompt']),draft)
        record={'case':label,'persona_id':pid,'draft':draft,'content':text,'error':bool(r.get('error')),'rating':rating}
        (out/(label+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'case':label,'status':rating['status'],'score':rating.get('score'),'axes':{d['id']:d['score'] for d in rating['dimensions']}},ensure_ascii=False),flush=True)
        return record
    noncommercial='--noncommercial' in sys.argv
    records=await asyncio.gather(call('D',OPEN_GOOD,'')) if noncommercial else await asyncio.gather(call('A',OPEN_GOOD,NATIVE),call('B',OPEN_GOOD,HARD),call('C',OPEN_BAD,NATIVE))
    summary={'syntheticOnly':True,'calls':len(records),'historyWrites':False,'elapsedSeconds':round(time.monotonic()-started),'results':[{'case':r['case'],'status':r['rating']['status'],'score':r['rating'].get('score'),'axes':{d['id']:d['score'] for d in r['rating']['dimensions']}} for r in records], 'limits':'Designed contrasts, single group/single run; no human score truth, no causal retention measurements.'}
    (out/('noncommercial-summary.json' if noncommercial else 'summary.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':asyncio.run(main())
