// Explicit source allowlist and synthetic preview; never reads application data.
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const req = createRequire(path.resolve(__dirname, '../frontend/package.json'));
const esbuild = req('esbuild');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'dist/漫画拟物UI风格包-20261016');
if (fs.existsSync(out)) throw Error('Staging directory already exists; preserve it and choose a new name.');
function write(rel, content) { const p = path.join(out, rel); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, content); }
const copied = new Set();
function resolveLocal(from, spec) {
  const base = path.resolve(path.dirname(from), spec);
  return [base, ...['.js','.jsx','.css','.json','/index.js','/index.jsx'].map(x => base+x)].find(p => fs.existsSync(p) && fs.statSync(p).isFile());
}
function copySource(rel) {
  if (copied.has(rel)) return;
  if (!rel.startsWith('frontend/src/')) throw Error('Outside UI source: '+rel);
  copied.add(rel);
  const file = path.join(root,rel), content = fs.readFileSync(file,'utf8');
  write('source/'+rel,content);
  if (/\.(jsx?|css)$/.test(rel)) {
    const imports = [...content.matchAll(/(?:from\s*|import\s*|import\s*\()\s*['"]([^'"]+)['"]/g)];
    for (const match of imports) if (match[1].startsWith('.')) {
      const resolved = resolveLocal(file, match[1]);
      if (!resolved) throw Error('Missing import '+rel+': '+match[1]);
      copySource(path.relative(root,resolved).split(path.sep).join('/'));
    }
  }
}
const entries = ['ReviewBoard.jsx','ReviewEmblem.jsx','Sidebar.jsx','AdvisorSetup.jsx','Settings.jsx','SearchableModelSelect.jsx','ReviewSoftTheme.css','ReviewComicTheme.css','ReviewSettingsTheme.css','ChatInterface.css','StageCopyButtons.css'];
entries.forEach(f=>copySource('frontend/src/components/'+f));
['App.css','ModeToggle.css','index.css'].forEach(f=>copySource('frontend/src/'+f));
write('LICENSE', fs.readFileSync(path.join(root,'LICENSE')));
for (const f of ['review-comic-design.md','review-settings-design.md']) write('design/'+f,fs.readFileSync(path.join(root,'desktop',f)));
write('design/tokens.json', JSON.stringify({surface:'#e0e5ec',paper:'#fffdf5',ink:'#252733',secondary:'#505362',yellow:'#ffe28a',shadow:'#b8bcc2',highlight:'#ffffff',border:'2px solid #252733',comicShadow:'3px 3px 0 #252733',softShadow:'6px 6px 12px #b8bcc2,-6px -6px 12px #fff',insetShadow:'inset 4px 4px 8px #b8bcc2,inset -4px -4px 8px #fff',motion:'100ms ease-out',fontFamily:'Microsoft YaHei UI, PingFang SC, sans-serif'},null,2));
write('README.md', `# 漫画 × 拟物 UI 风格包

版本：2026-10-16。提取自当前中文审稿工作台，包含最新设置窗口样式。

## 直接看效果

解压后双击 \\预览.html\\（去掉此处路径分隔符），浏览器即可离线打开。点击评审团筛选评论、点击评论查看依据、搜索评论、展开主编意见；右上角可打开设置外观演示。
预览使用真实 ReviewBoard / ReviewEmblem 组件，所有稿件、评论和分数均为专门编写的虚构示例。设置预览是交互外观样例，不连接后端，也不保存密钥。

## 文件内容

- 预览.html：无需安装依赖的离线交互演示。
- icons/：五个评审团、主编及自定义团，共 7 个独立 SVG。
- source/frontend/src/：当前样式与相关组件的相对依赖源码。Settings 等集成组件依赖原应用服务，不能将其当作完整应用直接启动。
- design/：颜色/阴影令牌、漫画与设置窗口规范。
- preview/demo.jsx、preview/demo.css：虚构示例源码。
- scripts/build-preview.mjs、package.json：可选的预览重建入口。
- LICENSE、NOTICE.md、third-party/：上游归属和预览依赖许可证。
- manifest.json：文件大小及 SHA-256 校验清单。

## 移植方式

React 项目先安装 package.json 中依赖。按需复制 source/frontend/src 下组件及其依赖，保留路径结构。
样式顺序：原组件基础 CSS → ReviewSoftTheme.css → ReviewComicTheme.css。设置窗口在 Settings.css 后加载 ReviewSettingsTheme.css。
根容器使用 app review-shell，审稿内容容器使用 review-mode；这些选择器限定了主题范围，不是任意网站一键换肤 CSS。
图标组件使用 ReviewEmblem，persona.avatar_emoji 可设 review:tech / value / fun / think / learn / editor / custom，review:auto 为自动匹配，也支持自定义表情。
图标变化不应改变角色实际职责或评分权重。当前权重为实用30%、技术25%、新手20%、表达趣味15%、观点思考10%，主编不作为第六个加权团。

可选重建：在解压目录安装依赖后运行 npm run build:preview，重新生成预览.html。重建需要 Node.js；观看预览无需 Node.js。

这是 UI 风格及组件源码包，不是 EXE 安装包或完整后端。未包含个人稿件、审稿历史、API 配置、凭据、角色提示词档案、原应用运行数据或旧界面截图。
` .replace('\\预览.html\\（去掉此处路径分隔符）','“预览.html”'));
write('NOTICE.md', `# 归属与复用

原应用 The AI Counsel：https://github.com/jacob-bd/the-ai-counsel
上游 Copyright (c) 2025 Jacob Ben David，MIT License，原文见 LICENSE。
本包包括在其基础上定制的中文漫画×拟物主题、评审团 SVG 图标与组件改动。复用请保留上游许可证和署名。本包新增主题、图标与示例也按所附 MIT 许可提供。
离线预览打包使用 React、react-dom、react-markdown、remark-gfm 等依赖，具体第三方许可证见 third-party/。字体使用系统字体，不附带字体文件。
`);
write('preview/demo.jsx', `import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import ReviewBoard from '../source/frontend/src/components/ReviewBoard.jsx';
import ReviewEmblem from '../source/frontend/src/components/ReviewEmblem.jsx';
import '../source/frontend/src/components/Settings.css';
import '../source/frontend/src/components/ReviewSoftTheme.css';
import '../source/frontend/src/components/ReviewComicTheme.css';
import '../source/frontend/src/components/ReviewSettingsTheme.css';
import './demo.css';
const groups=[['tech','source-tech','技术评审团',25,8.2,'这个例子挺直观，不过别把一次测试说成所有模型都行。','我只测试了模型A的一份笔记。','单次示例只能支持这次体验，不能推到所有模型。'],['value','source-practical','实用评审团',30,8.6,'先告诉我免费额度够不够整理一本书，观众才知道值不值得折腾。','免费版每天可以整理三份笔记。','已经交代额度，可再解释一份的长度。'],['fun','source-surfer','表达趣味评审团',15,8.4,'拿整理书桌打比方很顺，后面两个类似的比喻可以省一个。','就像把散在桌上的卡片重新归类。','首个比喻已经完成解释，后面的相似表达收益有限。'],['think','source-thinker','观点思考评审团',10,8.0,'能归类不等于真的理解，这个边界说出来会更可信。','AI帮我们完成了归类，但最后还要自己检查。','原稿已有检查提醒；如果强调理解，补一个反例更有说服力。'],['learn','source-beginner','新手评审团',20,8.8,'终于看到具体步骤了！第一步在哪点，录屏里标一下就能跟。','打开笔记页面，点击右上角的整理按钮。','口播已有入口，确认后期画面能指向按钮即可。']];
const personas=groups.map(([icon,id,name,weight])=>({id,name,avatar_emoji:'review:'+icon,system_prompt:'<review-group-config>'+JSON.stringify({id,name,weight,dimensions:[{id:'sample',name:'演示维度',weight:100}]})+'</review-group-config>'}));
const rounds=[{round_number:1,responses:groups.map(([icon,id,name,weight,score,text,basis,rationale])=>({persona_id:id,content:text+'\\n\\n### 给作者的备忘\\n本页仅为风格演示。\\n<review-comments>'+JSON.stringify([{text,basis,rationale,limits:'虚构稿件与模拟意见，仅用于界面预览。',next_step:'结合实际脚本和录屏确认后再决定。',kind:'示例意见'}])+'</review-comments>\\n<review-score>'+JSON.stringify({scores:{sample:score},unrated_reasons:{}})+'</review-score>'}))}];
const categories=['通用设置','模型与 API','模型来源','审稿流程提示词','联网搜索','备份与重设'];
function Demo(){const [open,setOpen]=useState(false),[section,setSection]=useState(0);return <div className="app review-shell"><aside className="demo-sidebar"><div className="demo-brand"><ReviewEmblem persona={{name:'主编'}}/><div><strong>审稿工作室</strong><small>漫画 × 拟物</small></div></div><span className="demo-tag">离线风格样本</span><p>纸面的利落，桌面的柔和。</p><div className="demo-swatches">{['#e0e5ec','#fffdf5','#ffe28a','#252733'].map(c=><span key={c} title={c} style={{background:c}}/>)}</div><h3>评审团图标</h3><div className="demo-icons">{[...groups.map(g=>[g[0],g[2]]),['editor','主编'],['custom','自定义']].map(([id,name])=><div key={id}><ReviewEmblem persona={{name,avatar_emoji:'review:'+id}}/><span>{name}</span></div>)}</div><button className="demo-button" onClick={()=>setOpen(true)}>设置外观预览 ↗</button><small>稿件、评论、分数均为虚构示例。无网络请求，无密钥存储。</small></aside><main className="demo-main review-mode"><div className="demo-banner"><strong>UI STYLE KIT / 2026</strong><span>点击评论，展开审阅依据</span></div><ReviewBoard personas={personas} rounds={rounds} maxRounds={1} question="【虚构演示稿】AI整理读书笔记：打开笔记页面，点击右上角的整理按钮。免费版每天可以整理三份笔记。我只测试了模型A的一份笔记。就像把散在桌上的卡片重新归类。AI帮我们完成了归类，但最后还要自己检查。" verdict={{content:'### 演示主编意见\\n先保留具体步骤与检查提醒，确认录屏覆盖按钮位置；一次测试的结论限定在当前样本。以上仅为界面示例。'}}/></main>{open&&<div className="settings-overlay" onClick={e=>{if(e.target===e.currentTarget)setOpen(false)}}><section className="settings-modal" role="dialog" aria-modal="true" aria-label="设置外观演示"><header className="settings-header"><div><h2>设置</h2><p className="settings-header-subtitle">外观演示 · 不连接或保存配置</p></div><button className="close-button" autoFocus onClick={()=>setOpen(false)} aria-label="关闭设置">×</button></header><div className="settings-body"><nav className="settings-sidebar">{categories.map((c,i)=><button key={c} className={'sidebar-nav-item '+(i===section?'active':'')} onClick={()=>setSection(i)}>{c}</button>)}</nav><div className="settings-main-panel"><h3>{categories[section]}</h3><p className="section-description">这是独立的设置外观样本，输入内容不会发送或保存。</p>{section===0?<><h4>界面语言</h4><select className="select-input" aria-label="界面语言"><option>简体中文</option><option>English</option></select><div className="credential-storage-panel">浅灰凹槽、粗墨线与柔和阴影共同区分表单层级。</div></>:section===1?<div className="api-key-section"><label htmlFor="demo-url">自定义模型服务 · 演示输入</label><div className="api-key-input-row"><input id="demo-url" placeholder="填写你的服务地址（此处不连接）"/><button className="test-button" disabled>仅展示</button></div><p className="api-key-hint">正式功能请使用原应用；本页仅预览样式。</p></div>:section===2?<div className="credential-storage-panel">{['本地模型','自定义 API','远程模型'].map(c=><label className="demo-check" key={c}><input type="checkbox" defaultChecked/>{c}</label>)}</div>:section===3?<textarea className="demo-textarea" aria-label="示例提示词" defaultValue="示例：先通读全文，再核对具体原句；没有问题时不凑数。"/>:<div className="api-key-section"><h4>{categories[section]}样式卡片</h4><p className="setting-description">黄纸按钮、浅色表单、清晰边界。</p><button className="demo-button" disabled>样式演示</button></div>}</div></div><footer className="settings-footer"><button className="demo-button" onClick={()=>setOpen(false)}>关闭</button><span className="settings-autosave-status">离线演示，不保存配置</span></footer></section></div>}</div>}
createRoot(document.getElementById('root')).render(<Demo/>);
`);
write('preview/demo.css', `:root{--font-scale:1}*{box-sizing:border-box}body{margin:0;background:#e0e5ec;color:#252733;font:14px/1.7 'Microsoft YaHei UI','PingFang SC',sans-serif}button,input,textarea,select{font:inherit}.app.review-shell{display:flex;align-items:flex-start;min-height:100vh}.demo-sidebar{width:248px;flex-shrink:0;padding:28px 22px;position:sticky;top:0;max-height:100vh;overflow:auto;border-right:3px solid #252733}.demo-brand{display:flex;align-items:center;gap:14px;margin-bottom:24px}.demo-brand strong{font-size:20px;display:block}.demo-brand small{display:block}.demo-tag{background:#ffe28a;border:2px solid #252733;padding:3px 8px;box-shadow:2px 2px 0 #252733;font-weight:800}.demo-swatches{display:flex;gap:9px;margin:22px 0}.demo-swatches span{width:32px;height:32px;border:2px solid #252733;border-radius:8px;box-shadow:2px 2px 0 #252733}.demo-icons{display:grid;grid-template-columns:1fr 1fr;gap:18px 10px;margin:20px 0}.demo-icons>div{display:flex;align-items:center;flex-direction:column;gap:8px}.demo-icons>div>span:last-child{font-size:11px}.demo-button{padding:9px 13px;background:#ffe28a;color:#252733;border:2px solid #252733;border-radius:7px;box-shadow:3px 3px 0 #252733;cursor:pointer;font-weight:800}.demo-button:active{box-shadow:none;transform:translate(2px,2px)}.demo-sidebar>small{display:block;margin-top:18px;font-size:11px;color:#505362}.demo-main{padding:28px 32px;width:calc(100% - 248px);min-width:0}.demo-banner{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-bottom:22px;font-size:12px;letter-spacing:1px}.demo-check{display:flex;gap:10px;align-items:center;margin:12px 0}.demo-textarea{width:100%;min-height:190px;padding:16px;background:#e0e5ec;border:2px solid #252733;border-radius:9px;box-shadow:inset 4px 4px 8px #b8bcc2,inset -4px -4px 8px #fff}.settings-modal{display:flex;flex-direction:column}.settings-header{display:flex;align-items:center;justify-content:space-between}.settings-body{display:flex;flex:1;overflow:hidden}.settings-sidebar{display:flex;flex-direction:column}.settings-main-panel{flex:1;overflow:auto}.settings-footer{display:flex;align-items:center}.markdown-content{overflow-wrap:anywhere}.markdown-content p{margin:8px 0}.demo-button:focus-visible{outline:3px solid #275a91;outline-offset:4px}[hidden]{display:none!important}@media(max-width:1000px){.demo-sidebar{width:200px;padding:22px 14px}.demo-main{width:calc(100% - 200px);padding:20px}}@media(max-width:760px){.app.review-shell{display:block}.demo-sidebar{position:static;width:100%;max-height:none;border-right:0;border-bottom:3px solid #252733;padding:20px}.demo-brand{margin-bottom:14px}.demo-icons{grid-template-columns:repeat(4,minmax(0,1fr));gap:15px}.demo-icons .review-emblem{width:43px;height:43px}.demo-main{width:100%;padding:18px 12px}.demo-swatches{margin:14px 0}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}`);
write('scripts/build-preview.mjs', `import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const result=await build({entryPoints:[path.join(root,'preview/demo.jsx')],bundle:true,write:false,outfile:'demo.js',minify:true,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
const js=result.outputFiles.find(f=>f.path.endsWith('.js')).text.replaceAll('</script','<\\/script');
const css=result.outputFiles.find(f=>f.path.endsWith('.css')).text;
fs.writeFileSync(path.join(root,'预览.html'),'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>漫画 × 拟物 · UI风格包</title><style>'+css+'</style></head><body><div id="root"></div><script>'+js+'</script></body></html>');
console.log('预览已重建。');
`);
const pkg=JSON.parse(fs.readFileSync(path.join(root,'frontend/package.json'),'utf8'));
write('package.json',JSON.stringify({name:'comic-soft-review-ui-kit',version:'1.0.0',private:true,type:'module',scripts:{'build:preview':'node scripts/build-preview.mjs'},dependencies:pkg.dependencies,devDependencies:{esbuild:req('esbuild/package.json').version}},null,2));
(async()=>{
 const result=await esbuild.build({entryPoints:[path.join(out,'preview/demo.jsx')],bundle:true,write:false,outfile:'demo.js',minify:true,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'},nodePaths:[path.join(root,'frontend/node_modules')],metafile:true});
 const js=result.outputFiles.find(f=>f.path.endsWith('.js')).text.replaceAll('</script','<\\/script');
 const css=result.outputFiles.find(f=>f.path.endsWith('.css')).text;
 write('预览.html','<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>漫画 × 拟物 · UI风格包</title><style>'+css+'</style></head><body><div id="root"></div><script>'+js+'</script></body></html>');
 // Render the actual SVG artwork from the original component, no raster conversion.
 const iconModule=await esbuild.build({stdin:{contents:"export {default} from './frontend/src/components/ReviewEmblem.jsx'",resolveDir:root},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],loader:{'.css':'empty'},nodePaths:[path.join(root,'frontend/node_modules')]});
 const m={exports:{}};new Function('require','module','exports',iconModule.outputFiles[0].text)(req,m,m.exports);
 const React=req('react'),{renderToStaticMarkup}=req('react-dom/server');
 for(const id of ['tech','value','fun','think','learn','editor','custom']){
  const html=renderToStaticMarkup(React.createElement(m.exports.default,{persona:{avatar_emoji:'review:'+id},decorative:false}));
  const svg=html.match(/<svg[\s\S]*?<\/svg>/)[0].replace('aria-hidden="true"','role="img" aria-label="'+id+'"').replace('<svg','<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"');
  write('icons/'+id+'.svg',svg);
 }
 const licensePackages=new Set();
 for(const file of Object.keys(result.metafile.inputs)){
  if(!file.includes('node_modules'))continue;
  let dir=path.dirname(path.resolve(file));
  while(dir!==path.dirname(dir)&&!fs.existsSync(path.join(dir,'package.json')))dir=path.dirname(dir);
  if(!fs.existsSync(path.join(dir,'package.json'))||licensePackages.has(dir))continue;
  licensePackages.add(dir);
  const p=JSON.parse(fs.readFileSync(path.join(dir,'package.json'),'utf8'));
  const names=fs.readdirSync(dir).filter(f=>/^(licen[cs]e|copying|notice)(\.|$)/i.test(f)&&fs.statSync(path.join(dir,f)).isFile());
  for(const name of names)write('third-party/'+p.name.replaceAll('/','__')+'/'+name,fs.readFileSync(path.join(dir,name)));
 }
 write('source-files.json',JSON.stringify([...copied].sort(),null,2));
 console.log(JSON.stringify({staging:out,sourceFiles:copied.size,licensePackages:licensePackages.size}));
})().catch(e=>{console.error(e);process.exitCode=1});
