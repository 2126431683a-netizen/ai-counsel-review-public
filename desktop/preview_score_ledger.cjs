// Isolated visual fixture: no API, secrets, real manuscripts or model calls.
const fs=require('node:fs'),path=require('node:path');
const {createRequire}=require('node:module');
const root=path.resolve(__dirname,'..'),req=createRequire(path.join(root,'frontend/package.json'));
const out=path.join(root,'build/score-ledger-preview');fs.mkdirSync(out,{recursive:true});
const bundle=JSON.parse(fs.readFileSync(path.join(root,'desktop/role_bundle.json'),'utf8'));
fs.writeFileSync(path.join(out,'bundle.json'),JSON.stringify(bundle));
const themes=['ReviewSoftTheme','ReviewComicTheme','ReviewCharacterTheme','ReviewContextTheme','ReviewEditorialTheme','ReviewLayoutTheme','ReviewDiscussionTheme','ReviewImportTheme'].map(t=>`import '../../frontend/src/components/${t}.css';`).join('\n');
fs.writeFileSync(path.join(out,'fixture.jsx'),`import React,{useState} from 'react';import {createRoot} from 'react-dom/client';
import ReviewBoard from '../../frontend/src/components/ReviewBoard.jsx';import bundle from './bundle.json';
import {groupConfig,consumeScore} from '../../frontend/src/utils/reviewScoring.js';
import '../../frontend/src/App.css';import '../../frontend/src/components/ChatInterface.css';${themes}
const people=Object.entries(bundle.personas).filter(([id])=>id!=='source-editor').map(([id,p])=>({id,...p}));
const question='先展示分镜，再生成工程。最后打开预览检查结果。';
function response(p,mode){const cfg=groupConfig(p.system_prompt);const comment='先看分镜再动手，这个顺序我能跟上。';
const notes={comments:[{text:comment,kind:'观众反应',basis:'先展示分镜',rationale:'从已经交代的顺序看，内容确认先于制作。',limits:'这里只验证评分展示。'}],dimension_notes:Object.fromEntries(cfg.dimensions.map(d=>[d.id,{basis:'先展示分镜',context:'最后打开预览检查结果',rationale:'给出了内容确认和检查点，但尚无具体界面示例。',deduction:'操作入口还可以更明确。',checks:d.checks.map(c=>({id:c.id,score:3.5,basis:'先展示分镜',rationale:'基本顺序能跟上。',gap:'具体操作入口尚未展开。'}))}]))};
notes.dimension_notes.commercial={...notes.dimension_notes.commercial,deduction:'不适用：虚构稿没有商业推广依据。',checks:[]};
let raw=comment+'\\n<review-comments>'+JSON.stringify(notes)+'</review-comments>';
if(p.id==='source-beginner'){
 if(mode==='明细缺漏'){delete notes.dimension_notes.clarity.checks;raw=comment+'\\n<review-comments>'+JSON.stringify(notes)+'</review-comments>';}
 if(mode==='分数冲突')raw+='<review-score>'+JSON.stringify({scores:Object.fromEntries(cfg.dimensions.map(d=>[d.id,d.id==='commercial'?null:10])),unrated_reasons:{commercial:'不适用：没有推广'}})+'</review-score>';
 const rated=mode==='分数冲突'?consumeScore(raw,cfg,null,question):{content:raw+'\\n\\n本团稿面评分：**暂缺**（评分数据缺失或格式无效）。',rating:{group_id:cfg.id,status:'invalid',dimensions:[],score:null}};
 return {persona_id:p.id,content:rated.content,review_rating:rated.rating};
}
raw+='<review-score>'+JSON.stringify({scores:Object.fromEntries(cfg.dimensions.map(d=>[d.id,d.id==='commercial'?null:7])),unrated_reasons:{commercial:'不适用：没有推广'}})+'</review-score>';
const v=consumeScore(raw,cfg,null,question);return {persona_id:p.id,content:v.content,review_rating:v.rating};}
function Demo(){const [mode,setMode]=useState('汇总恢复');return <div className="app review-shell"><main className="chat-interface review-mode" style={{height:'100vh',overflow:'auto',display:'block',padding:24,boxSizing:'border-box',minWidth:0}}><nav style={{display:'flex',flexWrap:'wrap',gap:8,marginBottom:20}}><strong>评分显示检查 · 虚构数据</strong>{['汇总恢复','明细缺漏','分数冲突'].map(m=><button key={m} onClick={()=>setMode(m)}>{m}</button>)}</nav><div className="review-message"><ReviewBoard key={mode} personas={people} question={question} rounds={[{round_number:1,complete:true,responses:people.map(p=>response(p,mode))}]} currentRound={1} maxRounds={1} roundPolicy="fixed" phase="complete" verdict={{content:'这是一份虚构界面检查稿，用于验证已有明细的计算和缺分提示。'}}/></div></main></div>}
createRoot(document.getElementById('root')).render(<Demo/>);`);
req('esbuild').build({entryPoints:[path.join(out,'fixture.jsx')],bundle:true,outfile:path.join(out,'fixture.js'),jsx:'automatic',minify:true,nodePaths:[path.join(root,'frontend/node_modules')],define:{'process.env.NODE_ENV':'"production"','import.meta.env':'{}'}}).then(()=>{
fs.writeFileSync(path.join(out,'index.html'),'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>评分显示检查（虚构数据）</title><link rel="stylesheet" href="fixture.css"><style>body{margin:0}#root,.app{min-width:0;max-width:100%}</style></head><body><div id="root"></div><script src="fixture.js"></script></body></html>');console.log(out);
}).catch(e=>{console.error(e);process.exitCode=1});
