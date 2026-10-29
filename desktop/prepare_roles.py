"""Read user-supplied persona Markdown as data and prepare a portable role bundle."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if (root / 'desktop/build_opening_commercial_roles.py').exists() and not any(x in sys.argv for x in ('--original', '--reading-v2', '--comments-v3', '--groups-v4', '--context-v5', '--discussion-v6', '--viewer-v7', '--scoring-v8', '--logic-v9', '--anchors-v10')):
    subprocess.run([sys.executable, str(root / 'desktop/build_opening_commercial_roles.py')], check=True)
    raise SystemExit(0)
if (root / 'desktop/build_anchored_roles.py').exists() and not any(x in sys.argv for x in ('--original', '--reading-v2', '--comments-v3', '--groups-v4', '--context-v5', '--discussion-v6', '--viewer-v7', '--scoring-v8', '--logic-v9')):
    subprocess.run([sys.executable, str(root / 'desktop/build_anchored_roles.py')], check=True)
    raise SystemExit(0)
if (root / 'desktop/build_logic_roles.py').exists() and not any(x in sys.argv for x in ('--original', '--reading-v2', '--comments-v3', '--groups-v4', '--context-v5', '--discussion-v6', '--viewer-v7', '--scoring-v8')):
    subprocess.run([sys.executable, str(root / 'desktop/build_logic_roles.py')], check=True)
    raise SystemExit(0)
if (root / "desktop/build_reliable_roles.py").exists() and not any(x in sys.argv for x in ("--original", "--reading-v2", "--comments-v3", "--groups-v4", "--context-v5", "--discussion-v6", "--viewer-v7")):
    subprocess.run([sys.executable, str(root / "desktop/build_reliable_roles.py")], check=True)
    raise SystemExit(0)
if (root / "desktop/build_viewer_roles.py").exists() and not any(x in sys.argv for x in ("--original", "--reading-v2", "--comments-v3", "--groups-v4", "--context-v5", "--discussion-v6")):
    subprocess.run([sys.executable, str(root / "desktop/build_viewer_roles.py")], check=True)
    raise SystemExit(0)
if (root / "desktop/build_discussion_roles.py").exists() and not any(x in sys.argv for x in ("--original", "--reading-v2", "--comments-v3", "--groups-v4", "--context-v5")):
    subprocess.run([sys.executable, str(root / "desktop/build_discussion_roles.py")], check=True)
    raise SystemExit(0)
if (root / "desktop/role-guides-v5/00_全文理解与审稿边界.md").exists() and not any(x in sys.argv for x in ("--original", "--reading-v2", "--comments-v3", "--groups-v4")):
    subprocess.run([sys.executable, str(root / "desktop/build_context_roles.py")], check=True)
    raise SystemExit(0)
if (root / "desktop/role-guides-v4/00_审稿团工作说明.md").exists() and not any(x in sys.argv for x in ("--original", "--reading-v2", "--comments-v3")):
    subprocess.run([sys.executable, str(root / "desktop/build_group_roles.py")], check=True)
    raise SystemExit(0)
if (root / "desktop/role-guides-v3/00_审稿工作说明.md").exists() and "--original" not in sys.argv and "--reading-v2" not in sys.argv:
    subprocess.run([sys.executable, str(root / "desktop/build_comment_roles.py")], check=True)
    raise SystemExit(0)
if (root / "desktop/role-guides-v2/00_审稿工作说明.md").exists() and "--original" not in sys.argv:
    subprocess.run([sys.executable, str(root / "desktop/upgrade_review_guides.py")], check=True)
    raise SystemExit(0)
downloads = Path.home() / "Downloads"
definitions = [
    ("01_较真技术党.md", "source-tech", "技术准确性与实测边界", "🔧"),
    ("02_精打细算实用党.md", "source-practical", "成本、门槛与实际价值", "💰"),
    ("03_玩梗冲浪党.md", "source-surfer", "节奏、趣味与AI味", "🏄"),
    ("04_深度思考派.md", "source-thinker", "观点深度与人的影响", "💭"),
    ("05_跃跃欲试新手.md", "source-beginner", "理解门槛与动手步骤", "🌱"),
    ("06_主编.md", "source-editor", "归纳观众意见与修改优先级", "📝"),
]
colors = ["#38bdf8", "#fbbf24", "#c084fc", "#818cf8", "#34d399", "#fb923c"]
personas = {}
sources = []
for index, (filename, pid, role, emoji) in enumerate(definitions):
    source = downloads / filename
    content = source.read_text(encoding="utf-8-sig")
    name = content.splitlines()[0].removeprefix("# 人格：").strip()
    description = "只给观众感受、问题和评分，不改写原稿。" if index < 5 else "整理必改、建议改、冲突取舍与最多5条优先级，只给修改方向。"
    personas[pid] = dict(name=name, role=role, description=description, system_prompt=content,
                         avatar_emoji=emoji, color=colors[index])
    sources.append({"file": filename, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
settings = {
    "response_language": "Chinese (Simplified)", "advisor_chair_persona_id": "source-editor",
    "advisor_round1_prompt": (
        "{search_context_block}\n审稿要求与完整稿件：\n{question}\n\n"
        "这是独立审阅轮。请逐段阅读原稿，仅从你的人格视角表达观众感受、问题和评分，"
        "严格遵守角色设定中的输出格式。不要改写句子或生成替代文案；无法从稿件判断的内容直说未知。"
        "不需要凑出不存在的问题。\n{consensus_tag}"
    ),
    "advisor_followup_prompt": (
        "{search_context_block}\n原稿与审稿要求：\n{question}\n"
        "第{round_number}轮，上一轮为第{previous_round_number}轮。\n"
        "上一轮意见摘要：\n{cross_pollination_extract}\n讨论记录：\n{transcript}\n\n"
        "以原稿为依据检查别人的意见，允许补充、修正或保留分歧，不为共识而妥协。"
        "继续按你角色文件要求的评分、原句、问题、真实反应和评论区一句话格式输出；"
        "不得改写原句或生成替代文案。新增问题应有原稿依据，最多3个。\n{consensus_tag}"
    ),
    "advisor_cross_pollination_prompt": (
        "原稿及需求：{question}\n第{round_number}轮的观众意见：\n{round_transcript}\n"
        "保留各角色原名、评分、被指出的原句、问题和真实反应。简要提取共同问题和分歧，"
        "不代替观众作新判断，不生成改写后的句子。"
    ),
    "advisor_verdict_prompt": (
        "原稿与审稿需求：\n{question}\n讨论概览：\n{debate_arc}\n"
        "下面是各类观众对同一份稿件的审阅意见（包含完整讨论）：\n{transcript}\n\n"
        "请严格按你的主编人格设定整理结果。依据观众的真实意见标出必改、建议改、"
        "冲突点与取舍思路，最后给出最多5条修改优先级。只给问题和方向，"
        "不要写出修改后的句子，不强行制造共识。"
    ),
    "advisor_tiebreaker_prompt": (
        "原稿与需求：{question}\n观众意见：\n{transcript}\n"
        "仅说明分歧依据与可能的取舍方向，无法判断时保留分歧。不得提供改写后的句子。"
    ),
    "advisor_default_rounds": 3,
}
bundle = {"name": "源宝五类观众审稿团＋主编", "personas": personas, "settings": settings, "sources": sources}
target = root / "desktop/role_bundle.json"
target.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"roles": [p["name"] for p in personas.values()], "promptsPreserved": True}, ensure_ascii=False))
