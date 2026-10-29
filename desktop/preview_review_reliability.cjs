// Offline fixtures: never call the user's API or write profile data.
const fs=require('node:fs'),path=require('node:path');
const {createRequire}=require('node:module');
const root=path.resolve(__dirname,'..'),req=createRequire(path.join(root,'frontend/package.json'));
const out=path.join(root,'build/reliability-preview');fs.mkdirSync(out,{recursive:true});
const bundle=JSON.parse(fs.readFileSync(path.join(root,'desktop/role_bundle.json'),'utf8'));
fs.writeFileSync(path.join(out,'people.json'),JSON.stringify(Object.entries(bundle.personas).filter(([pid])=>pid!=='source-editor').map(([id,p])=>({id,...p}))));
fs.writeFileSync(path.join(out,'fixture.jsx'),`import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import ReviewBoard from '../../frontend/src/components/ReviewBoard.jsx';
import people from './people.json';
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
const question='先确认内容，再生成工程。改完回到预览检查。';
function response(p,broken=false){const cfg=JSON.parse(p.system_prompt.match(/<review-group-config>(.*?)<\\/review-group-config>/s)[1]);return {persona_id:p.id,content:'改完我还是想再看一遍。\\n<review-comments>'+JSON.stringify({comments:[{text:'改完我还是想再看一遍。',basis:'改完回到预览检查。',rationale:'有明确检查步骤',kind:'观众反应'}],dimension_notes:Object.fromEntries(cfg.dimensions.map(d=>[d.id,{basis:broken?'原稿不存在的内容':'先确认内容',rationale:'内容确认在制作之前',deduction:'保留本例主观判断'}]))})+'</review-comments>\\n<review-score>'+JSON.stringify({scores:Object.fromEntries(cfg.dimensions.map(d=>[d.id,8]))})+'</review-score>'};}
function Demo(){const [mode,setMode]=useState('历史缺团');let responses=people.map(p=>response(p,mode==='依据不匹配'));if(mode==='历史缺团')responses=responses.filter((r,i)=>![1,2].includes(i));if(mode==='接口失败')responses[1]={persona_id:people[1].id,content:null,error:'请求超时（已重试1次）',attempts:2};if(mode==='审阅中')responses=responses.slice(0,2);return <div className="app review-shell"><main className="chat-interface review-mode" style={{padding:'24px',overflow:'auto',height:'100vh'}}><nav style={{display:'flex',flexWrap:'wrap',gap:8,marginBottom:20}}>{['历史缺团','接口失败','依据不匹配','完整返回','审阅中'].map(m=><button key={m} onClick={()=>setMode(m)}>{m}</button>)}<span>独立虚构示例，不调用接口</span></nav><div className="review-message"><ReviewBoard personas={people} question={question} rounds={[{round_number:1,complete:mode!=='审阅中',responses}]} currentRound={1} maxRounds={1} roundPolicy="fixed" phase={mode==='审阅中'?'round':'complete'} isRunning={mode==='审阅中'} verdict={mode==='审阅中'?null:{content:'本例仅检查返回状态与评分依据。'}}/></div></main></div>}
createRoot(document.getElementById('root')).render(<Demo/>);`);
req('esbuild').build({entryPoints:[path.join(out,'fixture.jsx')],bundle:true,outfile:path.join(out,'fixture.js'),jsx:'automatic',minify:true,nodePaths:[path.join(root,'frontend/node_modules')],define:{'process.env.NODE_ENV':'"production"','import.meta.env':'{}'}}).then(()=>{
fs.writeFileSync(path.join(out,'index.html'),'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>结果完整性检查</title><link rel="stylesheet" href="fixture.css"></head><body><div id="root"></div><script src="fixture.js"></script></body></html>');console.log(out);
}).catch(e=>{console.error(e);process.exitCode=1});
