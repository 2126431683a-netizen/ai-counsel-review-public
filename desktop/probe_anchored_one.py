"""A final-format synthetic reviewer probe; preserve the original exploratory output."""
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from desktop.check_anchored_roles import DRAFTS
from backend.settings import get_settings
from backend.council import query_model
from backend.review_scoring import group_config,consume_score

async def main():
    bundle=json.loads((ROOT/'desktop/role_bundle.json').read_text(encoding='utf-8'))
    settings=get_settings();pid='source-practical';draft=DRAFTS['middle']
    prompt=bundle['settings']['advisor_round1_prompt'].format(question=draft,search_context_block='',consensus_tag='请在末尾附CONSENSUS_SCORE: 1至5的整数，和稿件评分独立。')
    result=await query_model(settings.advisor_default_model,[{'role':'system','content':bundle['personas'][pid]['system_prompt']},{'role':'user','content':prompt}],temperature=settings.advisor_temperature,conversation_id=None)
    content=result.get('content') or ''
    _,rating=consume_score(content,group_config(bundle['personas'][pid]['system_prompt']),draft)
    record={'case':'middle','persona_id':pid,'repeat':False,'draft':draft,'content':content,'review_rating':rating,
            'error':result.get('error_message'),'promptSha256':hashlib.sha256(bundle['personas'][pid]['system_prompt'].encode()).hexdigest(),'syntheticOnly':True}
    (ROOT/'build/anchored-v10-check/final/practical-format-smoke.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':rating['status'],'score':rating.get('score'),'issues':rating.get('evidence_issues'),'error':record['error']},ensure_ascii=False))

if __name__=='__main__':asyncio.run(main())
