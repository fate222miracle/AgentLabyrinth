import { useEffect, useRef, useState } from 'react';
import type { TaskOption } from './apiContracts';
import { taskCategoryLabels, taskDescription, taskTitle } from './taskPresentation';

export function TaskLibrary({ tasks, loading, unavailable, disabled, onSelect }: {
  tasks: TaskOption[];
  loading: boolean;
  unavailable: boolean;
  disabled: boolean;
  onSelect: (task: TaskOption) => void;
}) {
  const [query, setQuery] = useState('');
  const [suite, setSuite] = useState('all');
  const [selected, setSelected] = useState<string | null>(null);
  const previewHeading = useRef<HTMLHeadingElement>(null);
  const previewTrigger = useRef<HTMLButtonElement | null>(null);
  const filtered = tasks.filter(task => (suite === 'all' || task.suite === suite)
    && `${taskTitle(task)} ${task.name} ${taskDescription(task)} ${taskCategoryLabels[task.category] ?? task.category}`
      .toLowerCase().includes(query.trim().toLowerCase()));
  const preview = tasks.find(task => task.id === selected);
  useEffect(() => {
    if (selected) previewHeading.current?.focus();
  }, [selected]);
  const closePreview = () => {
    setSelected(null);
    requestAnimationFrame(() => { if (previewTrigger.current?.isConnected) previewTrigger.current.focus(); });
  };
  return <section className="task-library" aria-label="任务库">
    <div className="library-toolbar">
      <label>查找任务<input type="search" className="form-input" placeholder="按目标、名称或能力搜索"
        value={query} onChange={event => { setQuery(event.target.value); setSelected(null); }} /></label>
      <label>任务来源<select className="form-input" value={suite} onChange={event => { setSuite(event.target.value); setSelected(null); }}>
        <option value="all">全部来源</option><option value="tool_lab_core">ToolLab 原生仿真</option>
        <option value="bfcl_adapted">BFCL Python 改编</option><option value="bfcl_java_adapted">BFCL Java 改编</option>
      </select></label><span role="status">{loading ? '正在读取任务…' : unavailable ? '目录未载入' : `${filtered.length} 个任务`}</span>
    </div>
    <div className={`library-browser ${preview ? 'has-preview' : ''}`}>
    {preview && <aside className="task-preview" aria-label="任务详情">
      <div className="task-preview-heading"><span className="task-library-category">{taskCategoryLabels[preview.category] ?? preview.category}</span>
        <button className="btn-text" onClick={closePreview}>关闭详情</button></div>
      <h2 ref={previewHeading} tabIndex={-1}>{taskTitle(preview)}</h2>
      <span className="task-code">{preview.name}</span>
      <div className="task-preview-goal"><h3>任务目标与交付要求</h3><p>{taskDescription(preview)}</p></div>
      <dl className="task-preview-facts">
        <div><dt>任务来源</dt><dd>{preview.suite === 'tool_lab_core' ? 'ToolLab 自建仿真' : preview.suite === 'bfcl_adapted' ? 'BFCL Python 改编' : 'BFCL Java 改编'}</dd></div>
        <div><dt>执行上限</dt><dd>{preview.max_steps} 步</dd></div>
        <div><dt>工具连接</dt><dd>{preview.supports_mcp ? '本地 / MCP HTTP' : '本地工具或函数调用'}</dd></div>
      </dl>
      <button className="btn-primary" disabled={disabled} onClick={() => onSelect(preview)}>配置此任务</button>
      <p className="metric-sub">只填写运行草稿，下一步确认模型后再启动。</p>
    </aside>}
    <div>
    {loading && tasks.length === 0 && <div className="library-loading" aria-hidden="true">{[0, 1, 2, 3].map(index => <div key={index}><span /><span /><span /></div>)}</div>}
    {unavailable && <p className="library-empty" role="status">任务目录未载入，请使用上方的重新读取按钮重试。</p>}
    {!loading && !unavailable && filtered.length === 0 && <div className="library-empty" role="status"><h2>没有找到匹配任务</h2><p>试试更短的关键词，或切换任务来源。</p>
      <button className="btn-secondary" onClick={() => { setQuery(''); setSuite('all'); }}>清除筛选</button></div>}
    <div className="library-grid">{filtered.map(task => <article key={task.id} className="library-task">
      <div><span className="task-library-category">{taskCategoryLabels[task.category] ?? task.category}</span>
        <h2>{taskTitle(task)}</h2><span className="task-code">{task.name}</span></div>
      <p>{taskDescription(task)}</p>
      <div className="library-task-actions"><span>{task.max_steps} 步上限 · {task.supports_mcp ? '支持 MCP' : '本地执行'}</span>
        <button className="btn-text" aria-expanded={selected === task.id} onClick={event => { previewTrigger.current = event.currentTarget; setSelected(task.id);
          if (selected === task.id) previewHeading.current?.focus(); }}>查看任务</button>
        <button className="btn-text" disabled={disabled} onClick={() => onSelect(task)}>配置运行 →</button></div>
    </article>)}</div>
    </div></div>
  </section>;
}
