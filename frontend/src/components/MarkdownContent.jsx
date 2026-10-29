import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const REMARK_PLUGINS = [remarkGfm];

export function MarkdownRenderer({ children, components }) {
  const content = typeof children === 'string' ? children : String(children || '');

  return <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={components}>{content}</ReactMarkdown>;
}

export default function MarkdownContent({ children, className = '', components }) {
  const content = typeof children === 'string' ? children : String(children || '');
  const classes = ['markdown-content', className].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      <MarkdownRenderer components={components}>{content}</MarkdownRenderer>
    </div>
  );
}
