"""Refresh the existing bounded public Bilibili sample; no login/profile metadata."""
import asyncio
from collections import Counter
import datetime as dt
import hashlib
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'desktop/comment-evidence-v10'
OUT.mkdir(exist_ok=True)
OLD = json.loads((ROOT / 'desktop/comment-evidence-v3/sample.json').read_text(encoding='utf-8'))
CUTOFF = int(dt.datetime(2026, 10, 16, 23, 59, 59, tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp())

async def main():
    semaphore = asyncio.Semaphore(2)
    async with httpx.AsyncClient(timeout=20, headers={'User-Agent':'Mozilla/5.0', 'Referer':'https://www.bilibili.com/'}) as client:
        async def fetch(index, original):
            bvid = original['bvid']
            async with semaphore:
                try:
                    response = await client.get('https://api.bilibili.com/x/web-interface/view', params={'bvid':bvid})
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get('code') != 0:
                        raise ValueError('view code=' + str(payload.get('code')))
                    video = payload['data']
                    if video['pubdate'] > CUTOFF:
                        raise ValueError('Published after task date')
                    response = await client.get('https://api.bilibili.com/x/v2/reply', params={'type':1, 'oid':video['aid'], 'sort':2, 'pn':1, 'ps':20})
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get('code') != 0:
                        raise ValueError('reply code=' + str(payload.get('code')))
                    data = payload.get('data') or {}
                    roots = list(data.get('replies') or [])
                    roots += [item for item in (data.get('top') or {}).values() if isinstance(item,dict) and 'rpid' in item]
                    comments = {}
                    queue = [(item, False, str(item['rpid'])) for item in roots]
                    for item, nested, root_id in queue:
                        if item['ctime'] > CUTOFF:
                            continue
                        rid = str(item['rpid'])
                        text = item['content']['message']
                        comments[rid] = {'bvid':bvid, 'rpid':rid, 'rootRpid':root_id, 'text':text,
                            'sha256':hashlib.sha256(text.encode()).hexdigest(), 'createdAt':item['ctime'],
                            'likes':item['like'], 'nested':nested,
                            'isCreator':str(item['member']['mid']) == str(video['owner']['mid']),
                            'url':f'https://www.bilibili.com/video/{bvid}/?comment_on=1#reply{rid}'}
                        if not nested:
                            queue.extend((child, True, rid) for child in item.get('replies') or [])
                    meta = {'bvid':bvid, 'aid':video['aid'], 'title':video['title'], 'creator':video['owner']['name'],
                            'publishedAt':video['pubdate'], 'url':f'https://www.bilibili.com/video/{bvid}/',
                            'reportedReplyCount':video['stat']['reply'], 'hotRootCount':len({str(r['rpid']) for r in roots}),
                            'sampledComments':len(comments)}
                    if index % 10 == 0:
                        print(json.dumps({'checkedVideo':index+1,'comments':len(comments)}, ensure_ascii=False), flush=True)
                    return meta, list(comments.values()), None
                except Exception as error:
                    return None, [], {'bvid':bvid, 'error':type(error).__name__ + ': ' + str(error)}
        batches = await asyncio.gather(*(fetch(i, video) for i, video in enumerate(OLD['videos'])))
        videos = [v for v,_,_ in batches if v]
        unique = {comment['rpid']:comment for _,comments,_ in batches for comment in comments}
        comments = list(unique.values())
        old_text = {item['rpid']:item['sha256'] for item in OLD['comments']}
        summary = {'sampleDate':'2026-10-16','videosRequested':len(OLD['videos']), 'videosRead':len(videos),
                   'creators':len({v['creator'] for v in videos}), 'comments':len(comments),
                   'nonCreatorComments':sum(not c['isCreator'] for c in comments),
                   'rootComments':sum(not c['nested'] for c in comments),
                   'newIdsComparedWithPriorSample':sum(c['rpid'] not in old_text for c in comments),
                   'revalidatedUnchangedTexts':sum(old_text.get(c['rpid']) == c['sha256'] for c in comments),
                   'errors':[error for _,_,error in batches if error]}
        mapping = {v['bvid']:v['creator'] for v in videos}
        summary['perCreator'] = {name:{'videos':sum(v['creator']==name for v in videos),
            'comments':sum(mapping[c['bvid']]==name for c in comments)} for name in dict.fromkeys(mapping.values())}
        summary['method'] = 'Guest public video/reply API; first hot page plus embedded replies; no login or full/random/latest claim. Same discovery frame as v3, refreshed online; UP replies flagged, not independent audience votes.'
        sample = {'summary':summary, 'videos':videos, 'comments':comments}
        (OUT / 'sample.json').write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding='utf-8')
        (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    asyncio.run(main())
