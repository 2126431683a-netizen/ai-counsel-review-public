"""Execute the established isolated protocol harness with v11 evidence fixtures."""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
source = (root/'desktop/verify_runtime.py').read_text(encoding='utf-8')
source = source.replace('import httpx', 'import httpx\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parent.parent))\nfrom backend.review_scoring import group_config')
needle = '        elif (chair_prompt and system == chair_prompt)'
insert = '''
            cfg = group_config(system)
            no_ad = self.path == '/api/chat'
            scores = {d['id']: None if no_ad and d['id']=='commercial' else 2 if d['id']=='commercial' else 6 if d['id']=='opening' else 8 for d in cfg['dimensions']}
            notes = {d['id']: {'basis':'每天节省十小时','context':'','rationale':'本地协议夹具，不是模型质量评估','deduction':'夹具预置差距','checks':[{'id':key,'score':scores[d['id']]/2,'basis':'每天节省十小时','rationale':'本地协议夹具','gap':'夹具预置差距'} for key in ['a','b']]} for d in cfg['dimensions'] if scores[d['id']] is not None}
            text = role+'验收意见：原句“每天节省十小时”缺乏来源，建议补充样本与计算口径。'
            metadata = {'comments':[{'id':'c1','text':text,'basis':'每天节省十小时','rationale':'本地协议夹具','kind':'确定问题'}],'dimension_notes':notes}
            content=text+'\\n<review-comments>'+json.dumps(metadata,ensure_ascii=False)+'</review-comments>\\n<review-score>'+json.dumps({'scores':scores,'unrated_reasons':{'commercial':'不适用：本地非商业协议夹具'} if no_ad else {}},ensure_ascii=False)+'</review-score>\\nCONSENSUS_SCORE: 2'
'''
assert needle in source
source = source.replace(needle, insert+needle)
source = source.replace('        settings = client.get("/api/settings").json()', '''        assert client.get('/api/health').json()['features']['review_opening_commercial']==1
        settings = client.get("/api/settings").json()''')
source = source.replace('                assert all(not item.get("error") for item in round_data["responses"])', '''                assert all(not item.get("error") for item in round_data["responses"])
                for item in round_data['responses']:
                    rating=item['review_rating']
                    assert rating['status']=='ok',rating
                    assert rating['coverage']==(75 if provider=='ollama' else 100)
                    assert rating['score']==(7.6 if provider=='ollama' else 6.2),rating
                    assert len(rating['dimensions'])==5
                report=round_data['review_score'] if 'review_score' in round_data else None
                if report: assert report['complete']
''')
# Current prompts prohibit rewriting in role instructions rather than this old exact phrase.
source = source.replace('assert "不要改写句子或生成替代文案" in first_round[0]["user"]', 'assert "review" in role_prompts[role_names[0]]')
source = source.replace('"htmlConsoleErrorExplained": args.check_html', '"htmlConsoleErrorExplained": args.check_html, "v11FiveAxesValidated":True, "commercialNAValidated":True')
source = source.replace('first_round = [c for c in reviewers if "这是独立审稿轮" in c["user"] or "这是独立审阅轮" in c["user"]]', 'first_round = reviewers[:len(role_names)]\n            assert set(c["role"] for c in first_round)==set(role_names)')
source = source.replace('build/fixture-calls.json', 'build/v11-fixture-calls.json')
exec(compile(source, str(root/'desktop/verify_runtime.py'), 'exec'))
