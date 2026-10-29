"""Generate a Simplified Chinese catalog while preserving source keys."""

import json
from pathlib import Path
from opencc import OpenCC

root = Path(__file__).resolve().parent.parent
source = root / "frontend/src/locales/zh-TW.js"
catalog = json.loads(source.read_text(encoding="utf-8").removeprefix("export default ").strip().removesuffix(";"))
converter = OpenCC("tw2sp")
localized = {key: converter.convert(value) for key, value in catalog.items()}
for key, value in localized.items():
    for before, after in (("金钥", "密钥"), ("介面", "界面"), ("设定", "设置"), ("载入", "加载"),
                          ("资讯", "信息"), ("自订", "自定义"), ("端点网址", "接口地址")):
        value = value.replace(before, after)
    localized[key] = value
localized.update({
    "LLM Advisors": "角色审稿团", "LLM Council": "多模型评议",
    "Advisors": "审稿角色", "Advisor Setup": "审稿团设置",
    "Persona-Driven Debate": "多角色审稿讨论", "Start Debate": "开始审稿",
    "Custom OpenAI-Compatible Endpoint": "自定义 API（OpenAI 兼容）",
    "Simple": "共用模型", "Advanced": "分别配置模型",
    "LLM API Keys": "模型与 API 设置", "Traditional Chinese": "繁体中文",
    "Debate Question": "审稿要求与原稿", "Start Debate ➤": "开始审稿 ➤",
    "Choose Advisors": "选择审稿角色", "Add Advisor": "添加角色",
    "Add Advisors": "新建角色审稿", "Add Council": "新建多模型评议",
    "Complete the form below to start a debate": "填写原稿并选择模型后开始审稿",
    "{count} / 8 selected": "已选 {count} / 8 位",
})
(root / "frontend/src/locales/zh-CN.js").write_text(
    "// Derived from the upstream MIT-licensed Traditional Chinese catalog.\nexport default "
    + json.dumps(localized, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
print(f"Simplified Chinese phrases: {len(localized)}")
