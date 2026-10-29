import {useEffect, useRef, useState} from 'react';
import {api} from '../api';
import './LocalModelConnect.css';

const SERVICES = {ollama:{name:'Ollama',url:'http://127.0.0.1:11434'},lmstudio:{name:'LM Studio',url:'http://127.0.0.1:1234/v1'},openai:{name:'其他本地API',url:'http://127.0.0.1:1234/v1'}};

export default function LocalModelConnect({onConnected, disabled=false, defaultOpen=false}) {
  const [open,setOpen]=useState(defaultOpen);
  const [service,setService]=useState('ollama');
  const [url,setUrl]=useState(SERVICES.ollama.url);
  const [key,setKey]=useState('');
  const [models,setModels]=useState([]);
  const [model,setModel]=useState('');
  const [busy,setBusy]=useState(false);
  const [result,setResult]=useState(null);
  const generation=useRef(0);
  useEffect(()=>()=>{generation.current++;},[]);
  const change=(kind,value)=>{
    generation.current++;
    setResult(null);setModels([]);setModel('');
    if(kind==='service'){setService(value);setUrl(SERVICES[value].url);setKey('');}
    if(kind==='url')setUrl(value);
    if(kind==='key')setKey(value);
  };
  const connect=async(action)=>{
    const stamp=++generation.current;setBusy(true);setResult(null);
    if(action==='check'){setModels([]);setModel('');}
    try {
      const value=await api.localModels(action,{service,url,api_key:key || null,model:action==='use'?model:null});
      if(stamp!==generation.current)return;
      setResult(value);
      if(value.success){setModels(value.models || []);setModel(action==='use'?value.model:value.models?.[0]?.id || '');setUrl(value.url || url);}
      if(value.success && action==='use')await onConnected?.(value);
    } catch(error){if(stamp===generation.current)setResult({success:false,message:error.message});}
    finally{if(stamp===generation.current)setBusy(false);}
  };
  return <section className="local-connect">
    <button className="local-connect__toggle" type="button" onClick={()=>setOpen(!open)} aria-expanded={open}>
      <svg viewBox="0 0 24 24" width="25" height="25" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4M7 9h3m-3 3h7"/></svg>
      <span><strong>连接本地模型</strong><small>Ollama / LM Studio，检测后直接选择</small></span><span aria-hidden="true">{open?'−':'＋'}</span>
    </button>
    {open && <div className="local-connect__body">
      <p className="local-connect__intro">先打开本地模型软件，再选服务并检测。连接单独保存，已有云端API仍可使用。</p>
      <div className="local-connect__services" role="group" aria-label="本地模型软件">{Object.entries(SERVICES).map(([id,s])=><button key={id} type="button" aria-pressed={service===id} disabled={busy || disabled} onClick={()=>change('service',id)}>{s.name}</button>)}</div>
      <p className="local-connect__hint">{service==='ollama'?'打开Ollama并下载一个聊天模型。':'在本地软件中下载聊天模型，并开启本地服务。LM Studio可在Developer页面启动服务。'}</p>
      <details className="local-connect__advanced"><summary>修改地址或填写密钥</summary><label>本机服务地址<input value={url} disabled={busy || disabled} onChange={e=>change('url',e.target.value)} placeholder={SERVICES[service].url}/></label>{service!=='ollama' && <label>访问密钥（通常留空）<input type="password" autoComplete="off" value={key} disabled={busy || disabled} onChange={e=>change('key',e.target.value)}/></label>}</details>
      <button className="local-connect__detect" type="button" disabled={busy || disabled} onClick={()=>connect('check')}>{busy?'正在连接…':models.length?'重新检测':'检测本地模型'}</button>
      {result && <p className={`local-connect__result ${result.success?'is-ok':'is-error'}`} role={result.success?'status':'alert'}>{result.message}</p>}
      {!!models.length && <div className="local-connect__choose"><label>选择聊天模型<select value={model} disabled={busy || disabled} onChange={e=>{setModel(e.target.value);setResult(null);}}>{models.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label><button type="button" disabled={!model || busy || disabled} onClick={()=>connect('use')}>用这个模型审稿</button></div>}
      <details className="local-connect__help"><summary>还没装本地模型软件？</summary><p>可先安装<a href="https://ollama.com/download" target="_blank" rel="noreferrer">Ollama</a>或<a href="https://lmstudio.ai/" target="_blank" rel="noreferrer">LM Studio</a>，在软件里下载适合电脑的聊天模型。这里负责连接服务，不会自动下载大模型。</p><p>检测只检查模型列表；模型能否顺利审长稿，还取决于电脑性能、上下文长度与模型能力。首次推理可能需要加载模型。</p></details>
    </div>}
  </section>;
}
