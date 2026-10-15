import { useEffect, useRef, useState } from 'react';
import type { documentEvidence } from './flowFrames';

const statuses = { unread: '尚未读取', found: '搜索已定位', reading: 'Agent 正在读取', read: '已读取', failed: '本次读取未取得正文' };

/** Observer-only document preview; selecting a card never executes an Agent tool. */
export function DocumentEvidence({ source, running }: { source: ReturnType<typeof documentEvidence>; running: boolean }) {
  const [selection, setSelection] = useState<{ id: string; cursor: string } | null>(null);
  const selectedId = selection?.cursor === source.readCursor ? selection.id : source.activeId;
  const selected = source.documents.find(doc => doc.id === selectedId) ?? source.documents[0];
  const status = (doc: typeof selected) => doc.status === 'reading' && !running ? '读取已发起 · 结果未确认' : statuses[doc.status];
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const container = list.current;
    const button = container?.querySelector<HTMLButtonElement>('[aria-pressed="true"]');
    if (!container || !button) return;
    const outer = container.getBoundingClientRect(), inner = button.getBoundingClientRect();
    // Keep the current document visible within its own list, without scrolling the page or moving focus.
    if (inner.top < outer.top) container.scrollTop += inner.top - outer.top - 2;
    else if (inner.bottom > outer.bottom) container.scrollTop += inner.bottom - outer.bottom + 2;
  }, [selected?.id, source.readCursor]);
  if (!selected) return null;
  const reads = source.documents.reduce((count, doc) => count + doc.readCount, 0);
  const repeats = source.documents.reduce((count, doc) => count + Math.max(0, doc.readCount - 1), 0);
  return <aside className="document-evidence" aria-label="关联资料与实际引用">
    <header><div><span className="story-section-label">资料工作台</span><h3>关联资料</h3></div>
      <span>{source.documents.filter(doc => doc.read).length} / {source.documents.length} 已读取</span></header>
    <p className="document-source-note">环境资料含干扰项；Agent 自主搜索、读取并提交引用。</p>
    <p className="document-source-note" aria-label="当前过程阅读统计">成功阅读 {reads} 次 · 重复阅读 {repeats} 次。仅统计已收到正文的工具返回。</p>
    <div ref={list} className="document-list" role="group" aria-label="环境文档目录">
      {source.documents.map(doc => <button type="button" key={doc.id} aria-pressed={doc.id === selected.id}
        className={`document-card ${doc.id === selected.id ? 'selected' : ''} ${doc.status}`}
        onClick={() => setSelection({ id: doc.id, cursor: source.readCursor })}>
        <span className="document-card-title">{doc.title}</span>
        <span className="document-card-meta"><span>{status(doc)}{doc.readCount > 1 && ` · 已成功读 ${doc.readCount} 次`}</span>{doc.cited && <strong>{doc.read ? '已提交引用' : '已引用 · 未读'}</strong>}</span>
      </button>)}
    </div>
    <section className="document-preview" aria-label="资料正文预览" tabIndex={0}>
      <div className="document-preview-heading"><strong>{selected.title}</strong><span>{selected.id}</span></div>
      <p className={`document-status ${selected.status}`} aria-live="polite">{status(selected)}
        {selected.readStep !== null && ` · Step ${selected.readStep} 成功读取`}
        {selected.cited && ' · 已提交引用（是否有效以评测为准）'}</p>
      <p className="document-content">{selected.content ?? '当前记录未保存此文档正文。'}</p>
      {selected.evidenceId && <p className="document-evidence-id">证据 ID：{selected.evidenceId}</p>}
      <p className="document-source-note">{selected.read ? '已由工具返回给 Agent；页面保留原始记录。' : '仅观察者预览，尚未取得阅读证据。'}点击资料只切换预览，不调用工具或修改模型输入。</p>
    </section>
  </aside>;
}
