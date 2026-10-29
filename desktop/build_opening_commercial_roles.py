"""v11: explicit opening and commercial-integration axes; retain v10 evidence."""
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / 'desktop'
POLICY = 'opening-commercial-v1'
CHECKS = {
    'opening': [
        ('前15秒值得留下', '能识别主题，但所得或具体情境较泛、有效内容偏晚', '在前15秒内以明确情境、可观察结果或有意义问题给目标观众留下的理由，承诺具体可信，不靠空泛震撼或强行悬念'),
        ('15至20秒继续推进', '主线能接上，但前20秒有重复铺垫、口号或理解负担', '到20秒已推进解释、例子、演示或关键冲突，观众看得出下一步价值；节奏符合体裁，不用追快代替清楚'),
    ],
    'commercial': [
        ('内容价值没有被推销挤占', '有可用信息，但部分篇幅被卖点罗列、催促或重复背书挤占', '即使观众不购买也有具体可带走的解释、方法或判断依据，品牌信息不替代内容；商业信息密集时仍有足够实质内容而非一句提醒'),
        ('商业信息自然且可信地融入', '产品与场景有关，但转入卖点、购买引导或结论略突兀', '产品在真实问题→相关使用/演示→有边界结果中发挥作用，转场自然、主张与稿面依据相称；商业披露清楚不破坏叙事，不靠隐瞒合作换取自然感'),
    ],
}

RULES = '''## 开头15–20秒与商业属性：必须单独判断

本团仍按自己的真实受众关注点评价，评分新增opening与commercial两维。原三个维度按原相对比例合计占60%，opening占15%，commercial占25%。五团之间原权重保持。商业融合比单独开头有更高权重，不是额外奖励分；低商业分会拉低总分，高融合分仍不能掩盖内容质量低或事实问题。

先读完整篇，再回到开头分别定位0–15秒、15–20秒已提供的内容，以及20秒后才兑现的内容。稿件有可靠时间码/明确时长时优先使用；无时间信息，只以口播约每秒4个汉字为工作假设粗估前60/80字（忽略标题、舞台备注和非口播文字），明确写“按稿面粗估，实际需试读计时”，不能说已测得真实秒数。数字/英文/停顿与画面会改变时长，边界不清要说明，不机械按字符裁断一句话。没有明确口播部分或不足20秒时评实际可判断范围，说明限制，不凭空补前20秒。普通文章只评价开篇的观看/阅读理由，明确15–20秒不适用，不假装是口播时间。

opening的basis必须来自实际开头，context可引后文兑现处；rationale必须分别说明15秒与20秒检查点、时间依据、目标受众得到什么、仍欠什么。后文补充可以撤销“全文缺失”批评，但不能倒算成观众开头已获得信息。审的是稿面跳出风险/留人能力，不输出“预计跳出率XX%”、平台通用阈值或播放预测；真正跳出率只能来自该视频发布后的留存数据。不要强迫故事/慢节奏类型做五秒爆点；仍要说明其目标观众有无足够继续看的理由。

commercial先核对作者brief、稿内合作/推广标注和具体推销行为。出现品牌、产品教程、客观测评或一次正常的合作披露，不能单独证明广告浓度重。按硬推销挤占、重复口号/催购、突兀转场、只讲好处、无支撑比较与偏离原题，判断“侵入性广告负担”，不按品牌次数或字数机械扣分。推广内容越取代实际信息、越打断观看动机，两个子项应按实际损害下档；举出本稿证据。产品真正承接问题、演示有检验点、结果和局限讲清，给相应高融合分，不因合作本身压低分，也不因一句免责声明就自动高分。隐瞒广告关系不是自然植入，不奖励藏广告。

无商业推广或无足够依据确认推广时，commercial填null并在unrated_reasons.commercial明确说明“不适用：未见足够商业推广依据”，结合具体稿面解释；不猜商业关系，不填10白送分。此时仅该项退出计算：原内容60/75=80%，opening15/75=20%。若稿件明确有推广，只是不知道真实成交/成片效果，仍评稿面融合质量，不能用null逃避扣分；不要求实际成交数据。

原有观看期待/节奏维度继续评中后段兑现与全篇信息推进，opening专管开头检查点；commercial专管推广造成的额外侵入与融合。同一段只有广告重复这一根因时，在commercial体现，不再用同一句“像广告”给所有旧项重复扣分；若开头确实延迟有效信息、整篇同时无证据，则可分别反映不同可说明的损害，主编需核对。

每个数值维度仍是a/b各0–5分、0.5步进，两项相加/10。新维度同样需要真实引句、具体档位理由与非满分差距；null商业项无需编造子项。除commercial外四维必须给出可核对分数，材料确实不足时整团暂不计分，不通过排除低分项抬高总分。程序只做计算和可追溯检查，不证明模型判断客观正确。
'''

CHAIR = '''
## v11新增的结论责任

必须分别汇总“开头15–20秒留人风险”和“广告负担与自然融合”，从实际返回的本轮团评中引用依据，并回查原稿。先给明确结论，再给关键原因、需改位置与最小方向。区分15秒/20秒已出现和后文才出现的信息，承认合理铺垫但不以结尾兑现抹掉开头拖延；时间未知明确是粗估，绝不编跳出率。广告重点看推销是否挤占价值、是否突兀与是否有支撑；相关产品自然参与解题且不买也有所得，应认可融合，不把合作披露当硬广缺陷，也不奖励隐藏合作。

核对各团commercial适用性是否一致；有分歧时根据brief/原稿说明采纳与保留，提醒复核而不暗改程序分。新团分：内容60%、开头15%、商业融合25%；无商业证据commercial为null，内容与开头按80/20计算。新旧版本不可直接当同标尺比较，旧历史不重算。同根广告问题不机械重复扣到全维，严重误导仍需优先处理，高融合分不能冲淡事实问题。不代替五团填分，不造未返回的意见。
'''


def main():
    prior = D / 'role_bundle.v10.json'
    if not prior.exists():
        current = json.loads((D / 'role_bundle.json').read_text(encoding='utf-8'))
        assert current['version'] == 10
        shutil.copy2(D / 'role_bundle.json', prior)
    bundle = copy.deepcopy(json.loads(prior.read_text(encoding='utf-8')))
    guides = D / 'role-guides-v11'
    guides.mkdir(exist_ok=True)
    configs = {}
    for pid, role in bundle['personas'].items():
        prompt = role['system_prompt']
        prompt = prompt.replace('v10', 'v11')
        if pid != 'source-editor':
            match = re.search(r'<review-group-config>(.*?)</review-group-config>', prompt, re.S)
            cfg = json.loads(match[1])
            cfg['scoring_policy'] = POLICY
            for dim in cfg['dimensions']:
                dim['weight'] = dim['weight'] * 60 // 100 if dim['weight'] * 60 % 100 == 0 else dim['weight'] * .6
            for key, name, weight in [('opening', '开头15–20秒留人能力', 15), ('commercial', '商业信息融合度', 25)]:
                cfg['dimensions'].append(dict(id=key, name=name, weight=weight, checks=[dict(id=i, name=n, basic=b, excellent=e) for i, (n, b, e) in zip(['a', 'b'], CHECKS[key])]))
            # The surfer's old axis now covers payoff; opening quality has its own axis.
            if pid == 'source-surfer':
                cfg['dimensions'][0]['checks'][0].update(name='中段延续观看理由', basic='中段与主题相关，但信息增量较泛', excellent='中段通过具体解释、例子或结果不断增加观看所得，不靠重复开头或品牌口号维持期待')
                prompt = re.sub(r'### 观看期待得到回应（promise）\n.*?(?=\n\n###)', '### 观看期待得到回应（promise）\n' + '\n'.join(f"- {c['id']}｜{c['name']}：基本档3分＝{c['basic']}；优秀档5分＝{c['excellent']}。" for c in cfg['dimensions'][0]['checks']), prompt, count=1, flags=re.S)
            prompt = prompt[:match.start()] + '<review-group-config>' + json.dumps(cfg, ensure_ascii=False, separators=(',', ':')) + '</review-group-config>' + prompt[match.end():] if pid != 'source-surfer' else re.sub(r'<review-group-config>.*?</review-group-config>', lambda _: '<review-group-config>' + json.dumps(cfg, ensure_ascii=False, separators=(',', ':')) + '</review-group-config>', prompt, count=1, flags=re.S)
            prompt = prompt.replace('原维度和团权重不变', '原三维相对比例不变，实际团内权重按新增60/15/25结构计算；五团之间权重不变').replace('本团三个维度', '本团配置中的全部五个维度').replace('避免重复六份子项文字', '避免重复十份子项文字')
            anchors = '\n'.join('### ' + d['name'] + '\n' + '\n'.join(f"- {c['id']}｜{c['name']}：基本档3分＝{c['basic']}；优秀档5分＝{c['excellent']}。" for c in d['checks']) for d in cfg['dimensions'][-2:])
            prompt = prompt.replace('## 输出协议', RULES + '\n' + anchors + '\n\n## 输出协议')
            # Replace schema examples to include all five dimensions.
            shape = {'comments': [], 'dimension_notes': {d['id']: dict(basis='本稿原样短引', context='相关原样短引或空', rationale='具体档位依据', deduction='未满分差距', checks=[dict(id=c['id'], score='实际0至5数字', basis='本稿原样短引', rationale='具体理由', gap='非5时的差距') for c in d['checks']]) for d in cfg['dimensions']}}
            payload = {'scores': {d['id']: 'a与b相加数字；仅commercial可按规则null' for d in cfg['dimensions']}, 'unrated_reasons': {}}
            prompt = re.sub(r'<review-comments>\{.*?</review-score>', lambda _: '<review-comments>' + json.dumps(shape, ensure_ascii=False, separators=(',', ':')) + '</review-comments>\n<review-score>' + json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '</review-score>', prompt, count=1, flags=re.S)
            no_ad = {'scores': {d['id']: None if d['id']=='commercial' else '填写a与b之和的数字' for d in cfg['dimensions']}, 'unrated_reasons': {'commercial': '不适用：未见足够商业推广依据；此处补本稿理由'}}
            prompt += '\n\n无广告时仅使用下面这个review-score结构替代上例，不要再多输出第二个评分块。将其他四项占位文字换成实际数字；commercial保持JSON null（无引号）。unrated_reasons末尾只需两个右大括号：一个关闭原因对象，一个关闭根对象，不能写三个。\n<review-score>' + json.dumps(no_ad, ensure_ascii=False, separators=(',', ':')) + '</review-score>\n'
            configs[pid] = cfg
        else:
            prompt += CHAIR
        role['system_prompt'] = prompt
        index = list(bundle['personas']).index(pid) + 1
        (guides / f'{index:02d}_{role["name"]}.md').write_text(prompt, encoding='utf-8')
    for key in ['advisor_round1_prompt', 'advisor_followup_prompt']:
        bundle['settings'][key] += '\n使用v11五维规则：原内容60%、开头15–20秒15%、商业融合25%；commercial不适用时null且解释，其余四维不可缺。按各团画像定位开头检查点与商业挤占/自然融合，给真实引句与a/b明细，不编实测跳出率；同根问题避免重复扣分。'
    bundle['settings']['advisor_verdict_prompt'] += CHAIR
    for file in ['07_真实评论与画像依据.md']:
        shutil.copy2(D / 'role-guides-v10' / file, guides / file)
    (guides / '00_开头与商业融合评分说明.md').write_text('# v11评分说明\n\n' + RULES + CHAIR + '\n\n来源与边界：2026-10-18核对[YouTube官方留存说明](https://support.google.com/youtube/answer/9314415?hl=en)：实际留存来自视频级分析，其Intro定义为前30秒，并非本项目15–20秒的通用跳出阈值。[B站商业推广说明](https://www.bilibili.com/opus/76356456869328234)说明商业合作填报机制。60/15/25是本项目编辑权重，每秒4汉字仅为无时间码时的工作假设，不是网上测得的模型或平台参数。真实受众资料沿用10月16日1020条公开记录，未声称新增实测留存/广告因果数据。\n', encoding='utf-8')
    (guides / '评分配置.json').write_text(json.dumps(configs, ensure_ascii=False, indent=2), encoding='utf-8')
    (guides / 'README_怎么用.md').write_text('# v11：开头留人能力与商业融合\n\n01–06可直接使用的完整人设；00解释权重与边界；07保留真实评论依据；评分配置.json为实际五维配置。自然推广可高分，硬广告挤占信息会低分。无推广商业项不适用、不白送满分。原五团权重不变。旧历史保留原版本；新提交使用v11。源码服务已增加规则校验，旧EXE未重打包。\n', encoding='utf-8')
    (guides / '09_工作流提示词.md').write_text('\n\n'.join('## '+k+'\n'+v for k,v in bundle['settings'].items() if k.endswith('_prompt')), encoding='utf-8')
    bundle.update(version=11, name='源宝五团＋主编 · 开头与商业融合v11')
    bundle['sources'] = [{'file': f.name, 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(guides.iterdir()) if f.is_file()]
    (D / 'role_bundle.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
    with zipfile.ZipFile(ROOT / 'dist/审稿说明与六角色-开头与商业融合v11.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for f in guides.iterdir():
            if f.is_file(): archive.write(f, f.name)
        archive.write(D / 'role_bundle.json', '角色配置.json')
    print(json.dumps({'version': 11, 'groups': len(configs), 'axes': 5, 'weights': [60, 15, 25]}, ensure_ascii=False))

if __name__ == '__main__':
    main()
