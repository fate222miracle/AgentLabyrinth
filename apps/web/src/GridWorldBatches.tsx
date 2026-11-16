import { useEffect, useRef, useState } from 'react';
import { readApi } from './apiClient';
import { gridWorldBatchListSchema, gridWorldBatchSchema, type GridWorldBatch, type ModelOption } from './apiContracts';
import { explainFailure } from './traceSteps';

const endpoint = '/api/v1/gridworld-batches';
const labels = {
  queued: '排队中', running: '运行中', completed: '通关', failed: '未通关',
  unavailable: '模型不可用', error: '运行或保存异常', interrupted: '运行中断', not_started: '未开始',
};

export function GridWorldBatches({ models, selected, onSelect }: {
  models: ModelOption[];
  selected: GridWorldBatch | null;
  onSelect: (batch: GridWorldBatch | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [batches, setBatches] = useState<GridWorldBatch[]>([]);
  const [viewId, setViewId] = useState('');
  const [error, setError] = useState('');
  const [readFailed, setReadFailed] = useState(false);
  const [skipped, setSkipped] = useState(0);
  const [revision, setRevision] = useState(0);
  const [posting, setPosting] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const postingRef = useRef(false);
  const active = batches.some(batch => batch.running);
  const view = batches.find(batch => batch.batch_id === viewId) ?? batches[0];

  useEffect(() => {
    if (!open || posting) return;
    const controller = new AbortController();
    let timer: number | undefined;
    async function refresh() {
      try {
        const response = await fetch(endpoint, { signal: controller.signal });
        const data = await readApi(response, gridWorldBatchListSchema);
        if (controller.signal.aborted) return;
        setBatches(data.items);
        setSkipped(data.skipped_count);
        setLoaded(true);
        setReadFailed(false);
        if (data.items.some(batch => batch.running)) timer = window.setTimeout(() => void refresh(), 2500);
      } catch {
        if (!controller.signal.aborted) {
          setReadFailed(true);
          setLoaded(true);
        }
      }
    }
    void refresh();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [open, posting, revision]);

  const selectedId = selected?.batch_id;
  useEffect(() => {
    const current = batches.find(batch => batch.batch_id === selectedId);
    if (current) onSelect(current);
  }, [batches, onSelect, selectedId]);

  const real = models.some(model => model.provider === 'aihubmix');
  async function start() {
    if (!loaded || active || !real || postingRef.current) return;
    postingRef.current = true;
    setPosting(true);
    setError('');
    try {
      const response = await fetch(endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schema_version: '1.0' }),
      });
      const batch = await readApi(response, gridWorldBatchSchema);
      setBatches(current => [batch, ...current.filter(item => item.batch_id !== batch.batch_id)]);
      setViewId(batch.batch_id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '批次启动未确认，请查看历史。');
    } finally {
      postingRef.current = false;
      setPosting(false);
    }
  }

  return <details className="comparison-panel batch-panel" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>同配置四模型批次</summary>
    <div className="batch-body">
      <div className="comparison-toolbar">
        <div>
          <h2>回廊档案室</h2>
          <p>MiniMax M2.7、MiniMax M3、GLM 5.3、GLM 5.3 Flash 按顺序各运行一局。</p>
          <p className="metric-sub">Seed 1 · 最近 2 轮 · 每局最多 24 步 / 330 秒 · 输入阈值 160,000 Token · 单次最多输出 2,048 Token</p>
        </div>
        <button type="button" className="btn-primary" disabled={!real || !loaded || readFailed || posting || active} onClick={() => void start()}>
          {posting ? '正在创建…' : active ? '已有批次在运行' : '启动四模型实测'}
        </button>
      </div>
      {!real && <p className="metric-sub">真实模型目录当前没有可选候选。</p>}
      {error && <p role="alert">{error}</p>}
      {readFailed && <p role="alert">读取批次失败。 <button className="btn-secondary" type="button"
        onClick={() => setRevision(value => value + 1)}>重新读取</button></p>}
      {skipped > 0 && <p role="status">{skipped} 条批次清单无法读取。</p>}
      {view && <>
        <label className="comparison-group">批次记录
          <select className="form-select" value={view.batch_id} onChange={event => setViewId(event.target.value)}>
            {batches.map(batch => <option key={batch.batch_id} value={batch.batch_id}>
              {new Date(batch.created_at).toLocaleString('zh-CN')} · {batch.running ? '进行中' : '已结束'}
            </option>)}
          </select>
        </label>
        <ul className="batch-runs">
          {view.runs.map(run => <li key={run.episode_id}>
            <strong>{run.model}</strong>
            <span>{run.status === 'failed' && run.row ? explainFailure(run.row.detail) || run.row.termination : labels[run.status]}</span>
          </li>)}
        </ul>
        <div>
          {selected?.batch_id !== view.batch_id && <button className="btn-secondary" type="button" onClick={() => onSelect(view)}
                disabled={view.runs.filter(run => run.row).length < 2}>在下方对比本批结果</button>}
        </div>
      </>}
    </div>
  </details>;
}
