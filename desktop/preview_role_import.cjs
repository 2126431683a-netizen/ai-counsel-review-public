// Offline setup harness: all APIs are in-memory, never touches user profiles.
const fs=require('node:fs'),path=require('node:path');
const {createRequire}=require('node:module');
const root=path.resolve(__dirname,'..'),req=createRequire(path.join(root,'frontend/package.json'));
const out=path.join(root,'build/import-preview');fs.mkdirSync(out,{recursive:true});
const jsx=`import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import AdvisorSetup from '../../frontend/src/components/AdvisorSetup.jsx';
import Sidebar from '../../frontend/src/components/Sidebar.jsx';
import {api} from '../../frontend/src/api.js';
import {I18nContext,translate} from '../../frontend/src/i18n.js';
import '../../frontend/src/App.css';
import '../../frontend/src/components/ChatInterface.css';
import '../../frontend/src/components/ReviewSoftTheme.css';
import '../../frontend/src/components/ReviewComicTheme.css';
import '../../frontend/src/components/ReviewCharacterTheme.css';
import '../../frontend/src/components/ReviewContextTheme.css';
import '../../frontend/src/components/ReviewEditorialTheme.css';
import '../../frontend/src/components/ReviewLayoutTheme.css';
import '../../frontend/src/components/ReviewDiscussionTheme.css';
import '../../frontend/src/components/ReviewImportTheme.css';
let people=['技术评审团','实用评审团','表达趣味评审团','观点思考评审团','新手评审团','主编'].map((name,i)=>({id:'demo'+i,name,role:'示例职责',description:'虚构检查角色',system_prompt:'仅审阅虚构示例。',avatar_emoji:'review:auto',color:'#275a91',is_custom:true}));
let settings={advisor_chair_persona_id:'demo5',advisor_default_rounds:3,advisor_default_model:'custom:demo',custom_endpoint_url:'http://localhost/fictional',enabled_providers:{custom:true},advisor_presets:[{id:'demo',name:'示例审稿团',persona_ids:people.slice(0,5).map(p=>p.id),is_default:true,max_rounds:3,default_model:'custom:demo'}]};
api.getPersonas=async()=>people;api.getSettings=async()=>settings;
api.getCustomEndpointModels=async()=>({models:[{id:'custom:demo',name:'示例模型',provider:'Custom'}]});
api.updateSettings=async patch=>{settings={...settings,...patch};return settings;};
api.createPersona=async fields=>{const p={...fields,id:'imported-'+people.length,is_custom:true,color:'#62448f'};people=[...people,p];return p;};
function Demo(){const [open,setOpen]=useState(false),[run,setRun]=useState(null),[version,setVersion]=useState(0);return <I18nContext.Provider value={{language:'zh-CN',t:(s,v)=>translate(s,'zh-CN',v)}}><div className="app review-shell"><Sidebar conversations={[]} currentConversationId={null} onNewAdvisors={()=>{}} onOpenSettings={()=>{}} isOpen={open} onClose={()=>setOpen(false)}/><main className="chat-interface review-mode"><button className="mobile-menu-btn" aria-label="打开菜单" onClick={()=>setOpen(true)}><span className="hamburger-icon"/></button><div className="advisor-setup-scroll"><p className="fixture-note">独立界面示例 · 导入只保存在本页内存 <button onClick={()=>setVersion(v=>v+1)}>检查重新打开</button></p><AdvisorSetup key={version} onStartDebate={setRun}/>{run && <div role="status" className="fixture-note">已选择 {run.maxRounds} 轮，执行方式 {run.roundPolicy}。本示例没有发送模型请求。</div>}</div></main></div></I18nContext.Provider>}
createRoot(document.getElementById('root')).render(<Demo/>);`;
fs.writeFileSync(path.join(out,'fixture.jsx'),jsx);
req('esbuild').build({entryPoints:[path.join(out,'fixture.jsx')],bundle:true,outfile:path.join(out,'fixture.js'),jsx:'automatic',minify:true,nodePaths:[path.join(root,'frontend/node_modules')],define:{'process.env.NODE_ENV':'"production"','import.meta.env':'{}'}}).then(()=>{
fs.writeFileSync(path.join(out,'index.html'),'<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>人设文件与轮次 · 独立检查</title><link rel="stylesheet" href="fixture.css"><style>body{margin:0;font:14px/1.7 "Microsoft YaHei UI",sans-serif;color:#252733}.fixture-note{font-size:12px;margin:0 auto 15px;max-width:1300px;color:#505362}.advisor-setup-scroll{overflow:auto;height:100%;padding:30px}</style></head><body><div id="root"></div><script src="fixture.js"></script></body></html>');console.log(out);
}).catch(e=>{console.error(e);process.exitCode=1});
