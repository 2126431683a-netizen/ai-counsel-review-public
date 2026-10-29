// Render the real synthetic connection-check output; never submit a manuscript.
const fs=require('node:fs'),path=require('node:path');
const {createRequire}=require('node:module');
const root=path.resolve(__dirname,'..'),req=createRequire(path.join(root,'frontend/package.json'));
const out=path.join(root,'build/stream-check-preview');fs.mkdirSync(out,{recursive:true});
const data=JSON.parse(fs.readFileSync(path.join(root,'build/stream-connection-real/result.json'),'utf8'));
fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(data));
fs.writeFileSync(path.join(out,'fixture.jsx'),`import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import ReviewBoard from '../../frontend/src/components/ReviewBoard.jsx';
import data from './result.json';
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
function Demo(){const [failed,setFailed]=useState(false);const people=data.personas;const rounds=failed?[{round_number:1,complete:true,responses:people.map(p=>({persona_id:p.id,error:'The provider closed the connection unexpectedly',attempts:2}))}]:data.rounds;return <div className="app review-shell"><main className="chat-interface review-mode" style={{height:'100vh',overflow:'auto',padding:24}}><nav><strong>等长虚构稿 · 连接恢复实测</strong><p>3347字虚构稿；五团与主编实际返回。仅检查连接与展示，分数不代表你的稿件。</p><button onClick={()=>setFailed(false)}>查看成功实测</button><button onClick={()=>setFailed(true)}>查看相同断连示例</button></nav><div className="review-message"><ReviewBoard personas={people} question={data.sample_question || ''} rounds={rounds} currentRound={1} maxRounds={1} roundPolicy="fixed" phase="complete" verdict={failed?{error:'示例：接口未完整返回'}:data.verdict}/></div></main></div>}
createRoot(document.getElementById('root')).render(<Demo/>);`);
req('esbuild').build({entryPoints:[path.join(out,'fixture.jsx')],bundle:true,outfile:path.join(out,'fixture.js'),jsx:'automatic',minify:true,nodePaths:[path.join(root,'frontend/node_modules')],define:{'process.env.NODE_ENV':'"production"','import.meta.env':'{}'}}).then(()=>{
fs.writeFileSync(path.join(out,'index.html'),'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>等长虚构稿连接实测</title><link rel="stylesheet" href="fixture.css"><style>nav{position:sticky;top:0;z-index:20;background:#fff9e8;border:2px solid #292b38;padding:8px 12px;border-radius:10px}nav p{margin:5px 0}nav button{margin-right:8px}.review-teams-heading{scroll-margin-top:130px}main.chat-interface{box-sizing:border-box;min-width:0}</style></head><body><div id="root"></div><script src="fixture.js"></script></body></html>');console.log(out);
}).catch(e=>{console.error(e);process.exitCode=1});
