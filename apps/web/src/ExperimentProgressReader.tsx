import { useEffect, useState } from 'react';
import { experimentProgressSchema, requireIdentity, type ExperimentProgress } from './apiContracts';
import { readApi } from './apiClient';
import { explainFailure } from './traceSteps';

const labels = { completed: '已保存结束记录', checkpoint: '仅保存安全点',
  no_saved_record: '尚无保存记录', invalid: '保存记录不可用' };

/** A user-selected snapshot, never a resume operation or a fabricated Experiment. */
export function ExperimentProgressReader({ id, onClose }: { id: string; onClose: () => void }) {
  const [data, setData] = useState<ExperimentProgress | null>(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError('');
    (async () => {
      try {
        const result = await readApi(await fetch(`/api/v1/experiments/${encodeURIComponent(id)}/progress`,
          { signal: controller.signal }), experimentProgressSchema);
        requireIdentity(result.experiment_id, id);
        if (!controller.signal.aborted) setData(result);
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : '保存进度读取失败。');
      }
    })();
    return () => controller.abort();
  }, [id, revision]);
  return <section className="resumable-panel" aria-label="实验保存进度">
    <h3>已保存到哪一步？</h3>
    <p className="memory-review-id">Experiment：{id}</p>
    <p className="chart-note">只读保存快照，不继续执行。没有保存记录可能表示尚未开始或尚未落盘，不能计作失败或零用量；这里不计算完整实验成绩。</p>
    <div className="memory-review-actions">
      <button type="button" className="btn-secondary" onClick={() => setRevision(n => n + 1)}>重新读取进度</button>
      <button type="button" className="btn-secondary" onClick={onClose}>关闭进度</button>
    </div>
    {error ? <p role="alert">{error} 已保存文件不会因此被修改。</p>
      : !data ? <p role="status">正在读取保存进度…</p>
        : <div className="memory-review-arms">{data.arms.map(arm => <section className="memory-review-arm" key={arm.episode_id}>
          <h4>{arm.arm === 'baseline' ? '左侧' : '右侧'} · {arm.task_name}</h4>
          <p>Seed {arm.seed} · 第 {arm.repeat_index} 次 · {labels[arm.state]}</p>
          {arm.state === 'completed' && <p>{arm.success ? '评测通过' : '评测未通过'} · {arm.termination_reason}</p>}
          {arm.detail && <p className="chart-note">{explainFailure(arm.detail)}</p>}
          {arm.state === 'completed' && <a className="btn-secondary" href={`/?episode_id=${encodeURIComponent(arm.episode_id)}`}>查看保存的运行</a>}
        </section>)}</div>}
  </section>;
}
