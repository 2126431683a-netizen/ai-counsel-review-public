"""v8 scoring calibration; retain viewer voice, weights and historic v7 package."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parent.parent
D=ROOT/'desktop'
backup=D/'role_bundle.v7.json'
if not backup.exists():
    current=json.loads((D/'role_bundle.json').read_text(encoding='utf-8'))
    assert current['version']==7
    shutil.copy2(D/'role_bundle.json',backup)
base=json.loads(backup.read_text(encoding='utf-8'))
bundle=copy.deepcopy(base)
guides=D/'role-guides-v8';guides.mkdir(exist_ok=True)
calibration='''# v8 评分标尺与缺团边界

评分对象是这篇稿子实际承诺的内容，而不是你希望作者额外拍的一期。先识别体验、方法分享、完整教程、比较评测等体裁，以及目标观众；每团仍只用原有三个维度，权重不变。

## 给分的含义

- 9–10：按本期有限目标，关键承诺有解释、示例或合理演示安排，没有实质未解决缺口。10不代表工具万能、事实已经外部认证或成片完美。
- 7–8.5：主体成立，有能指出实际影响的局部不足。
- 5–6.5：有用，但仍有明显理解断点或兑现障碍。
- 3–4.5：多个关键承诺缺乏支撑，需要大幅补充或改动。
- 0–2.5：核心主张或路径存在严重矛盾，按目前内容无法成立。

这是语义标尺，不是分数名额或强制分布。先看证据再给分，不因为其他团都给9就跟着给9，不因评论写得顺口或主编喜欢就加分。通常以0.5步进；程序会加权成9.1等显示值，不要在模型维度里制造无依据的小数精度。

## 扣分必须说清影响

每个非满分维度的deduction要指明：哪段原文支持剩余不足、全文已经解释了什么、为什么仍影响本期目标。不能只写“半分作为主观保留／没看到成片所以留点余地／为严谨起见”；没有具体影响就不借这个理由扣分。趣味、节奏等个人口味可以保留，但要说自己的偏好与具体触发点，不伪装成确定缺陷。

缺失类扣分必须对应作者实际承诺必需的一步。产品体验稿展示了制作、调整、导出时，不因没有交代所有观众的设备、资格和开通方式就默认无法上手；只有本期确实承诺观众照做且必要准入条件未说明时，才扣相应路径/前置条件分。已安排画面、演示与资料算稿面已规划；没有成片不自动扣分。后文已答的疑问撤回，不在别的维度暗中重复扣。

评论若指出确定矛盾，评分理由要承认它的实际影响；同一问题不跨维度机械罚分。高分不能掩盖关键矛盾，必要时主编应明确暂缓而不是用均分放行。不能为匹配分数而制造问题，也不能为了保高分把已经证实的关键问题藏到个人口味。

dimension_notes仍逐维提供basis/rationale/context/deduction。basis与context必须是原稿连续真实短引，不拼接、省略或改写。null维度说明无法判定原因，不编一个低分代替未知。引文能匹配只说明有出处，不等于事实正确或判断已经通过。

别团未返回时，它没有投赞成票，也没有投反对票，不替它补话。主编只能综合实际收到的结果，并说明范围。上述评分说明写在详情里，不把标尺和免责声明搬进可见观众评论。
'''
for file in (D/'role-guides-v7').glob('*.md'):
    if file.name not in ['README_怎么用.md','10_抽查结果与边界.md']:
        shutil.copy2(file,guides/file.name)
for pid,role in bundle['personas'].items():
    if pid=='source-editor':continue
    role['system_prompt']+='\n\n'+calibration
    filename=next(f for f in guides.glob('0[1-5]_*.md') if not f.stem.endswith('_角色') and role['name'] in f.stem)
    filename.write_text(role['system_prompt'],encoding='utf-8')
(guides/'11_评分标尺与缺团边界.md').write_text(calibration,encoding='utf-8')
(guides/'README_怎么用.md').write_text('''# 观众审稿 v8

五团观众口吻沿用v7，追加明确评分标尺、禁止无依据的主观扣半分，并区分体验分享与完整教程。角色权重/维度、主编提示、模型、温度及轮数不变。01–06为完整人设MD，_角色为维护片段。全部评论仍为模拟反馈。

新后端保留每团失败原因与尝试次数；只对临时故障有限重试一次，审稿最多同时两团请求。桌面自定义接口默认等待300秒，显式环境配置优先。缺团或评分依据不齐时不算总分，不把缺分当零，不抬高其余权重。依据检查只验证引文与字段，不代表判断正确。

prepare_roles.py默认v8，--viewer-v7恢复上一版。旧ZIP/旧报告保留，新规则只影响新审稿；旧页可重新显示缺失状态和现存依据，但不能凭空找回已丢失的失败原因或评论。EXE没有重新打包。
''',encoding='utf-8')
bundle.update(version=8,name='源宝五团＋主编 · 观众口吻与评分核对v8')
bundle['sources']=[{'file':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(guides.glob('*.md'))]
(D/'role_bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
target=ROOT/'dist/审稿说明与六角色-评分核对v8.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(guides.glob('*.md')):z.write(f,f.name)
    z.write(D/'role_bundle.json','角色配置.json')
    z.write(D/'review_groups.json','五团评分权重.json')
print(json.dumps({'version':8,'reviewersUpdated':5,'weightsUnchanged':True},ensure_ascii=False))
