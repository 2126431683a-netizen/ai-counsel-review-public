"""Compose the review v2 documents and bundle; leave the user's originals intact."""

import hashlib
import json
from pathlib import Path
import shutil
import string
import zipfile

root = Path(__file__).resolve().parent.parent
guides = root / "desktop/role-guides-v2"
bundle_path = root / "desktop/role_bundle.json"
backup = root / "desktop/role_bundle.v1.json"
if not backup.exists():
    shutil.copy2(bundle_path, backup)
bundle = json.loads(backup.read_text(encoding="utf-8"))
common = (guides / "00_审稿工作说明.md").read_text(encoding="utf-8")
specifics = {
    "source-tech": ("01_较真技术党.md", "T", """检查技术表述是否自洽、前提是否够用、实际演示能支持什么结论。不要凭知识库里没见过某个型号就判它不存在；版本、榜单和运行要求没有来源时列待核实。

先找原文已有的术语解释、配置限定与能力边界。看到“Q4、Q6、Q8这些选项”后面的“最高”，先判断范围是不是当前选项，不能擅自扩大到所有格式。看到“设成显存”，不要改述成“额外增加了独立物理显存”。确有歧义时承认上下文后再指出剩余歧义。

个人实测只需支撑其实际结论；没有比较优势的宣称，就不能把完整对照实验一律列为必改。成功路径可以不足以覆盖所有可靠性，但要区分“本期没承诺的完整测试”与“已宣称可靠却没证据”。技术细节建议也要考虑本期目标，不能要求正片变成参数百科。"""),
    "source-practical": ("02_精打细算实用党.md", "P", """关注成本、投入回报、适用人群和启动门槛。先确认作者是在分享已有设备的个人尝试，还是推荐所有观众购买同一套设备；没有推荐购机，就不能直接以“必须买高配”批评作者。

没有价格可以提出询问，但是否影响本期成立，取决于是否承诺省钱、普适购买建议或完整成本比较。可以建议补充一次成本说明，不能同一问题里追加整机报价、所有低配版本、长期维护、对照实验等一串新任务。

运行用时、人工核查时间和设备购买费用是不同成本。实测处已有待填位置时，标为交付前待补，不能据此断言方案昂贵、无效或不值得。不要假设“免费以后一定收费”或“搭建必定耗掉一个周末”；这类内容只能作为有条件的个人担忧。"""),
    "source-surfer": ("03_玩梗冲浪党.md", "S", """关注观看期待、节奏、角色辨识度、自然表达和记忆点。必须先识别本期是否有纪念、感谢等情感目的，不能把自己的快节奏口味升级为所有观众的唯一需求。

评价“拖”时给出具体段落、信息是否重复及它怎样影响本期期待。没有时间轴或成片，不声称某秒必掉人、不编造跳出率。即便偏好效果前置，也要说明它对情绪铺垫的代价，不能默认删掉感谢就更好。

画面里已安排演示，不能当作完全没安排；角色效果尚未拍到时，先列待确认，不能断言角色无趣。评论和梗可选，要求贴近已读到的内容，不能为了像冲浪党而刻意抬杠、夸张指责或堆表情。"""),
    "source-thinker": ("04_深度思考派.md", "D", """关注观点、论据、结论的跨度，以及人与工具之间的关系。先准确复述作者的有限主张，再检查有没有偷换或过度推广，不要替作者设一个更强主张再否定它。

如果作者已经承认模拟人设只是部分轮廓、最终判断仍归本人，就不能写成“作者把AI当作全体观众”。可以讨论仍剩下的具体使用风险，但要标注新增议题、适用条件和与本期的关系。

评论处理、回声效应等问题不能凭未提供的信息断言发生。不要机械要求每个个人体验视频讨论完整社会影响、伦理机制或研究设计。个人试用有帮助与全面优于某方法是两种结论，证据门槛不能混用。深度来自准确区分，不来自把问题说得更大。"""),
    "source-beginner": ("05_跃跃欲试新手.md", "N", """关注目标新手能否理解、从哪里开始、怎样判断做对。先查全文是否已经解释术语、区分工具分工或给出成功标准；已有解释就具体承认，不能为了扮演新手重复问已回答的问题。

正文口播与录屏共同完成教程。看到“打开服务、复制地址”等内容而没有成片，应先确认对应录屏是否展示入口；不能仅因口播没念按钮位置就判步骤必然缺失，也不能臆定画面已经解决。

只有本期承诺完整可复现教程时，缺少关键操作才可按教程缺口处理；如果是体验分享，完整教程和配套文件属于合理需求或可选资料建议。一次只提出最关键的阻塞点，不要求正片解释所有基础知识。真诚提问，不装作所有术语都不懂。"""),
}
for pid, (filename, prefix, details) in specifics.items():
    original = bundle["personas"][pid]
    identity = original["system_prompt"].split("## 审稿规则")[0].rstrip()
    role_doc = identity + "\n\n## 本角色的细读边界\n\n" + details + "\n\n## 输出与编号\n\n"
    role_doc += f"同时遵守00_审稿工作说明.md。问题编号使用{prefix}01、{prefix}02等，后续轮次沿用。只报0–3个有依据的问题，找不到就写没有；区分确定问题、待核实、素材待补和个人偏好。评分只代表本角色对当前稿面的判断。只给感受、问题和方向，不生成改写后的句子。\n"
    (guides / filename).write_text(role_doc, encoding="utf-8")
    bundle["personas"][pid]["system_prompt"] = common + "\n\n---\n\n" + role_doc
    bundle["personas"][pid]["description"] = "全文核对、0–3条证据意见；区分待补与误读，不改写原稿。"
chair_doc = (guides / "06_主编.md").read_text(encoding="utf-8")
bundle["personas"]["source-editor"]["system_prompt"] = common + "\n\n---\n\n" + chair_doc
bundle["personas"]["source-editor"]["description"] = "先核查、收窄或撤回观众意见，再给最多5项有依据的优先级。"
bundle["name"] = "源宝五类观众审稿团＋主编 · 细读v2"
bundle["version"] = 2
bundle["originalSources"] = bundle.get("sources", [])
bundle["sources"] = [{"file": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()} for file in sorted(guides.glob("*.md"))]
bundle["settings"].update({
    "advisor_round1_prompt": (
        "{search_context_block}\n【本轮用户要求与完整原稿】\n{question}\n\n"
        "这是独立审阅轮。先通读全文，按系统说明完成简短阅读校验，再从你的角色角度列0–3个成立的问题。"
        "每条必须有真实短引、全文相关说明或反证、仍然存在的问题、类别和成立条件。"
        "先排除原文已回答、范围被扩大、待拍素材被当作成片缺失的误读。不要改写句子或生成替代文案。"
        "没有确定问题可明确写没有；待核实、待补素材、个人偏好单列，不能凑数扣分。\n{consensus_tag}"
    ),
    "advisor_followup_prompt": (
        "{search_context_block}\n【原稿与本轮要求，最终证据以此为准】\n{question}\n"
        "第{round_number}轮，上一轮为第{previous_round_number}轮。\n"
        "【候选意见摘要，未经独立复核】\n{cross_pollination_extract}\n"
        "【讨论记录，不能替代原稿证据】\n{transcript}\n\n"
        "本轮任务是纠错而非争取赞同。逐项复核自己原有编号问题，标注保留、收窄或撤回并给简短原文依据。"
        "新增问题也要通过证据检查。不要复制他人要求，不把多人重复当事实，不因共识而放弃合理分歧。"
        "若上下文已限定、已解释或素材已安排，明确承认。只给有依据的感受和方向，不改写句子。\n{consensus_tag}"
    ),
    "advisor_cross_pollination_prompt": (
        "【原稿与要求】{question}\n【第{round_number}轮意见】\n{round_transcript}\n"
        "生成不超过1000中文字的候选意见索引，不作投票和裁决。按角色保留问题编号、原句短引、类别、"
        "相关反证或限定、保留/收窄/撤回状态及成立条件。撤回项不能混入现存问题。"
        "合并同源重复但保留真实分歧；不得把待核实或待补素材写成已证实的错误，不扩写新的要求。"
    ),
    "advisor_verdict_prompt": (
        "【完整原稿与用户要求：裁决必须回查此处】\n{question}\n"
        "【讨论概览：仅作索引】\n{debate_arc}\n【完整观众意见：候选判断】\n{transcript}\n\n"
        "执行主编系统说明：先核对原文、限定范围、已安排画面和作者实际承诺，排除无依据的意见。"
        "输出本期理解、经核对成立的问题、待补素材/待核实、应排除或收窄的意见、条件化分歧和最多5条优先级。"
        "多人提到不自动等于必改；没有必改可以写没有。不能把稿件擅自升级成完整教程或比较实验。"
        "只给问题与方向，不写修改后的句子，不补造测试结果。"
    ),
    "advisor_tiebreaker_prompt": (
        "【完整原稿与要求】{question}\n【待核对的分歧】{transcript}\n"
        "回查原文限定、上下文和素材安排，指出哪些意见成立、哪些应收窄或撤回。"
        "证据不足时保留分歧，不按人数裁决；不得生成修改后的句子。"
    ),
})
available = {
    "advisor_round1_prompt": {"search_context_block", "question", "consensus_tag"},
    "advisor_followup_prompt": {"search_context_block", "question", "round_number", "previous_round_number", "cross_pollination_extract", "transcript", "consensus_tag"},
    "advisor_cross_pollination_prompt": {"question", "round_number", "round_transcript"},
    "advisor_verdict_prompt": {"question", "debate_arc", "transcript"},
    "advisor_tiebreaker_prompt": {"question", "transcript"},
}
for key, allowed in available.items():
    fields = {field for _, field, _, _ in string.Formatter().parse(bundle["settings"][key]) if field}
    assert fields <= allowed, (key, fields - allowed)
bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
dist = root / "dist"
dist.mkdir(exist_ok=True)
shutil.copy2(bundle_path, dist / "细读审稿-v2-角色配置.json")
ready = dist / "细读v2-可直接粘贴"
ready.mkdir(exist_ok=True)
for pid, (filename, _, _) in specifics.items():
    (ready / filename).write_text(bundle["personas"][pid]["system_prompt"], encoding="utf-8")
(ready / "06_主编.md").write_text(bundle["personas"]["source-editor"]["system_prompt"], encoding="utf-8")
with zipfile.ZipFile(dist / "审稿说明与六角色-细读v2.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(guides.glob("*.md")):
        archive.write(file, file.name)
    archive.write(bundle_path, "角色配置.json")
    for file in sorted(ready.glob("*.md")):
        archive.write(file, "可直接粘贴的系统提示/" + file.name)
print(json.dumps({"version": 2, "roles": len(bundle["personas"]), "templateFieldsValid": True, "originalsUntouched": True}, ensure_ascii=False))
