export function reviewFailureMessage(error) {
  const value=String(error || '');
  if (/closed the connection unexpectedly|RemoteProtocolError|缺少回复完成标记/.test(value)) return '模型接口提前断开连接，未取得完整审稿。可稍后重新提交；这不是稿件评分结果。';
  if (/timed out|timeout/i.test(value)) return '等待模型回复超时，未取得完整审稿。';
  if (/\b(?:401|403)\b/.test(value)) return '模型接口拒绝访问，请检查密钥与访问权限。';
  return value;
}

export function reviewAvailability(response, { running=false, count=0 } = {}) {
  if (response?.error) return {state:'failed',label:'本团返回失败',reason:reviewFailureMessage(response.error)};
  if (response?.content?.trim()) return {state:'returned',label:count ? `${count} 条评论` : '已返回，暂无可展示短评',reason:''};
  if (running) return {state:'waiting',label:'正在审阅',reason:''};
  return {state:'missing',label:'本轮未取得结果',reason:'这份旧记录未保留失败原因，无法从现有内容恢复该团意见。'};
}
