"""Build v6 natural discussion and dimension evidence; preserve v5 and score policy."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import string
import zipfile

ROOT=Path(__file__).resolve().parent.parent
D=ROOT/'desktop'
GUIDES=D/'role-guides-v6'
GUIDES.mkdir(exist_ok=True)
current=json.loads((D/'role_bundle.json').read_text(encoding='utf-8'))
if current.get('version')==5 and not (D/'role_bundle.v5.json').exists():
    shutil.copy2(D/'role_bundle.json',D/'role_bundle.v5.json')
base=json.loads((D/'role_bundle.v5.json').read_text(encoding='utf-8'))
bundle=copy.deepcopy(current)
files=['01_较真技术党','02_精打细算实用党','03_玩梗冲浪党','04_深度思考派','05_跃跃欲试新手','06_主编']
ids=['source-tech','source-practical','source-surfer','source-thinker','source-beginner','source-editor']
common=(D/'role-guides-v5/00_全文理解与审稿边界.md').read_text(encoding='utf-8').replace('审稿团 v5','审稿团 v6').replace('先给少量具体、独立、像看完全片后说出的模拟评论。','先给具体、自然、像看完全片后说出的模拟评论，条数由实际信息量决定。')
voice='''
## v6 评论区表达：把短评与审稿备忘分开

评论先说一个具体感受、理解、取舍或仍成立的疑问，像观众顺手打出的句子。技术判断可以严谨，语气不必写成“该方案具有较好的可复用性，值得保留”。少用“主线成立/承接前文/闭环完整/无需补充”等编辑报告用语；这些留给备忘。不要逐句复述旁白后贴一句“挺好”，同义赞美不拆成多条。允许很短的一句，也允许有内容的一小段，不让所有句子同长度、同起手或都先夸后转折。自然不靠强塞热梗、错字、购买冲动或编个人经历。

这里要的是评论，不是把备忘切成四段：通常一条只说一个意思，常见短句约6–35字，确实要展开才写40–80字；这是口气参考，不按字数卡模板。不要每条都写成70–120字的“这段先怎样、后面怎样、所以值得保留”完整分析。严谨解释放rationale，不占满可见短评。类似“能只改这句字幕就省事多了”“原来先看分镜，不是上来就做整片”“复杂视频我先不碰，短的试试”是在稿件有对应依据时可用的口气参考，禁止逐稿照抄。允许直接的认可或疑问，不必每条都交代制作阶段、全流程与免责声明。

用户希望比过去更多评论：信息丰富的中长稿通常可找3–6个不同触发点，短稿或信息有限时1–3条乃至空数组均可；这是软参考，不是名额。若只能凑同义句就少给。评论中可有认可、具体联想、不同取舍、已被后文解开的疑问，但不能把已解答的问题重新当缺失。每条针对全文已经提供的信息发言，不能为了热闹发明作者未说的事实。不要让五团都复述同一套制作流程。

允许少量有实质新信息的团内回应，先有确实输出的前一条评论，再针对它补充、收窄或表达另一种取舍；不必一问一答，不固定安排反对者/护航者。回应必须在reply_to中指向本团较早评论的id；不伪造其他团说过的话、真人昵称、点赞数或身份经历。界面将标为模拟团内回应，不冒充真实粉丝。后轮有真实其他团意见时才可据其内容讨论，仍回到全文纠正误读，不按人数投票。
'''
common+='\n'+voice
(GUIDES/'00_全文理解与审稿边界.md').write_text(common,encoding='utf-8')
extras=[
 '本团短评优先聊具体技术关系和真正限制，少讲编辑术语。可以短说“哦，模型写代码，渲染另有工具，这下分清了”；有真实矛盾再直接指出。例子只校准口气，不逐稿复制，不虚构亲测。',
 '本团更像有任务要完成的人，聊哪个环节能省事、哪类任务不值折腾。可说“有现成稿能接着改就好，不想每次从零来”；必须有稿内对应内容，不自动追问价格或编耗时。',
 '本团轻松一些，允许一句顺口的感受、反差或小联想；不把每句变成段子，也不替作者做运营诊断。认真解释也可以有趣，不编观众流失和完播数据。',
 '本团用普通话聊具体取舍，例如“最后要不要用还是人来定，这点我更在意”；只在原稿实际支持时表达，不固定反AI，不每条都升华行业伦理。',
 '本团带着学到的内容继续聊，可短说“原来先看分镜，不是上来就生成整片”；有后文答案要承认看懂了，问的是剩余卡点，不装失忆、不索取所有安装基础课。',
]
protocol='''
## v6 评论与逐维评分依据协议

先输出自然评论，每条单独一段。需要回应时正文可直接自然接话，不加真人姓名。随后用“给作者的备忘”作简短必要说明。最后在<review-comments>与</review-comments>之间放一个严格JSON对象，不能加代码围栏：
{"comments":[{"id":"c1","text":"逐字对应前面的一条评论","reply_to":null,"basis":"原稿中连续、真实的短引","context":"全文另一处相关连续短引，确实没有必要则空字符串","rationale":"结合全文后可核对的判断摘要","limits":"本条判断边界，无需则空","next_step":"仅必要方向，无需则空","kind":"观众反应"}],"dimension_notes":{"配置中的维度键":{"basis":"该维度真实短引","context":"前后解释或限定的真实短引，无需则空","rationale":"为什么这些内容支持这个分，不能只说表现较好","deduction":"若未满分，具体说明剩余影响；无具体扣分证据时坦言主观保留，不补造缺陷"}}}

comments每条text须与前文逐字相同，不在机器块新增评论；id本团唯一，reply_to仅指同团较早的真实id，无回应为null。kind只能为观众反应/确定问题/待核实/素材待补/个人口味。每条有自己的basis/rationale，不能所有评论共用一段万能理由。引文不用“原稿：”前缀、不要改写或省略拼接；界面只检查文字是否存在，不代表外部事实核验。context不把“未提供”当全文反证。不要把称赞、反问、个人口味包装成事实问题。

dimension_notes必须覆盖本团三个配置维度；分数仍只放review-score，依据不能改变维度键/权重。按稿面完成度评分，优先用0.5分步进，避免9.1与9.2一类没有实际依据的精确感；null仍按既有覆盖规则处理。9–10可以正常给，不因评论较多就多扣分。已解释的信息和已规划演示纳入判断，不能说不是缺陷又暗中扣成缺陷。同一个问题只在真正相关维度反映，说明边界，不机械重复罚分。不输出内部逐步思考，只给可复核依据摘要。
'''
for i,pid in enumerate(ids[:-1]):
    role=(D/'role-guides-v5'/(files[i]+'_角色.md')).read_text(encoding='utf-8')+'\n\n## 团内说话的区别\n\n'+extras[i]+'\n'
    (GUIDES/(files[i]+'_角色.md')).write_text(role,encoding='utf-8')
    old=base['personas'][pid]['system_prompt']
    marker=old.split('\n\n',1)[0]
    score='## 本团评分协议'+old.split('## 本团评分协议',1)[1]
    composed=marker+'\n\n'+common+'\n\n---\n\n'+role+'\n'+protocol+'\n'+score
    bundle['personas'][pid]['system_prompt']=composed
    (GUIDES/(files[i]+'.md')).write_text(composed,encoding='utf-8')
chair_role=(D/'role-guides-v5/06_主编_角色.md').read_text(encoding='utf-8')+'''

## v6 让结论真正吸收各团讨论

独立通读原稿后，必须核对本轮真实收到的各团原始评论与备忘，再定结论，不能只写一份与讨论无关的通用稿评。开头仍是整体结论和具体保留项；其后用“各团意见的取舍”解释实际影响整体判断的观点。写清哪个团的哪条评论（真实短引），你采纳、收窄、不采纳还是保留分歧，理由对应原稿真实短引和全文前后解释。认可的、对主体成立有贡献的意见也要吸收，不能只搜集反对票。多个团同义复述合并处理，不能靠出现次数提高问题真实性。

不必列齐五团、固定条数或为每条写长评，只处理值得进入结论的不同观点。但不能在全部有效意见都被你忽略后自说自话。若同一团内有回应，先辨清是否仅是不同任务偏好；不能把一个有条件的建议推广成所有观众必改。明确撤回被全文推翻的误读，说明“不采纳”的根据，不能隐藏到泛泛的风险段。只收到部分团结果时说明范围，不假称全团一致。

最后才列真正需要处理的0–3项正文方向；已规划演示另作简短交付核对。没有必改就明确说没有，不把为了更热闹而增加的评论数量当成缺陷数量，不改写口播、不编版本与事实。五团加权规则不变，程序计分，不由主编重新投票。
'''
(GUIDES/'06_主编_角色.md').write_text(chair_role,encoding='utf-8')
# The chair uses the full-context boundary but not the reviewers' comment protocol.
chair_common=common.split('## v6 评论区表达')[0]
bundle['personas']['source-editor']['system_prompt']=chair_common+'\n---\n\n'+chair_role
(GUIDES/'06_主编.md').write_text(bundle['personas']['source-editor']['system_prompt'],encoding='utf-8')
bundle['version']=6
bundle['name']='源宝五个审稿团＋主编 · 有据讨论v6'
bundle['settings']=copy.deepcopy(base['settings'])
bundle['settings']['advisor_round1_prompt']+='\n评论按实际信息量展开，避免过去一团只给两段报告腔长评；中长稿可有3–6个不同评论点，短稿少给，不凑数。自然口气与逐条证据分开，可有真实团内回应。严格按v6对象协议给comments及三个dimension_notes，既有review-score协议不变。'
bundle['settings']['advisor_followup_prompt']+='\n读取真实讨论后可作有根据的补充/收窄/回应，不重复上一轮凑条数，不编其他团观点。按v6对象协议重新输出本轮评论、逐维依据和评分。'
bundle['settings']['advisor_cross_pollination_prompt']+='\n保留被实际说出的不同观点和团内回应的条件，不把不同任务偏好硬合成冲突；给主编列真实评论短引与原稿对应关系，供最终采纳/收窄/不采纳裁决。'
bundle['settings']['advisor_verdict_prompt']+='\n必须综合实际收到的各团意见：整体结论之后写“各团意见的取舍”，按有意义的不同观点给出真实评论短引、对应团、采纳/收窄/不采纳/保留分歧及原稿依据。认可意见也计入整体判断，不只汇总挑刺，不虚构没收到的讨论或全体共识。最后再给0–3必要方向；讨论多少不决定扣分多少。'
bundle['settings']['advisor_tiebreaker_prompt']+='\n回应实际存在的不同观点并引用，分清任务偏好与事实矛盾，未收到的团不代其发言。'
allowed={'search_context_block','question','consensus_tag','round_number','previous_round_number','cross_pollination_extract','transcript','round_transcript','debate_arc'}
for k,v in bundle['settings'].items():
    if k.endswith('_prompt'):
        assert {f for _,f,_,_ in string.Formatter().parse(v) if f} <= allowed
        v.format(**{x:'示例' for x in allowed})
for name in ['07_评论采样与证据索引.md','08_五团权重与计算.md']:
    shutil.copy2(D/'role-guides-v5'/name,GUIDES/name)
(GUIDES/'09_工作流提示词.md').write_text('# v6 五阶段\n\n'+'\n\n'.join('## '+k+'\n\n'+v for k,v in bundle['settings'].items() if k.endswith('_prompt')),encoding='utf-8')
(GUIDES/'README_怎么用.md').write_text('''# 有据讨论 v6

01–06无后缀MD是完整系统提示；_角色是维护片段。全文理解v5边界、五团评分维度和权重保留。使用B站评论与弹幕skill的自然表达原则，但内容仍为模拟评审，不是真实网友。中长稿3–6条是软参考，不为了热闹凑评论；有依据才回应。

v6机器块由旧数组扩成comments+dimension_notes对象，旧界面需同步更新才能显示新关联；当前本机网页已支持旧数组和新对象。review-score保持原协议，后台无需重启。新评论可展开逐条原文与理由，逐维分数可展开其独立依据；原稿匹配不等于事实正确。主编须说明实际各团意见的采纳、收窄或不采纳依据。

build_discussion_roles.py重建包；import_review_v6.py仅更新六提示与五模板，保留模型/凭据/权重/其他角色字段/历史，自动备份原提示。仅影响新审稿，不改写旧报告或当前快照。旧EXE和UI风格ZIP没有同步重打包。提示词不能保证模型不误读，仍需抽查。
''',encoding='utf-8')
bundle['sources']=[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(GUIDES.glob('*.md'))]
(D/'role_bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
target=ROOT/'dist/审稿说明与六角色-有据讨论v6.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(GUIDES.glob('*.md')):z.write(p,p.name)
    z.write(D/'role_bundle.json','角色配置.json')
    z.write(D/'review_groups.json','五团评分权重.json')
with zipfile.ZipFile(target) as z:assert z.testzip() is None
print(json.dumps({'version':6,'roles':6,'templateFieldsValid':True,'package':target.name},ensure_ascii=False))
