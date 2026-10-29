"""Same synthetic manuscript, paired voice checks; never write conversation history."""
import asyncio
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['AI_COUNSEL_DATA_DIR'] = str(Path(os.environ['LOCALAPPDATA']) / 'AICounselReview')
from backend.council import query_model
from backend.settings import get_settings
from backend.review_scoring import group_config, consume_score
from desktop.check_discussion_roles import DRAFT

OUTPUT = ROOT / 'build/viewer-v7-check'
OUTPUT.mkdir(exist_ok=True)
bundle = json.loads((ROOT / 'desktop/role_bundle.json').read_text(encoding='utf-8'))
before = json.loads((ROOT / 'build/voice-v7-before.json').read_text(encoding='utf-8'))
semaphore = asyncio.Semaphore(3)

async def call(label, persona, settings, temp, draft=DRAFT, transcript='', followup=False):
    chair = persona['name'] == bundle['personas']['source-editor']['name']
    key = 'advisor_verdict_prompt' if chair else 'advisor_followup_prompt' if followup else 'advisor_round1_prompt'
    prompt = settings[key].format(question=draft, search_context_block='',
        consensus_tag='Give CONSENSUS_SCORE: n (0-5) on its own line at the end.',
        debate_arc='一次虚构稿审阅，下面是实际收到的输出。', transcript=transcript,
        cross_pollination_extract='候选意见仅供复核，不是原稿事实。', round_number=2, previous_round_number=1)
    async with semaphore:
        result = await query_model(get_settings().advisor_default_model,
            [{'role':'system','content':persona['system_prompt']}, {'role':'user','content':prompt}],
            temperature=temp, timeout=240, conversation_id=None)
    if result.get('error') or not result.get('content'):
        raise RuntimeError(label + ': model returned no usable content')
    content = result['content']
    (OUTPUT / (label+'.md')).write_text(content, encoding='utf-8')
    record = {'case':label,'temperatureSent':temp,'chars':len(content),'persona':persona['name']}
    if not chair:
        blocks = re.findall(r'<review-comments>\s*([\s\S]*?)\s*</review-comments>',content)
        assert len(blocks)==1, label+' comment block'
        payload = json.loads(blocks[0])
        comments = payload['comments']
        cfg = group_config(persona['system_prompt'])
        _, rating = consume_score(content, cfg)
        assert rating['status']=='ok', label+' score protocol'
        assert set(payload['dimension_notes'])=={x['id'] for x in cfg['dimensions']}, label+' dimensions'
        assert all(c['text'] in content.split('<review-comments>')[0] for c in comments), label+' visible texts'
        ids=[]
        for c in comments:
            assert not c.get('reply_to') or c['reply_to'] in ids, label+' reply order'
            ids.append(c['id'])
        norm=lambda x:re.sub(r'[\s“”"‘’*`_]','',x)
        notes = comments + list(payload['dimension_notes'].values())
        assert all(x.get('basis') and norm(x['basis']) in norm(draft) for x in notes), label+' basis presence'
        assert all(not x.get('context') or norm(x['context']) in norm(draft) for x in notes), label+' context presence'
        record.update(comments=comments,dimensionNotes=payload['dimension_notes'],score=rating['score'],
            commentCount=len(comments),lengths=[len(c['text']) for c in comments],allQuotesPresent=True)
        print(json.dumps({'case':label,'comments':[c['text'] for c in comments]},ensure_ascii=False),flush=True)
    else:
        record['hasOpinionSelection']='各团意见的取舍' in content
        print(label+' finished',flush=True)
    (OUTPUT/(label+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return record,content

async def main():
    failures=[]
    if '--safeguards' in sys.argv:
        outputs=[(p,json.loads((OUTPUT/(p+'.json')).read_text(encoding='utf-8'))) for p in bundle['personas'] if p!='source-editor']
        transcript='\n\n'.join(r['persona']+'\n'+(OUTPUT/(p+'.md')).read_text(encoding='utf-8') for p,r in outputs)
        transcript+='\n\n待复核的候选误读：有人说全文没写模型名称，也没安排修改字幕的演示。'
        followup_transcript=transcript
        records=await asyncio.gather(
            call('tech-contradiction',bundle['personas']['source-tech'],bundle['settings'],.85,DRAFT.replace('每章20秒，总共60秒','每章固定30秒，总共60秒，章时长不能调整')),
            call('editor-selection',bundle['personas']['source-editor'],bundle['settings'],.3,transcript=transcript),
            call('practical-followup',bundle['personas']['source-practical'],bundle['settings'],.85,transcript=followup_transcript,followup=True))
    else:
        tasks=[]
        for pid in ['source-practical','source-surfer']:
            role=next(x for x in before['personas'] if x['name']==bundle['personas'][pid]['name'])
            if not (OUTPUT/(pid+'-before.json')).exists():
                tasks.append(call(pid+'-before',role,before['settings'],before['settings']['advisor_temperature']))
        role=next(x for x in before['personas'] if x['name']==bundle['personas']['source-practical']['name'])
        if not (OUTPUT/'practical-temperature-only.json').exists():
            tasks.append(call('practical-temperature-only',role,before['settings'],.85))
        for pid, role in bundle['personas'].items():
            if pid!='source-editor':
                tasks.append(call(pid,role,bundle['settings'],.85))
        results=await asyncio.gather(*tasks,return_exceptions=True)
        failures=[str(x) for x in results if isinstance(x,Exception)]
        records=[x for x in results if not isinstance(x,Exception)]
        if failures:
            (OUTPUT/'failures.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'failures':failures},ensure_ascii=False),flush=True)
    summary={'calls':len(records),'syntheticOnly':True,'historyWritten':False,'failures':failures,'checks':[r for r,_ in records]}
    name='safeguards.json' if '--safeguards' in sys.argv else 'paired-results.json'
    (OUTPUT/name).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'calls':len(records),'allProtocolsAndQuotesValid':not failures,'historyWritten':False},ensure_ascii=False))
    if failures:
        raise SystemExit(1)

if __name__=='__main__':
    asyncio.run(main())
