"""Optional, deterministic draft ratings for explicitly configured review groups.

Configuration comes from the saved persona prompt, never from model output.
CONSENSUS_SCORE remains a separate discussion signal, not a manuscript rating.
"""
from decimal import Decimal, ROUND_HALF_UP
import json
import math
import re

GROUPS = {'source-tech', 'source-practical', 'source-surfer', 'source-thinker', 'source-beginner'}
CONFIG = re.compile(r'<review-group-config>\s*(.*?)\s*</review-group-config>', re.S)
SCORE = re.compile(r'<review-score>\s*(.*?)\s*</review-score>', re.S)

def normalize_review_blocks(content):
    """Close only complete, unambiguous JSON objects; never repair their data."""
    value = content or ''
    for tag in ['review-comments','review-score']:
        opening, closing = '<'+tag+'>', '</'+tag+'>'
        if value.count(opening) != 1 or closing in value:
            continue
        start = value.index(opening)+len(opening)
        start += len(value[start:])-len(value[start:].lstrip())
        try:
            parsed, length = json.JSONDecoder().raw_decode(value[start:])
        except ValueError:
            continue
        if not isinstance(parsed,dict):
            continue
        end = start+length
        tail = value[end:].lstrip()
        allowed = not tail or (tag=='review-comments' and tail.startswith('<review-score>')) or (tag=='review-score' and tail.startswith('CONSENSUS_SCORE:'))
        if allowed:
            value = value[:end]+closing+value[end:]
    return value


def _number(value, minimum, maximum):
    return type(value) in (int, float) and minimum <= value <= maximum and math.isfinite(value)


def _shown(value):
    return float(value.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def group_config(prompt):
    matches = CONFIG.findall(prompt or '')
    if len(matches) != 1:
        return None
    try:
        cfg = json.loads(matches[0])
        if cfg.get('id') not in GROUPS or not isinstance(cfg.get('name'), str):
            return None
        if not _number(cfg.get('weight'), 1, 100):
            return None
        dims = cfg.get('dimensions')
        if not isinstance(dims, list) or not 1 <= len(dims) <= 8:
            return None
        ids = [x['id'] for x in dims]
        if len(set(ids)) != len(ids) or not all(isinstance(x, str) for x in ids):
            return None
        if not all(isinstance(x.get('name'), str) and _number(x.get('weight'), 1, 100) for x in dims):
            return None
        if sum(Decimal(str(x['weight'])) for x in dims) != 100:
            return None
        if 'scoring_policy' in cfg:
            if cfg['scoring_policy'] != 'opening-commercial-v1' or cfg.get('rubric_version') != 2 or len(dims) != 5:
                return None
            weights = {d['id']: d['weight'] for d in dims}
            if weights.get('opening') != 15 or weights.get('commercial') != 25:
                return None
        if 'rubric_version' in cfg:
            if cfg['rubric_version'] != 2:
                return None
            for dimension in dims:
                checks = dimension.get('checks')
                if not isinstance(checks, list) or len(checks) != 2:
                    return None
                if not all(isinstance(c, dict) and isinstance(c.get('id'), str) and c['id'] and isinstance(c.get('name'), str) for c in checks):
                    return None
                if len({c['id'] for c in checks}) != 2:
                    return None
        return cfg
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def audit_score_evidence(content, config, manuscript, dimensions=None):
    """Check traceability only; a matching quote does not prove a judgment true."""
    normalize = lambda value: re.sub(r'[\s“”"‘’\'*`_]', '', value)
    issues = []
    try:
        blocks = re.findall(r'<review-comments>\s*(.*?)\s*</review-comments>', content or '', re.S)
        if len(blocks) != 1:
            raise ValueError('missing notes')
        payload = json.loads(blocks[0])
        notes = payload.get('dimension_notes', {}) if isinstance(payload, dict) else {}
        text = normalize(manuscript)
        for dimension in dimensions or config['dimensions']:
            note = notes.get(dimension['id'], {})
            if not isinstance(note, dict) or not all(isinstance(note.get(k), str) and note[k].strip() for k in ['basis', 'rationale']):
                issues.append(dimension['name'] + '缺少独立原文与理由')
                continue
            if not normalize(note['basis']) or normalize(note['basis']) not in text:
                issues.append(dimension['name'] + '的原文引文未匹配')
            context = note.get('context')
            if context and (not isinstance(context, str) or normalize(context) not in text):
                issues.append(dimension['name'] + '的相关解释未匹配')
            if dimension.get('score', 10) < 10 and not (isinstance(note.get('deduction'), str) and note['deduction'].strip()):
                issues.append(dimension['name'] + '缺少扣分或主观保留说明')
            if config.get('rubric_version') == 2:
                supplied = note.get('checks')
                expected = {c['id'] for c in dimension['checks']}
                if not isinstance(supplied, list) or len(supplied) != 2 or not all(isinstance(c, dict) and isinstance(c.get('id'), str) for c in supplied) or {c['id'] for c in supplied} != expected:
                    issues.append(dimension['name'] + '缺少两项画像评分明细')
                    continue
                total = Decimal(0)
                for check in supplied:
                    points = check.get('score')
                    if not _number(points, 0, 5) or Decimal(str(points)) % Decimal('0.5'):
                        issues.append(dimension['name'] + '子项分应为0至5的半分步进')
                        continue
                    total += Decimal(str(points))
                    if not all(isinstance(check.get(k), str) and check[k].strip() for k in ['basis','rationale']):
                        issues.append(dimension['name'] + '子项缺少原文与档位理由')
                    elif not normalize(check['basis']) or normalize(check['basis']) not in text:
                        issues.append(dimension['name'] + '子项引文未匹配')
                    if points < 5 and not (isinstance(check.get('gap'), str) and check['gap'].strip()):
                        issues.append(dimension['name'] + '子项缺少距更高档位的具体差距')
                if dimension.get('score') is not None and total != Decimal(str(dimension['score'])):
                    issues.append(dimension['name'] + '维度分与两项明细之和不一致')
        return issues
    except (ValueError, TypeError, AttributeError):
        return ['未保存可核对的逐维评分依据']


def score_from_ledger(content, config, manuscript):
    """Calculate only already supplied, fully traceable v2 checkpoint numbers.

    No prose grades, inferred commercial status, rounding of checkpoints, or model
    calls. An explicit not-applicable commercial note is the sole null case.
    """
    if config.get('rubric_version') != 2 or not isinstance(manuscript, str) or not manuscript.strip():
        return None
    try:
        blocks = re.findall(r'<review-comments>\s*(.*?)\s*</review-comments>', content, re.S)
        if len(blocks) != 1:
            return None
        notes = json.loads(blocks[0])['dimension_notes']
        if not isinstance(notes, dict) or set(notes) != {d['id'] for d in config['dimensions']}:
            return None
        values, reasons = {}, {}
        numeric_dimensions = []
        for dimension in config['dimensions']:
            key = dimension['id']
            note = notes[key]
            checks = note.get('checks')
            if key == 'commercial' and config.get('scoring_policy') == 'opening-commercial-v1' and checks == []:
                # Require the model's explicit judgment, never infer N/A just
                # because a list is empty or the draft mentions a free resource.
                reason = note.get('deduction', '')
                if not isinstance(reason, str) or not re.match(r'^不适用(?:[：:，,。；;\s]|$)', reason.strip()):
                    return None
                if audit_score_evidence(content, {**config, 'rubric_version': 1}, manuscript, [dimension]):
                    return None
                values[key], reasons[key] = None, reason.strip()
                continue
            expected = {c['id'] for c in dimension['checks']}
            if not isinstance(checks, list) or len(checks) != 2 or not all(isinstance(c, dict) and isinstance(c.get('id'), str) for c in checks) or {c['id'] for c in checks} != expected:
                return None
            if not all(_number(c.get('score'), 0, 5) and Decimal(str(c['score'])) % Decimal('0.5') == 0 for c in checks):
                return None
            values[key] = float(sum((Decimal(str(c['score'])) for c in checks), Decimal(0)))
            numeric_dimensions.append({**dimension, 'score': values[key]})
        if audit_score_evidence(content, config, manuscript, numeric_dimensions):
            return None
        return {'scores': values, 'unrated_reasons': reasons}
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def consume_score(content, config, manuscript=None):
    """Remove the private score payload, validate it, then calculate a team rating."""
    if not config:
        return content, None
    original = content
    if config.get('rubric_version') == 2:
        content = normalize_review_blocks(content)
    matches = SCORE.findall(content or '')
    clean = SCORE.sub('', content or '').strip()
    if '<review-score>' in clean:  # Hide an incomplete payload too; never guess its score.
        clean = clean.split('<review-score>', 1)[0].strip()
    result = {'group_id': config['id'], 'status': 'invalid', 'score': None,
              'reason': '评分数据缺失或格式无效', 'dimensions': [], 'coverage': 0}
    if content != original:
        result['format_normalized'] = True
    # A syntactically broken/missing summary may be redundant with a complete
    # ledger. Conflicting parseable summaries, duplicates and truncated blocks
    # remain errors, even if a plausible number could be reconstructed.
    payload = None
    recoverable = len(matches) <= 1 and content.count('<review-score>') == len(matches)
    if len(matches) == 1:
        try:
            payload = json.loads(matches[0])
            recoverable = False
        except ValueError:
            pass
    if payload is None and recoverable:
        payload = score_from_ledger(content, config, manuscript)
        if payload is not None:
            result['calculation_source'] = 'validated_check_ledger'
    try:
        if payload is None:
            raise ValueError('评分汇总缺失或格式错误，且没有可完整校验的评分明细')
        values = payload['scores']
        reasons = payload.get('unrated_reasons', {})
        if set(values) != {x['id'] for x in config['dimensions']} or not isinstance(reasons, dict):
            raise ValueError('评分维度与本团设定不一致')
        weighted = Decimal(0)
        coverage = Decimal(0)
        dimensions = []
        for dimension in config['dimensions']:
            key = dimension['id']
            value = values[key]
            if value is None:
                if config.get('scoring_policy') == 'opening-commercial-v1' and key != 'commercial':
                    raise ValueError('内容与开头维度不可留空')
                reason = reasons.get(key)
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError('不适用维度缺少原因')
            else:
                if not _number(value, 0, 10):
                    raise ValueError('维度评分必须是0至10的有效数字')
                weight = Decimal(str(dimension['weight']))
                coverage += weight
                weighted += Decimal(str(value)) * weight
                reason = None
            dimensions.append({**dimension, 'score': value, 'reason': reason})
        result.update(dimensions=dimensions, coverage=float(coverage))
        if coverage < 60:
            result.update(status='unrated', reason='可判断维度权重不足60%，本团暂不评分')
        else:
            raw = weighted / coverage
            result.update(status='ok', score=_shown(raw), raw_score=str(raw), reason=None)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        result['reason'] = str(error) if isinstance(error, ValueError) else '评分汇总字段不完整或类型错误'
        result['ledger_recovery_blocked'] = not recoverable
    if manuscript is not None and result['status'] == 'ok':
        issues = audit_score_evidence(content, config, manuscript, [d for d in result['dimensions'] if d['score'] is not None])
        result.update(evidence_status='insufficient' if issues else 'located', evidence_issues=issues)
        if issues:
            result.update(status='unverified', proposed_score=result['score'], score=None,
                          reason='评分依据待核对：' + '；'.join(issues))
    if result['status'] == 'ok':
        detail = '；'.join(f"{d['name']} {'待定' if d['score'] is None else str(d['score'])}" for d in result['dimensions'])
        clean += f"\n\n本团稿面评分：**{result['score']:.1f}/10**（{detail}；可判断维度{result['coverage']:g}%）。"
        if result.get('calculation_source') == 'validated_check_ledger':
            clean += '\n评分汇总格式异常，已按校验通过的子项明细计算；未重新评价稿件。'
    else:
        clean += '\n\n本团稿面评分：**暂缺**（' + result['reason'] + '）。'
    return clean.strip(), result


def build_score_report(personas, final_responses):
    configs = [(p.id, group_config(p.system_prompt)) for p in personas]
    configs = [(pid, cfg) for pid, cfg in configs if cfg]
    if not configs:
        return None
    ids = [cfg['id'] for _, cfg in configs]
    valid_panel = len(configs) == len(personas) == 5 and set(ids) == GROUPS and sum(Decimal(str(cfg['weight'])) for _, cfg in configs) == 100
    by_id = {r['persona_id']: r for r in final_responses}
    rows = []
    weighted = Decimal(0)
    available_weight = Decimal(0)
    for pid, cfg in configs:
        response = by_id.get(pid, {})
        rating = response.get('review_rating') or {}
        valid = not response.get('error') and rating.get('status') == 'ok' and rating.get('group_id') == cfg['id']
        # Recompute from configured dimensions; never trust a stored raw total.
        recomputed = None
        if valid:
            dims = rating.get('dimensions', [])
            if len(dims) != len({d.get('id') for d in dims}):
                valid = False
            else:
                payload = {'scores': {d.get('id'):d.get('score') for d in dims},
                           'unrated_reasons': {d.get('id'):d.get('reason') for d in dims if d.get('score') is None}}
                _, recomputed = consume_score('<review-score>'+json.dumps(payload)+'</review-score>', cfg)
                valid = recomputed['status'] == 'ok'
        raw = Decimal(recomputed['raw_score']) if valid else None
        contribution = raw * Decimal(str(cfg['weight'])) / 100 if valid else None
        if valid:
            weighted += contribution
            available_weight += Decimal(str(cfg['weight']))
        rows.append({'persona_id': pid, 'group_id': cfg['id'], 'name': cfg['name'], 'weight': cfg['weight'],
                     'score': recomputed['score'] if valid else None,
                     'dimensions': rating.get('dimensions', []), 'coverage': rating.get('coverage', 0),
                     'contribution': _shown(contribution) if valid else None,
                     'evidence_status': rating.get('evidence_status', 'legacy'),
                     'reason': None if valid else response.get('error') or rating.get('reason', '本轮未取得有效评分')})
    complete = valid_panel and available_weight == 100
    return {'version': 1, 'complete': complete, 'score': _shown(weighted) if complete else None,
            'available_weight': float(available_weight), 'configured_weight': sum(cfg['weight'] for _, cfg in configs),
            'reason': None if complete else ('需要五个不同审稿团，且权重合计100%' if not valid_panel else '部分团评分暂缺，不将缺分当0，也不提高其他团权重'),
            'groups': rows, 'scope': '模型给出的当前稿面主观评分；不是观众比例、实测真实性或完播率。'}


def score_markdown(report):
    if not report:
        return ''
    lines = ['### 审稿团加权评分', '', '|审稿团|权重|稿面分 /10|加权贡献|', '|---|---:|---:|---:|']
    for row in report['groups']:
        score = '暂缺' if row['score'] is None else f"{row['score']:.1f}"
        contribution = '—' if row['contribution'] is None else f"{row['contribution']:.1f}"
        lines.append(f"|{row['name']}|{row['weight']:g}%|{score}|{contribution}|")
    lines += ['', f"**加权总分：{report['score']:.1f}/10**" if report['complete'] else '**总分暂缺**：' + report['reason'], '',
              '程序按各团未四舍五入的维度加权分计算，再统一保留一位小数；表中贡献已取整，逐项相加可能有0.1的差异。权重是作者的编辑偏好，不代表粉丝人数。高分不能抵消已核实的严重错误。']
    for row in report['groups']:
        pending = [f"{d['name']}：{d['reason']}" for d in row['dimensions'] if d['score'] is None]
        if pending:
            lines += ['', f"{row['name']}待判断：" + '；'.join(pending)]
    return '\n'.join(lines)


def combine_verdict(content, report):
    if not report:
        return content
    body = re.split(r'(?:^|\n)#{1,6}\s*审稿团加权评分', content or '', maxsplit=1)[0].strip()
    return body + '\n\n' + score_markdown(report)
