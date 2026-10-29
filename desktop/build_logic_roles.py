"""Add whole-manuscript paragraph logic checks without changing score weights."""
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / 'desktop'

POLICY = '''# v9 全文逻辑与段落衔接

先按自然段、镜头或章节识别全文推进：这一段承接什么，增加什么，下一段为何从这里展开。逐个检查相邻段的连接，同时回查跨段伏笔、条件和结论。只在内部建立简要结构，输出可核对的依据摘要，不输出内部逐步思考过程，不把逐段检查清单搬进评论。

重点核对：指代和讨论对象是否连续；同一词、比较对象、时间、范围与条件有没有悄悄变；步骤是否依赖尚未具备的前置条件；现象是否被直接当成原因；一个例子是否被推广为所有情况；结论是否得到前文支持；开头承诺在结尾有没有兑现。先确认是在同一条件下谈同一件事，不能把不同情境的差异当成矛盾。

发现疑似跳步后，必须查完整稿件中的后文解释、回指、限定以及画面/资料安排。明确预告的后置解释、悬念、倒叙、平行案例、章节切换和合理口语省略不是默认漏洞；没有“所以/接下来”等连接词也不等于逻辑不通。但若观众在解释出现前已被要求据此理解关键操作或接受结论，仍可指出具体的理解顺序障碍，先承认后文已经解释，不能说全文未解释。

评审团的逻辑批评必须在现有详情字段里给出前段和后段两处连续真实短引：basis放触发短引，context放另一处相关短引（分别来自原稿，禁止拼接成伪引文）；rationale简要说明两段关系、全文已补的内容、还缺的必要桥梁及实际影响；next_step只给最小调整方向，不改写口播。主编在现有自然文字报告中对应交代这两处依据与关系，不生成评审团机器块。关系靠多处才能成立时，可在理由中指明段落位置。证据不足就待确认，不猜作者暗含的前提。可见短评仍像观众说话，不统一套“逻辑链不闭环”术语。

区分：同条件直接冲突/影响核心结论的推导错误；会卡住目标观众的顺序跳步；个人偏好的过渡润色。只有前两类经全文反证后仍成立，才考虑必要修改与相称扣分；第三类可不提、不升级必改。不要求每段都补连接句，不强制每段出一条评论，不为显示认真而凑漏洞。自洽的承接也可以具体认可。

逻辑不是新增评分项：评审团沿用原有三维和权重，归入最贴近且确有影响的一个维度；同一根因多段出现合并处理，不重复扣分，主编仍不参与加权。不用机械关键词或分数判断推理是否成立。
'''

FOCUS = {
    'source-tech': '关注术语、模型/工具分工、输入输出与技术因果是否前后一致。全文已命名的Opus 5.5等作为稿内已知，简称变化不是换模证据；没有外部核查不要凭印象否定版本。',
    'source-practical': '关注目标、条件、成本、步骤和所得是否接得上；免费试用与长期免费、局部节省与总体收益要辨清。同一体验不自动升级为所有人都能复刻的承诺，别擅加完整部署课。',
    'source-surfer': '关注听感上哪里突然换话题、例子接不到主线、梗是否切断必要信息。区分故意反转与漏讲，不把少一个过渡词判成逻辑错误，不为逻辑审查牺牲自然评论。',
    'source-thinker': '重点负责主张—理由—证据—结论，核对前提、因果、概念和推广范围；留意相关性冒充因果、个案推出普遍结论、结尾偷换开头目标。只审本期论证，不扩成哲学或伦理论文。',
    'source-beginner': '按目标新手第一次观看的顺序看必要概念何时出现、步骤依赖何时满足、此处“它/这个”能否对应前文。承认后文解释存在；仅当过晚解释已妨碍中间关键理解/操作时，提顺序调整，不假装整篇未交代。',
    'source-editor': '你最终负责整篇自洽。先独立核对每段承接与开头—结尾，再逐条裁决各团实际意见。在已有主编结论/各团意见取舍中自然交代全文主线是否成立；确有逻辑断点时列前后两处原句、关系、后文已解释什么、剩余影响与最小处理方向。把多个团指向同一根因的评论合并，保留成立的不同视角；撤回已由后文解释或不同条件化解的误读。若核心结论确有未解决的错误，不让加权高分替代判断。没有断点就明确主线成立，不硬凑“潜在逻辑风险”；不要另开无来源的批评清单。',
}

ROLE_TITLES = {'source-tech':'技术评审团', 'source-practical':'实用评审团',
               'source-surfer':'表达趣味评审团', 'source-thinker':'观点思考评审团',
               'source-beginner':'新手评审团', 'source-editor':'主编'}

def clean_legacy_headings(text):
    """Remove inherited chapter version labels, never change rule paragraphs."""
    return re.sub(r'(?m)^(#{1,6}[ \t]+)([^\n]*)$',
                  lambda match: match[1] + re.sub(r'\bv[1-8]\b[ \t]*', '', match[2]).replace(' ：', '：').rstrip(), text)

def main():
    # Preserve the exact previously installed v9 variant for a safe live upgrade.
    legacy = D / 'role_bundle.v9-legacy-headings.json'
    current = json.loads((D / 'role_bundle.json').read_text(encoding='utf-8'))
    if not legacy.exists() and current.get('version') == 9 and any(re.search(r'(?m)^#{1,6} .*\bv[1-8]\b', role['system_prompt']) for role in current['personas'].values()):
        shutil.copy2(D / 'role_bundle.json', legacy)
    frozen = D / 'role_bundle.v8.json'
    if not frozen.exists():
        current = json.loads((D / 'role_bundle.json').read_text(encoding='utf-8'))
        assert current['version'] == 8, 'Need the original scoring-v8 baseline'
        shutil.copy2(D / 'role_bundle.json', frozen)
    baseline = json.loads(frozen.read_text(encoding='utf-8'))
    bundle = copy.deepcopy(baseline)
    guides = D / 'role-guides-v9'
    guides.mkdir(exist_ok=True)
    for file in (D / 'role-guides-v8').glob('*.md'):
        if file.name not in {'README_怎么用.md', '10_抽查结果与边界.md'}:
            (guides / file.name).write_text(clean_legacy_headings(file.read_text(encoding='utf-8')), encoding='utf-8')
    for pid, role in bundle['personas'].items():
        role['system_prompt'] += '\n\n' + POLICY + '\n## 本团的逻辑审查分工\n\n' + FOCUS[pid] + '\n'
        role['system_prompt'] = f'# {ROLE_TITLES[pid]} v9：全文细读与逻辑衔接\n\n' + clean_legacy_headings(role['system_prompt'])
        number = '06' if pid == 'source-editor' else {'source-tech':'01','source-practical':'02','source-surfer':'03','source-thinker':'04','source-beginner':'05'}[pid]
        file = next(f for f in guides.glob(number + '_*.md') if f.stem == number + '_' + role['name'])
        file.write_text(role['system_prompt'], encoding='utf-8')
    (guides / '12_全文逻辑与段落衔接.md').write_text(POLICY + '\n' + '\n\n'.join('## ' + baseline['personas'][pid]['name'] + '\n' + text for pid, text in FOCUS.items()), encoding='utf-8')
    (guides / 'README_怎么用.md').write_text('''# 观众审稿 v9：全文逻辑与段落衔接

五团和主编增加逐段承接、跨段一致、推导与首尾兑现审查。保留观众口吻和原有输出协议，问题详情给前后原句与实际影响。允许后文解释、悬念和自然省略，不把每处转场都当漏洞。主编最后依据实际各团意见核对全文主线。

01–06是完整人设；12是本次新增规则，_角色为历史维护片段。评分维度/权重、模型、温度、轮数与阶段模板不变，不新增逻辑分。prepare_roles.py默认v9，--scoring-v8明确恢复原版v8；v8文件和ZIP保留。规则适用于新审稿，历史不改写。此包仅含角色文字和通用设置模板，不含实际API地址或密钥。旧EXE未重打包。

六份完整人设首行统一标为v9；此前沿用规则中的v6/v7/v8章节编号已移除，规则正文保留。v9指当前完整人设版本，并非工作台软件版本。
''', encoding='utf-8')
    (guides / '10_抽查结果与边界.md').write_text('''# v9 定向抽查与边界

2026-10-16：四次实际模型调用，只用短虚构稿，不重发用户原稿、不写正式历史。思考团认可同一工程局部修改的有限结论，识别分镜在后文解释且出现在关键操作前，未误报全文缺失；在反例中指出单例推广至所有题材、免检查与再次预览直接冲突。新手团承认后文提供了令牌获取方法，但准确指出先用令牌后申请且承诺按顺序跟做的障碍，没有把顺序问题说成全文缺失。主编采用实际收到的思考团意见、限定汇总范围，并撤回两项候选误读。

23项评分/主编/返回完整性回归通过；三份评审团真实输出的现有评论与评分协议仍可解析。最终字段提示统一为原有next_step。维度/权重/阶段模板未变，不新增逻辑分；相同根因不重复扣。定向样本不能证明任意长稿都无误读，也不是人工评分或自然度基准。源码网页的人设可直接更新，无需重启；旧EXE不随包自动更新。
''', encoding='utf-8')
    bundle.update(version=9, name='源宝五团＋主编 · 全文逻辑与段落衔接v9')
    bundle['sources'] = [{'file': f.name, 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(guides.glob('*.md'))]
    (D / 'role_bundle.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
    package = ROOT / 'dist/审稿说明与六角色-逻辑衔接v9.zip'
    saved_package = ROOT / 'dist/审稿说明与六角色-逻辑衔接v9-原始标题备份.zip'
    if package.exists() and not saved_package.exists():
        shutil.copy2(package, saved_package)
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(guides.glob('*.md')):
            archive.write(file, file.name)
        archive.write(D / 'role_bundle.json', '角色配置.json')
        archive.write(D / 'review_groups.json', '五团评分权重.json')
    print(json.dumps({'version': 9, 'promptsUpdated': 6, 'weightsUnchanged': True}, ensure_ascii=False))

if __name__ == '__main__':
    main()
