"""Build the offline HTML/Markdown guide and optional printable Chinese PDF."""
import argparse
import base64
import html
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out-dir',type=Path,required=True)
    parser.add_argument('--pdf-output',type=Path)
    parser.add_argument('--data',type=Path,default=ROOT/'docs/guide-v11.2.json')
    parser.add_argument('--label',default='v11.2')
    parser.add_argument('--rules',default='v11')
    args=parser.parse_args()
    data=json.loads(args.data.read_text(encoding='utf-8'))
    out=args.out_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    esc=html.escape
    def table(rows):
        return '<div class="table-wrap"><table>'+''.join('<tr>'+''.join(f'<{"th" if i==0 else "td"}>{esc(str(cell))}</{"th" if i==0 else "td"}>' for cell in row)+'</tr>' for i,row in enumerate(rows))+'</table></div>'
    sections=[]
    md=[f'# {data["title"]}',data['subtitle'],'',f'[本次发布与下载]({data["release"]})','']
    for i,c in enumerate(data['chapters'],1):
        content=f'<section id="chapter-{i}"><span class="chapter-number">第{i}章</span><h2>{esc(c["title"])}</h2><p class="intro">{esc(c["intro"])}</p>'
        md.extend([f'## {i}. {c["title"]}','',c['intro'],''])
        if c.get('table'):
            content+=table(c['table'])
            rows=c['table'];md.append('| '+' | '.join(rows[0])+' |');md.append('| '+' | '.join('---' for _ in rows[0])+' |')
            md.extend('| '+' | '.join(row)+' |' for row in rows[1:]);md.append('')
        content+='<ol>'+''.join('<li>'+esc(s)+'</li>' for s in c['steps'])+'</ol>'
        md.extend(f'{j}. {s}' for j,s in enumerate(c['steps'],1));md.append('')
        content+='<aside><strong>使用提醒</strong><p>'+esc(c['note'])+'</p></aside><a class="back" href="#top">返回目录</a></section>'
        md.extend(['> '+c['note'],'']);sections.append(content)
    logo=ROOT/'frontend/public/yuanbao-ip-cat-256.png'
    image='data:image/png;base64,'+base64.b64encode(logo.read_bytes()).decode()
    toc=''.join(f'<a href="#chapter-{i}"><span>{i:02d}</span>{esc(c["title"])}</a>' for i,c in enumerate(data['chapters'],1))
    css='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#faf8ee;color:#10110f;font:15px/1.85 "Microsoft YaHei UI","PingFang SC",sans-serif}header{max-width:1220px;margin:auto;padding:42px 30px 26px;border-bottom:4px solid #ffd21c;display:flex;align-items:center;gap:28px}header img{width:105px;height:105px;object-fit:contain}h1{font-size:32px;line-height:1.4;margin:4px 0 8px}header p{margin:0;color:#595a50}.version{font-size:12px;color:#185bac}.layout{display:grid;grid-template-columns:245px minmax(0,1fr);gap:38px;max-width:1220px;margin:25px auto;padding:0 30px}nav{position:sticky;top:22px;align-self:start;padding:15px 0}nav strong{font-size:14px}nav a{display:flex;gap:10px;color:#45463e;text-decoration:none;font-size:12px;padding:9px 0;border-bottom:1px solid #e2dfd4}nav a span{color:#185bac}main{min-width:0}section{background:#fffef9;border:1px solid #d9d6c9;border-radius:10px;padding:30px 34px;margin-bottom:26px;scroll-margin-top:20px}.chapter-number{font-size:12px;color:#185bac}h2{font-size:25px;margin:5px 0 15px;line-height:1.5}.intro{color:#595a50}ol{padding-left:24px}li{padding-left:5px;margin:14px 0;overflow-wrap:anywhere}.table-wrap{overflow-x:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:12px}td,th{padding:10px 12px;text-align:left;vertical-align:top;border:1px solid #dedbd0;overflow-wrap:anywhere}th{background:#fff4bd}aside{background:#f1f5f9;border-left:3px solid #185bac;padding:16px 18px;margin-top:23px;font-size:13px}aside p{margin:5px 0 0}a{color:#185bac;text-underline-offset:3px}.back{display:inline-block;font-size:11px;margin-top:15px}button{font:inherit;font-size:12px;background:#ffd21c;border:1px solid #10110f;border-radius:4px;padding:8px 14px;cursor:pointer}footer{max-width:1160px;margin:30px auto;padding:25px 30px;border-top:1px solid #d9d6c9;font-size:12px;color:#595a50}@media(max-width:800px){.layout{grid-template-columns:1fr;padding:0 16px;gap:15px}nav{position:static;display:grid;grid-template-columns:1fr 1fr;gap:0 15px}nav strong{grid-column:1/-1}header{padding:25px 18px;gap:12px}header img{width:70px;height:70px}h1{font-size:24px}section{padding:22px 18px}h2{font-size:21px}}@media print{body{font-size:10pt;background:white}header{padding:0 0 12px}h1{font-size:24pt}.layout{display:block;padding:0;margin:0}nav,button,.back{display:none}section{border:0;border-radius:0;padding:20px 0;break-before:page;margin:0}section:first-child{break-before:auto}li,aside,tr{break-inside:avoid}footer{display:none}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}'''
    page=f'<!doctype html><html lang="zh-CN"><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(data["title"])}</title><style>{css}</style><body><header id="top"><img src="{image}" alt="源宝墨镜猫"><div><span class="version">发布v11.2 / 评分规则v11</span><h1>{esc(data["title"])}</h1><p>{esc(data["subtitle"])}</p><button onclick="window.print()">打印教程</button></div></header><div class="layout"><nav aria-label="教程目录"><strong>按你需要的步骤阅读</strong>{toc}</nav><main>{"".join(sections)}</main></div><footer>教程日期：2026-10-18。模型判断和稿面完播预估需要人工复核。<a href="{data["release"]}">GitHub发布页</a></footer></body></html>'
    page=page.replace('发布v11.2 / 评分规则v11','发布'+args.label+' / 评分规则'+args.rules)
    (out/'使用教程.html').write_text(page,encoding='utf-8')
    (ROOT/('docs/使用教程-'+args.label+'.md')).write_text('\n'.join(md),encoding='utf-8')
    plain=[data['title'],data['subtitle'],data.get('reading_note','网页版与安装包同步；评分规则仍为v11。启动器“详细教程”可离线阅读HTML，安装目录也有PDF。'),'']
    for i,c in enumerate(data['chapters'],1):
        plain.extend([f'{i}. {c["title"]}',c['intro']])
        plain.extend(f'  {j}) {step}' for j,step in enumerate(c['steps'],1))
        plain.extend(['  提醒：'+c['note'],''])
    (ROOT/'desktop/使用说明.txt').write_text('\n'.join(plain),encoding='utf-8')
    if args.pdf_output:
        from reportlab.pdfgen import canvas
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.colors import HexColor,white
        from reportlab.lib.enums import TA_LEFT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        font=Path('C:/Windows/Fonts/msyh.ttc')
        pdfmetrics.registerFont(TTFont('GuideCJK',str(font),subfontIndex=0))
        ink=HexColor('#10110f');blue=HexColor('#185bac');muted=HexColor('#595a50');yellow=HexColor('#fff4bd')
        styles={
            'body':ParagraphStyle('body',fontName='GuideCJK',fontSize=9.8,leading=17,textColor=ink,wordWrap='CJK',spaceAfter=8),
            'intro':ParagraphStyle('intro',fontName='GuideCJK',fontSize=10,leading=17.5,textColor=muted,wordWrap='CJK',spaceAfter=13),
            'title':ParagraphStyle('title',fontName='GuideCJK',fontSize=23,leading=32,textColor=ink,wordWrap='CJK',spaceAfter=14),
            'label':ParagraphStyle('label',fontName='GuideCJK',fontSize=9,leading=14,textColor=blue,spaceAfter=6),
            'cell':ParagraphStyle('cell',fontName='GuideCJK',fontSize=8.3,leading=13.5,textColor=ink,wordWrap='CJK'),
            'note':ParagraphStyle('note',fontName='GuideCJK',fontSize=8.8,leading=15,textColor=muted,wordWrap='CJK'),
        }
        def para(text,kind='body'):return Paragraph(esc(text).replace('\n','<br/>'),styles[kind])
        target=args.pdf_output.resolve();target.parent.mkdir(parents=True,exist_ok=True)
        doc=SimpleDocTemplate(str(target),pagesize=(595.28,841.89),leftMargin=43,rightMargin=43,topMargin=76,bottomMargin=45,title=data['title'],author='Git源宝审稿室',pageCompression=1)
        story=[]
        for i,c in enumerate(data['chapters'],1):
            if i>1:story.append(PageBreak())
            story.extend([para(f'使用教程  /  第{i}章','label'),para(c['title'],'title'),para(c['intro'],'intro')])
            if c.get('table'):
                rows=c['table'];widths=[120,389] if len(rows[0])==2 else [104,285,120]
                t=Table([[para(str(v),'cell') for v in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
                t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),yellow),('GRID',(0,0),(-1,-1),.5,HexColor('#d9d6c9')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
                story.extend([t,Spacer(1,14)])
            for j,s in enumerate(c['steps'],1):story.append(para(f'{j}. {s}'))
            note=Table([[para('使用提醒：'+c['note'],'note')]],colWidths=[509])
            note.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),HexColor('#f1f5f9')),('BOX',(0,0),(-1,-1),.5,HexColor('#dce2e7')),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
            story.extend([Spacer(1,8),note])
        def decorate(c,document):
            c.saveState();c.setFillColor(HexColor('#faf8ee'));c.rect(0,0,595.28,841.89,fill=1,stroke=0)
            c.setFillColor(HexColor('#ffd21c'));c.rect(43,781,509,4,fill=1,stroke=0)
            c.drawImage(str(logo),43,793,width=27,height=27,mask='auto',preserveAspectRatio=True)
            c.setFont('GuideCJK',9);c.setFillColor(ink);c.drawString(80,800,'Git源宝审稿室  /  v11.2')
            c.setFillColor(muted);c.setFont('GuideCJK',8);c.drawRightString(552,800,'安装 · 模型接入 · 审阅 · 自动完播预估')
            c.setStrokeColor(HexColor('#d9d6c9'));c.line(43,34,552,34);c.drawString(43,22,'本地使用教程  |  2026-10-18');c.drawRightString(552,22,str(document.page));c.restoreState()
        doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
        shutil.copy2(target,out/target.name)
    print(json.dumps({'guideChapters':len(data['chapters']),'htmlBytes':(out/'使用教程.html').stat().st_size,'pdf':bool(args.pdf_output)}))

if __name__=='__main__':main()
