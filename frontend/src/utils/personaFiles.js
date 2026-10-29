export const ROLE_FILE_LIMIT=1024*1024;
export const ROLE_BATCH_LIMIT=20;
const cleanName=s=>String(s || '').trim().replace(/\s+/g,' ');
export const personaNameKey=s=>cleanName(s).toLocaleLowerCase();

export function decodePersonaFile(bytes) {
  const b=new Uint8Array(bytes);
  const encoding=b[0]===0xff && b[1]===0xfe?'utf-16le':b[0]===0xfe && b[1]===0xff?'utf-16be':'utf-8';
  try{return new TextDecoder(encoding,{fatal:true}).decode(b).replace(/^\uFEFF/,'');}
  catch{throw Error('文件编码无法读取，请保存为 UTF-8 或带标记的 UTF-16 文本。');}
}

function validatePersona(item,fallbackName) {
  if(!item || typeof item!=='object' || Array.isArray(item))throw Error('角色需要包含名称和 system_prompt 正文。');
  for(const field of ['name','role','description'])if(item[field]!=null && typeof item[field]!=='string')throw Error(`${field}需要为文字。`);
  const name=cleanName(item.name || fallbackName);
  const system_prompt=typeof item.system_prompt==='string'?item.system_prompt.trim():'';
  if(!name || name.length>80)throw Error('角色名称需为1–80个字符。');
  if(!system_prompt || system_prompt.length>100000)throw Error('人设正文为空或超过10万字符。');
  const role=cleanName(item.role || `${name}审稿视角`);
  const description=typeof item.description==='string'?item.description.trim():'从文件导入，可编辑角色设定。';
  if(role.length>160 || description.length>1000)throw Error('角色职责或简介过长。');
  return {name,role,description,system_prompt,avatar_emoji:typeof item.avatar_emoji==='string'?item.avatar_emoji:'review:auto'};
}

export function parsePersonaFile(filename,source) {
  const ext=filename.split('.').pop().toLowerCase();
  if(!['md','markdown','txt','json'].includes(ext))throw Error('支持 MD、TXT、JSON 人设文件。');
  const text=source.replace(/^\uFEFF/,'').trim();
  const stem=filename.replace(/\.[^.]+$/,'').replace(/^\d+[_.、\s-]+/,'').replace(/_角色$/,'');
  if(ext==='json'){
    let payload;
    try{payload=JSON.parse(text);}catch{throw Error('JSON格式有误，未导入此文件。');}
    const raw=Array.isArray(payload)?payload:payload?.personas && typeof payload.personas==='object'?Object.values(payload.personas):[payload];
    if(!raw.length || raw.length>ROLE_BATCH_LIMIT)throw Error('一个JSON文件需包含1–20个角色。');
    return raw.map(x=>validatePersona(x,raw.length===1?stem:''));
  }
  const meta={};
  const front=/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(text);
  if(front)for(const line of front[1].split(/\r?\n/)){
    const match=/^(name|role|description|avatar_emoji):\s*(.*?)\s*$/.exec(line);
    if(match)meta[match[1]]=match[2].replace(/^(['"])(.*)\1$/,'$2');
  }
  const named=/^#{1,6}\s*(?:人格|角色|名称)[：:]\s*(.+)$/m.exec(text);
  return [validatePersona({...meta,name:meta.name || named?.[1] || stem,system_prompt:text},stem)];
}
