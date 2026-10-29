"""Read a bounded public comment sample; keep no commenter profile information."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'desktop/comment-evidence-v3'
OUT.mkdir(exist_ok=True)
VIDEOS = [
    'BV1Lvwez5EP1', 'BV1FrWczmEti', 'BV1SKP4etE1k',
    'BV1S64y1N7P1', 'BV1iM411D7SE', 'BV1Sh4y1k75o',
    'BV15D4y1r7g9', 'BV1eS411w7hu', 'BV1ni421a7qQ',
    'BV1Cw4m167yJ', 'BV1ozm5YbExy', 'BV1eSrYBpEMv',
    'BV1iM4y1y7oA', 'BV1QMSjBREzr',
]
result = {'collectedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
          'method': 'Public Bilibili view + reply API; first page sort=2 and sort=0, ps=20; available embedded replies; no login, no paging beyond page 1; deduplicate rpid.',
          'videos': [], 'comments': [], 'errors': []}
seen = set()
manifest = OUT / 'manifest.json'
if manifest.exists():
    VIDEOS = [x['bvid'] for x in json.loads(manifest.read_text(encoding='utf-8'))]
snapshot = OUT / 'sample.json'
if snapshot.exists():
    result = json.loads(snapshot.read_text(encoding='utf-8'))
    initial = OUT / 'sample-initial-14-videos.json'
    if not initial.exists():
        initial.write_bytes(snapshot.read_bytes())
    seen = {x['rpid'] for x in result['comments']}
result['method'] = 'Public Bilibili view + reply API; page 1 sort=2 and sort=0, ps=20; embedded replies. Guest response generally only three hot roots, sort=0 returns empty. Not a latest/random/full comment sample. Deduplicate rpid; UP replies marked; no commenter profile metadata retained.'
result['updatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
done = {v['bvid'] for v in result['videos']}
with httpx.Client(timeout=20, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/'}) as client:
    for bvid in VIDEOS:
        if bvid in done:
            continue
        try:
            response = client.get('https://api.bilibili.com/x/web-interface/view', params={'bvid': bvid})
            response.raise_for_status()
            raw = response.json()
            if raw.get('code') != 0:
                raise ValueError(f"view code={raw.get('code')}: {raw.get('message')}")
            data = raw['data']
            if data['pubdate'] > int(dt.datetime(2026, 10, 15, 23, 59, 59, tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()):
                result['errors'].append({'bvid': bvid, 'error': 'publication after task date; excluded'})
                continue
            video = {'bvid': bvid, 'aid': data['aid'], 'title': data['title'], 'creator': data['owner']['name'],
                     'url': f'https://www.bilibili.com/video/{bvid}/', 'publishedAt': data['pubdate'],
                     'reportedReplyCount': data['stat']['reply'], 'batches': []}
            result['videos'].append(video)
            for sort in [2, 0]:
                response = client.get('https://api.bilibili.com/x/v2/reply', params={'type': 1, 'oid': data['aid'], 'sort': sort, 'pn': 1, 'ps': 20})
                response.raise_for_status()
                payload = response.json()
                if payload.get('code') != 0:
                    result['errors'].append({'bvid': bvid, 'sort': sort, 'code': payload.get('code'), 'message': payload.get('message')})
                    continue
                reply_data = payload.get('data') or {}
                roots = list(reply_data.get('replies') or [])
                top = reply_data.get('top') or {}
                roots += [v for v in top.values() if isinstance(v, dict) and 'rpid' in v]
                batch = {'sort': sort, 'rootCount': len(roots), 'uniqueAdded': 0}
                video['batches'].append(batch)
                queue = [(x, False) for x in roots]
                for item, nested in queue:
                    rid = str(item['rpid'])
                    if rid in seen:
                        continue
                    seen.add(rid)
                    text = item['content']['message']
                    result['comments'].append({'id': f'C{len(seen):04d}', 'bvid': bvid, 'rpid': rid,
                        'url': video['url'] + '?comment_on=1#reply' + rid, 'text': text,
                        'sha256': hashlib.sha256(text.encode()).hexdigest(), 'likes': item['like'],
                        'createdAt': item['ctime'], 'sortFirstSeen': sort, 'nested': nested,
                        'isCreator': item['member']['mid'] == str(data['owner']['mid'])})
                    batch['uniqueAdded'] += 1
                    if not nested:
                        queue.extend((x, True) for x in item.get('replies') or [])
            print(json.dumps({'video': bvid, 'creator': video['creator'], 'sample': sum(x['uniqueAdded'] for x in video['batches'])}, ensure_ascii=False), flush=True)
            snapshot.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            result['errors'].append({'bvid': bvid, 'error': str(exc)})
(OUT / 'sample.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'videos': len(result['videos']), 'comments': len(result['comments']), 'errors': result['errors']}, ensure_ascii=False))
