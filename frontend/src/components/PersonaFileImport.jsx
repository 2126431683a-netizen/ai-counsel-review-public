import { useRef, useState } from 'react';
import { api } from '../api';
import { ROLE_FILE_LIMIT, ROLE_BATCH_LIMIT, decodePersonaFile, parsePersonaFile, personaNameKey } from '../utils/personaFiles.js';

export default function PersonaFileImport({personas=[],disabled=false,onImported,onManual,onBusyChange,createPersona=api.createPersona}) {
  const input=useRef(null),busyRef=useRef(false);
  const [busy,setBusy]=useState(false),[drag,setDrag]=useState(false),[results,setResults]=useState([]);
  const acceptFiles=async files=>{
    if(disabled || busyRef.current || !files.length)return;
    if(files.length>ROLE_BATCH_LIMIT){setResults([{status:'error',message:'一次最多导入20个文件。'}]);return;}
    busyRef.current=true;setBusy(true);onBusyChange?.(true);setResults([]);setDrag(false);
    const records=[],drafts=[],created=[],names=new Set(personas.map(p=>personaNameKey(p.name)));
    try{
      for(const file of files)try{
        if(file.size>ROLE_FILE_LIMIT)throw Error('文件超过1MB，请拆分后导入。');
        const parsed=parsePersonaFile(file.name,decodePersonaFile(await file.arrayBuffer()));
        if(drafts.length+parsed.length>ROLE_BATCH_LIMIT)throw Error('一次最多添加20个角色，请分批导入。');
        drafts.push(...parsed.map(p=>({...p,sourceFile:file.name})));
      }catch(e){records.push({status:'error',message:`${file.name}：${e.message}`});}
      for(const {sourceFile,...draft} of drafts){
        const key=personaNameKey(draft.name);
        if(names.has(key)){records.push({status:'skipped',message:`${draft.name}：同名角色已存在，已跳过。`});continue;}
        try{const saved=await createPersona(draft);created.push(saved);names.add(key);records.push({status:'success',message:`${draft.name}：已添加。`});}
        catch{records.push({status:'error',message:`${sourceFile}：${draft.name}未能保存，请重试。`});}
      }
      if(created.length)onImported?.(created);
      setResults(records);
    }finally{busyRef.current=false;setBusy(false);onBusyChange?.(false);}
  };
  return <div className="review-role-import">
    <div className={`review-role-import__drop ${drag?'is-dragging':''}`} onDragOver={e=>{e.preventDefault();if(!disabled && !busy)setDrag(true);}} onDragLeave={e=>{if(!e.currentTarget.contains(e.relatedTarget))setDrag(false);}} onDrop={e=>{e.preventDefault();setDrag(false);acceptFiles([...e.dataTransfer.files]);}}>
      <span aria-hidden="true" className="review-role-import__icon">＋</span><div><strong>从文件添加评审团</strong><p>拖入人设文件，或点击选择。支持 MD、TXT、JSON，可一次导入多个。</p></div>
      <button type="button" disabled={disabled || busy} onClick={()=>input.current?.click()}>{busy?'正在导入…':'选择人设文件'}</button>
      <input ref={input} type="file" multiple accept=".md,.markdown,.txt,.json" aria-label="选择人设文件" hidden onChange={e=>{const files=[...e.target.files];e.target.value='';acceptFiles(files);}}/>
    </div>
    <div className="review-role-import__foot"><span>同名角色跳过；文件中的模型与连接设置不会导入。最多选8团参与。</span><button type="button" disabled={disabled || busy} onClick={onManual}>手动填写角色</button></div>
    {!!results.length && <div className="review-role-import__results" role="status"><strong>已添加 {results.filter(r=>r.status==='success').length} 个 · 跳过 {results.filter(r=>r.status==='skipped').length} 个 · 失败 {results.filter(r=>r.status==='error').length} 个</strong><ul>{results.map((r,i)=><li key={i} className={`is-${r.status}`}>{r.message}</li>)}</ul></div>}
  </div>;
}
