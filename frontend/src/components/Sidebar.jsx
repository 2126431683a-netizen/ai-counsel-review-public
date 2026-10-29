import { useRef, useState } from 'react';
import { formatDatePart } from '../utils/dateFormat';
import { useI18n } from '../i18n';
import './Sidebar.css';

function Icon({ name }) {
  const paths = {
    pen: <><path d="m14 4 6 6M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15l-1 6Z"/><path d="M13 21h8"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    settings: <><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/></>,
    trash: <><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6"/></>,
    close: <path d="m6 6 12 12M6 18 18 6"/>,
    check: <path d="m5 12 4 4L19 6"/>,
    collapse: <><path d="M4 4h16v16H4zM10 4v16m6-11-3 3 3 3"/></>,
    expand: <><path d="M4 4h16v16H4zM10 4v16m3-11 3 3-3 3"/></>,
    history: <><path d="M4 8a9 9 0 1 1-1 7M3 3v6h6M12 7v6l4 2"/></>,
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

const reviewTitle = title => {
  const text = title || '未命名稿件';
  const first = text.trim().split(/\s+/)[0];
  return /[\u4e00-\u9fff]/.test(first) && first.length >= 8 ? first : text;
};

export default function Sidebar({ conversations, currentConversationId, onSelectConversation,
  onNewAdvisors, onDeleteConversation, onOpenSettings, isLoading, onAbort,
  isOpen, onClose, dateFormat = 'auto' }) {
  const { t } = useI18n();
  const [confirmingDelete, setConfirmingDelete] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('review.sidebarCollapsed.v1') === 'true'; } catch { return false; }
  });
  const searchRef = useRef(null);
  const setCompact = value => {
    setCollapsed(value);
    try { localStorage.setItem('review.sidebarCollapsed.v1', String(value)); } catch { /* Optional browser preference. */ }
  };
  const filtered = conversations.filter(conv => (conv.title || '').toLowerCase().includes(searchQuery.trim().toLowerCase()));
  return <>
    {isOpen && <button className="sidebar-backdrop" aria-label="收起审稿导航" onClick={onClose}/>}
    <aside className={`sidebar review-sidebar ${isOpen ? 'open' : ''} ${collapsed ? 'is-collapsed' : ''}`} aria-label="审稿导航">
      <button className="sidebar-collapse" onClick={() => setCompact(!collapsed)} aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'} title={collapsed ? '展开侧边栏' : '收起侧边栏'} aria-expanded={!collapsed}><Icon name={collapsed ? 'expand' : 'collapse'}/></button>
      <button className="sidebar-close-btn" onClick={onClose} aria-label={t('Close menu')}><Icon name="close"/></button>
      <header className="sidebar-header">
        <span className="sidebar-brand-icon sidebar-brand-icon--cat"><img src="/yuanbao-ip-cat-256.png" alt="源宝墨镜小猫" width="56" height="56" decoding="async"/></span>
        <div><strong className="sidebar-brand-name">Git源宝</strong><h1 className="sidebar-title">审稿工作台</h1></div>
      </header>
      <div className="sidebar-actions"><button className="sidebar-new-review" onClick={onNewAdvisors} disabled={isLoading} aria-label="新建审稿" title="新建审稿"><Icon name="plus"/><span>新建审稿</span></button></div>
      <button className="sidebar-history-rail" onClick={() => { setCompact(false); requestAnimationFrame(() => searchRef.current?.focus()); }} aria-label={`展开审稿记录，共${conversations.length}篇`} title="审稿记录"><Icon name="history"/><span>{conversations.length}</span></button>
      <div className="sidebar-search"><Icon name="search"/><input ref={searchRef} aria-label="搜索审稿记录" type="search" placeholder="搜索审稿记录" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}/></div>
      <div className="sidebar-list-heading"><h2>审稿记录</h2><span>{filtered.length}</span></div>
      <nav className="conversation-list" aria-label="历史稿件">
        {!filtered.length && <p className="sidebar-empty-state">{searchQuery ? '没有匹配的稿件' : '还没有审稿记录，先放入一篇稿件。'}</p>}
        {filtered.map(conv => {
          const active = conv.id === currentConversationId;
          return <article key={conv.id} className={`conversation-item ${active ? 'active' : ''}`}>
            <button className="conversation-open" onClick={() => onSelectConversation(conv.id)} aria-current={active ? 'page' : undefined} title={conv.title}>
              <span className="conversation-title">{reviewTitle(conv.title)}</span>
              <span className="conversation-meta"><time className="conversation-timestamp" dateTime={conv.created_at}>{formatDatePart(conv.created_at, dateFormat)}</time>{active && <span className="conversation-current">当前</span>}</span>
            </button>
            <div className="conversation-item-actions">
              {isLoading && active ? <button className="history-stop" onClick={onAbort}>{t('Stop')}</button> : confirmingDelete === conv.id ? <>
                <button className="history-icon" onClick={() => { onDeleteConversation(conv.id); setConfirmingDelete(null); }} aria-label={t('Confirm delete')} title={t('Confirm delete')}><Icon name="check"/></button>
                <button className="history-icon" onClick={() => setConfirmingDelete(null)} aria-label={t('Cancel')} title={t('Cancel')}><Icon name="close"/></button>
              </> : <button className="history-icon" onClick={() => setConfirmingDelete(conv.id)} aria-label={t('Delete conversation')} title={t('Delete conversation')}><Icon name="trash"/></button>}
            </div>
          </article>;
        })}
      </nav>
      <footer className="sidebar-footer"><button className="sidebar-settings" onClick={onOpenSettings} aria-label="模型与 API 设置" title="模型与 API 设置"><Icon name="settings"/><span>模型与 API 设置</span></button>
      </footer>
    </aside>
  </>;
}
