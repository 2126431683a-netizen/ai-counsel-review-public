from pathlib import Path
import hashlib
import json
import shutil
import zipfile
import re

root = Path(__file__).resolve().parent.parent
stage = root / 'dist/漫画拟物UI风格包-20261016'
readme = stage / 'README.md'
readme.write_text(readme.read_text(encoding='utf-8').replace('右上角可打开设置外观演示', '点击“设置外观预览”可打开设置样例'), encoding='utf-8')
(stage / '设计规范与复用提示.md').write_text('''# 漫画 × 拟物 · 设计规范与复用提示

## 风格核心

浅灰模塑桌面承托暖白纸卡。纸卡、主按钮与评论气泡使用清晰粗墨线和小幅硬阴影；输入、工具栏与设置底板保留柔和双向阴影或内凹槽。角色图标带手绘轮廓和低饱和底色。漫画负责信息边界，拟物负责承托层次。

## 基础规范

| 项目 | 值与用途 |
| --- | --- |
| 底板 | #e0e5ec |
| 内容纸面 | #fffdf5 |
| 墨线/主文字 | #252733 |
| 次要说明 | #505362 |
| 主按钮/选中强调 | #ffe28a |
| 柔阴影 | #b8bcc2 与 #ffffff，偏移4–6px、模糊8–12px |
| 硬阴影 | 2–4px，小偏移、无模糊、墨线色 |
| 边框 | 2px；主要框架3px |
| 圆角 | 主框架8–12px；评论气泡约20px并保留一个小圆角 |
| 字体 | Microsoft YaHei UI / PingFang SC / sans-serif，使用系统字体 |
| 字号 | 标题24–28px，正文14–16px，辅助说明11–13px |
| 间距 | 以4px为基数，组内8–12px，模块16–24px |
| 动效 | 100ms ease-out；按压减小硬阴影；尊重减少动态效果设置 |

## 图标与语义

技术团：芯片放大镜，蓝色，准确性与实测边界。
实用团：算盘，橙色，成本、门槛与实际价值。
表达趣味团：笑脸气泡，粉色，表达节奏与趣味。
观点思考团：灯泡，紫色，观点深度与论证。
新手团：指南针，绿色，理解门槛与动手路径。
主编：红笔校对，红色，核对依据与整理优先级。
自定义团：对话拼图，灰色，按自定义设定审阅。

每个图标仍配文字标签，不仅依赖颜色传达身份。头像选择与角色职责分离；换图标不改职责或权重。SVG为透明背景独立素材，带色图章外框由ReviewEmblem.css提供。

## 页面与状态

导航侧栏置于软底板；主要内容使用纸面框。顶部各团卡片承载图标、职责、权重与分数，可筛选评论。评论先出现，点击后在旁边显示已有原文依据、判断摘要与待确认项。手机转单栏，详情提供关闭返回。主编汇总独立于五个加权团。
设置窗口沿用同一色板；桌面左右分类/内容双栏，小屏分类横向滚动，表单独立滚动。窗口内所有文字、输入、开关、提示和确认弹窗都要保持统一浅色。
选中态通过颜色、边界和内凹阴影表达；键盘焦点用明显蓝色轮廓。悬停不作为唯一操作入口。未返回、缺分、错误与空状态需真实展示，不补造分数或判断。

## 可直接复用的风格提示词

请将界面设计为“漫画纸面 × 新拟物桌面”风格。用#e0e5ec浅灰底板和#fffdf5暖白内容纸卡，#252733作为2–3px轮廓与主文字，#ffe28a用于主按钮及选中标签，#505362作为辅助文字。纸卡和气泡配2–4px硬阴影，侧栏/输入区配双向柔阴影或内凹槽。少量网点只用于标题装饰，不铺在正文后面。保持系统中文字体、清晰层级和充足留白。
为不同角色配置可辨认的手绘SVG图标及文字职责：技术芯片、实用算盘、趣味笑脸、思考灯泡、新手指南针、主编红笔，自定义使用拼图气泡。角色图标与身份在卡片、评论、详情和设置中一致。
以评论为主信息，点击评论展开原文依据和判断摘要；桌面双栏、手机单栏。设置窗口与主页面保持相同纸面/墨线/阴影语言。按钮按压时减小硬阴影，交互约100ms，保留清晰键盘焦点并尊重减少动态效果。先保障内容可读、状态清楚和操作可达，再使用漫画装饰。参照本包预览和真实主题CSS实现。

## 集成边界

source目录保留实际组件与其静态相对依赖，适合回到原项目或逐步迁移；API客户端是通用代码，不含用户当前服务配置。离线预览仅加载ReviewBoard及其显示依赖，设置部分是无后端的外观示例，不代表独立可用的审稿系统。桌面源码集成还需在原App入口按README加载主题CSS及review-shell/review-mode容器类。
''', encoding='utf-8')
for source, name in [('ui-style-overview-proof.png','界面示例.png'),('ui-style-settings-proof.png','设置示例.png')]:
    shutil.copyfile(root/'build'/source, stage/name)
# Fix the optional rebuilder's escaping using an unambiguous character expression.
builder = stage/'scripts/build-preview.mjs'
text = builder.read_text(encoding='utf-8')
text = re.sub(r"const js=.*", "const js=result.outputFiles.find(f=>f.path.endsWith('.js')).text.replaceAll('</script','<' + String.fromCharCode(92) + '/script');", text)
builder.write_text(text, encoding='utf-8')
files = sorted(p for p in stage.rglob('*') if p.is_file() and p.name != 'manifest.json')
for p in files:
    rel = p.relative_to(stage).as_posix()
    assert not any(part in {'data','build','node_modules','.venv','.git'} for part in p.relative_to(stage).parts), rel
    if p.suffix in {'.json','.html','.js','.jsx','.css','.md','.mjs'}:
        content = p.read_text(encoding='utf-8')
        assert not re.search(r'weidu|127\.0\.0\.1:3340|gpt-6\.1-sol|sk-[A-Za-z0-9]{20,}',content), rel
manifest = {'name':'漫画拟物UI风格包','date':'2026-10-16','contents':'UI style and synthetic offline preview; no runtime user data','files':[{'path':p.relative_to(stage).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
(stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2), encoding='utf-8')
archive = stage.with_suffix('.zip')
assert not archive.exists(), 'Preserve existing archive'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(stage.rglob('*')):
        if p.is_file(): z.write(p,Path(stage.name)/p.relative_to(stage))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for entry in manifest['files']:
        assert hashlib.sha256(z.read(stage.name+'/'+entry['path'])).hexdigest()==entry['sha256']
report={'archive':str(archive),'bytes':archive.stat().st_size,'files':len(files)+1,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'crc':'passed','manifest':'all files passed','screenChecks':['five groups rendered','comment detail matches synthetic text','group filter','keyword search','settings open and API tab','no browser error logs']}
(root/'build/ui-style-package-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
