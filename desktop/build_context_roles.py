"""Build v5 whole-manuscript reviewer prompts without changing scoring policy."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import string
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / 'desktop'
GUIDES = DESKTOP / 'role-guides-v5'
current = json.loads((DESKTOP / 'role_bundle.json').read_text(encoding='utf-8'))
if current.get('version') == 4 and not (DESKTOP / 'role_bundle.v4.json').exists():
    shutil.copy2(DESKTOP / 'role_bundle.json', DESKTOP / 'role_bundle.v4.json')
bundle = copy.deepcopy(current)
common = (GUIDES / '00_全文理解与审稿边界.md').read_text(encoding='utf-8')
policy = json.loads((DESKTOP / 'review_groups.json').read_text(encoding='utf-8'))
files = dict(zip(['source-tech','source-practical','source-surfer','source-thinker','source-beginner','source-editor'],
                ['01_较真技术党','02_精打细算实用党','03_玩梗冲浪党','04_深度思考派','05_跃跃欲试新手','06_主编']))
comments = '''
## 评论详情协议

先写自然短评，再以“给作者的备忘”为标题写简短依据。随后附一个<review-comments>和</review-comments>包裹的严格JSON数组。每项text必须逐字对应前面已输出的短评，不新增评论。basis放真实触发短引；context放全文其他相关解释/限定的真实短引，若无需跨段则留空；rationale只写结合上下文后仍成立的简短判断；limits写边界；next_step只写必要方向，已讲清的内容可留空；kind从观众反应/确定问题/待核实/素材待补/个人口味选一项。
负面项的context不能用“未提供”代替全文回查，已被该上下文解答的批评应先撤回，不能照样包装成确定问题。不要为了填字段制造缺口，不输出内部逐步思考链。没有短评可给空数组，机器块不加代码围栏。
'''
for group in policy['groups']:
    pid = group['id']
    role = (GUIDES / (files[pid] + '_角色.md')).read_text(encoding='utf-8')
    cfg = {k: group[k] for k in ('id','name','weight','dimensions')}
    score = '\n## 本团评分协议\n\n按上述角色关注点评价本团三个维度：' + '；'.join(f"{d['name']}（键{d['id']}，团内权重{d['weight']}%）" for d in group['dimensions'])
    score += '。分数反映全文实际完成度，语义已被前后文解释、已有合理演示安排，不得仅因没有最终画面或外部验证材料而自动扣分。每轮都提交完整三维分。\n\n'
    score += '在review-comments之后、CONSENSUS_SCORE之前，附一个<review-score>和</review-score>包裹的严格JSON对象。scores必须且只能有这些键：' + ', '.join(d['id'] for d in group['dimensions'])
    score += '。值为0–10数值或null；unrated_reasons为对象，所有null必须有同名中文原因，其他情况可为空对象。没有成片不必然不可评分：能判断稿面安排时就按稿面评。不可判断时才null，不默认0/5，不自算团分或总分。最后仅保留CONSENSUS_SCORE共识标签，标签不是稿件分。\n'
    marker = '<review-group-config>' + json.dumps(cfg,ensure_ascii=False,separators=(',',':')) + '</review-group-config>\n\n'
    composed = marker + common + '\n\n---\n\n' + role + comments + score
    bundle['personas'][pid]['system_prompt'] = composed
    (GUIDES / (files[pid]+'.md')).write_text(composed,encoding='utf-8')
chair = common + '\n\n---\n\n' + (GUIDES / '06_主编_角色.md').read_text(encoding='utf-8')
bundle['personas']['source-editor']['system_prompt'] = chair
(GUIDES / '06_主编.md').write_text(chair,encoding='utf-8')
bundle['version'] = 5
bundle['name'] = '源宝五个审稿团＋主编 · 全文理解v5'
bundle['settings'].update({
 'advisor_round1_prompt':'{search_context_block}\n【完整稿件及作者要求】\n{question}\n\n先独立理解全文的实际目标、前后回答和制作阶段，再按角色作判断。稿内已明确的信息是本次上下文，不因自己没听过而猜错；前文疑问被后文解决就不再列问题。待拍演示按已规划处理，不凭未给画面判漏步。输出自然的看完全片后反应和必要备忘，可以没有批评；每条负面项须承认全文已说明什么，再写仍剩的实质影响。不机械索取模型横评、完整安装课或计费审计。按角色提交评论关联及三个维度评分。\n{consensus_tag}',
 'advisor_followup_prompt':'{search_context_block}\n【完整原稿，最高裁决依据】\n{question}\n【上一轮候选摘要，可能有误】\n{cross_pollination_extract}\n【讨论记录，不是事实证据】\n{transcript}\n\n第{round_number}轮，上一轮{previous_round_number}轮。优先用全文推翻或收窄误读，不为维护上一轮立场继续挑刺。已说明的名称/解释、后文回答和已规划演示必须纳入判断；同一缺口被多个团复述不增加真实性。只有仍影响本期目标的剩余问题才保留，可明确没有必改。保留各团独特视角，少量自然短评与必要备忘即可，重新输出完整评分与评论关联，不重算总分。\n{consensus_tag}',
 'advisor_cross_pollination_prompt':'【完整原稿】\n{question}\n【第{round_number}轮意见】\n{round_transcript}\n\n只整理简短索引，先注明本期实际方向和整体已讲清的内容。批评必须与全文前后解释交叉核对，保留具体引句、相关回应和仍剩影响。已被原稿回答的疑问标撤回，已安排演示标交付核对，不概括成作者漏教或缺失。无依据的模型身份怀疑和题外责任清单不升级为共识。可以没有确定问题，不新增问题、不打分、不把讨论热度当证据。',
 'advisor_verdict_prompt':'【完整原稿与作者目标，优先于以下所有意见】\n{question}\n【讨论摘要，可能有误，仅作线索】\n{debate_arc}\n【各团原始意见，均需复核】\n{transcript}\n\n先独立重建整篇的目标、解释链和制作阶段，再裁决意见。用紧凑主编判断说清这期方向是否成立、什么已经讲清且值得保留；只处理全文反证之后仍影响本期的缺口。已经给过的模型名称不重问；后文解释不当缺失；已安排的演示/资料放交付核对，不按没有最终成片扣成没讲清楚。反对意见可以被撤回，不为负责而把0个实质问题凑成5条改稿要求。正文修改最多0–3项；可选口味与交付核对不混入必改。不要擅自把方法讲解改成模型鉴定、完整部署课、论文横评或商业审计。不改写口播、不虚构事实。程序计算五团分数，不重算或自报总分。',
 'advisor_tiebreaker_prompt':'【完整原稿】\n{question}\n【候选分歧】\n{transcript}\n\n回到全文裁决，不投票。指出原文已有回答和限定，撤回误读；只有仍影响本期目标的部分才保留。已规划演示是交付核对，未知版本不因模型知识盲区判错；需要外部事实核查但没有证据就明确未核实，不猜。允许分歧和没有必改，不扩大选题、不改写原稿。',
})
allowed={'search_context_block','question','consensus_tag','round_number','previous_round_number','cross_pollination_extract','transcript','round_transcript','debate_arc'}
for key,value in bundle['settings'].items():
    if key.endswith('_prompt'):
        assert {f for _,f,_,_ in string.Formatter().parse(value) if f} <= allowed
        value.format(**{k:'示例' for k in allowed})
shutil.copy2(DESKTOP / 'role-guides-v4/07_评论采样与证据索引.md',GUIDES / '07_评论采样与证据索引.md')
shutil.copy2(DESKTOP / 'role-guides-v4/08_五团权重与计算.md',GUIDES / '08_五团权重与计算.md')
(GUIDES / '09_工作流提示词.md').write_text('# 五个审稿阶段\n\n'+'\n\n'.join('## '+k+'\n\n'+v for k,v in bundle['settings'].items() if k in {'advisor_round1_prompt','advisor_followup_prompt','advisor_cross_pollination_prompt','advisor_verdict_prompt','advisor_tiebreaker_prompt'}),encoding='utf-8')
(GUIDES / 'README_怎么用.md').write_text('''# 全文理解审稿 v5

01–06的普通文件名MD是已合并共同规则、角色视角和协议的完整系统提示，可直接粘贴；后缀“_角色”的文件是供维护的角色片段，不单独代替完整提示。00是共同规则，09是五阶段全局提示，08保留既有评分政策。

这是看完全片后的模拟评论，不是逐句即时弹幕。核心变化：全文反证门槛、明确名称不重复索取身份、区分口播与待拍演示、按作者实际承诺评判、主编允许没有必改。沿用源宝优先的公开评论样本边界与弹幕skill的人味规则，不再把样本里的疑虑机械套给每篇稿。

运行build_context_roles.py可重建角色配置与ZIP；import_review_v5.py仅更新六角色提示及相关审稿阶段模板，保留模型、密钥、权重和旧历史。运行前自动备份旧角色提示。

新提示用于后续新审稿，旧历史与进行中的快照不改写。此前EXE种子和UI风格ZIP未因此更新。提示词不能保证模型永不出错，需用已回答/后文回应/待拍演示及真实矛盾的正反例持续检查。
''',encoding='utf-8')
bundle['sources']=[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(GUIDES.glob('*.md'))]
(DESKTOP / 'role_bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
target=ROOT / 'dist/审稿说明与六角色-全文理解v5.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(GUIDES.glob('*.md')):archive.write(p,p.name)
    archive.write(DESKTOP/'role_bundle.json','角色配置.json')
    archive.write(DESKTOP/'review_groups.json','五团评分权重.json')
with zipfile.ZipFile(target) as archive:assert archive.testzip() is None
print(json.dumps({'version':5,'roles':len(bundle['personas']),'workflowTemplates':5,'templateFieldsValid':True,'package':target.name},ensure_ascii=False))
