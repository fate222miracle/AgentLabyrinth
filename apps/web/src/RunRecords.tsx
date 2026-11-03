import { useState } from 'react';
import type { EpisodeHistorySummary } from './historySummary';
import { HistoryReader } from './HistoryReader';

export function RunRecords({ ids, summaries, value, busy, onChange, onRead }: {
  ids: string[];
  summaries: Record<string, EpisodeHistorySummary>;
  value: string;
  busy: boolean;
  onChange: (value: string) => void;
  onRead: (id: string) => Promise<void>;
}) {
  const [query, setQuery] = useState('');
  const filtered = ids.filter(id => `${id} ${summaries[id]?.taskName ?? ''} ${summaries[id]?.modelId ?? ''}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <section className="run-records" aria-label="本机最近访问记录">
    <div className="records-toolbar"><label>筛选最近访问<input className="form-input" type="search" value={query}
      placeholder="任务、模型或运行 ID" onChange={event => setQuery(event.target.value)} /></label>
      <HistoryReader kind="episode" value={value} busy={busy} onChange={onChange} onRead={onRead} /></div>
    <p className="records-scope">仅显示此浏览器最近访问的 {ids.length} 条运行，最多 5 条。可用完整 ID 读取其他保存记录；这里还不是数据库全部历史。</p>
    <div className="record-list">{filtered.map(id => {
      const item = summaries[id];
      const ready = item?.status === 'ready';
      const status = ready ? item.success === undefined ? '结果未记录' : item.success ? '评测通过' : '评测未通过'
        : item?.status === 'error' ? '摘要暂不可用' : '读取摘要中';
      const parsed = item?.timestamp ? new Date(item.timestamp) : null;
      const time = parsed && !Number.isNaN(parsed.getTime()) ? parsed.toLocaleString() : '时间未记录';
      return <button className="record-row" key={id} disabled={busy} onClick={() => onRead(id)}>
        <span><strong>{item?.taskName ?? '读取历史运行'}</strong><span>{item?.modelId ?? '模型未记录'}</span></span>
        <span className="record-identity"><span>{time}</span><code>{id}</code></span>
        <span className={ready && item.success !== undefined ? item.success ? 'record-success' : 'record-failed' : ''}>{status} →</span>
      </button>;
    })}</div>
    {filtered.length === 0 && <p className="empty-state" role="status">{ids.length ? '没有匹配的最近访问记录。' : '尚未访问运行记录。完成一次任务，或在上方输入已保存的 ID。'}</p>}
  </section>;
}
