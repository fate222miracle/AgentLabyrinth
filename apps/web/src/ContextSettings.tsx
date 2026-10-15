import type { EpisodeArtifact } from './apiContracts';

export type ContextChoice = 'full' | 'window' | 'memory';

/** Construct an explicit, versioned projection; the default keeps old requests unchanged. */
export function contextInput(choice: ContextChoice, rounds: number, bytes: number) {
  if (choice === 'full') return undefined;
  if (!Number.isInteger(rounds) || rounds < 1 || rounds > 100) throw new Error('上下文窗口须为 1–100 的整数');
  if (choice === 'memory' && (!Number.isInteger(bytes) || bytes < 256 || bytes > 32768)) {
    throw new Error('记忆大小须为 256–32768 的整数字节');
  }
  return choice === 'memory'
    ? { schema_version: '1.1', algorithm_version: 'tool-round-window-memory-v1', mode: 'recent_tool_rounds',
      max_tool_rounds: rounds, memory_max_bytes: bytes }
    : { mode: 'recent_tool_rounds', max_tool_rounds: rounds };
}

export function contextLabel(policy: EpisodeArtifact['agent']['context_policy']): string {
  if (!policy || policy.mode === 'full') return '完整历史';
  return `最近 ${policy.max_tool_rounds} 轮工具交互${policy.memory_max_bytes === undefined ? '' : ` + 工具记忆（最多 ${policy.memory_max_bytes} 字节）`}`;
}

export function ContextSettings({ prefix, choice, rounds, bytes, disabled, comparison = false, onChoice, onRounds, onBytes }: {
  prefix: string; choice: ContextChoice; rounds: number; bytes: number; disabled: boolean; comparison?: boolean;
  onChoice: (choice: ContextChoice) => void; onRounds: (rounds: number) => void; onBytes: (bytes: number) => void;
}) {
  return <div className="context-settings">
    <div className="form-group"><label htmlFor={`${prefix}-mode`} className="form-label">{comparison ? '右侧上下文策略' : '模型上下文'}</label>
      <select id={`${prefix}-mode`} className="form-select" value={choice} disabled={disabled}
        onChange={event => onChoice(event.target.value as ContextChoice)}>
        {!comparison && <option value="full">完整历史（默认）</option>}
        <option value="window">仅保留近期工具轮次</option><option value="memory">近期工具轮次 + 单任务工具记忆</option>
      </select></div>
    <div className="context-settings-values">
    {choice !== 'full' && <div className="form-group"><label htmlFor={`${prefix}-window`} className="form-label">{comparison ? '右侧保留完整工具轮次' : '保留完整工具轮次'}</label>
      <input id={`${prefix}-window`} className="form-input" type="number" min="1" max="100" step="1" value={rounds}
        disabled={disabled} onChange={event => onRounds(Number(event.target.value))} /></div>}
    {choice === 'memory' && <div className="form-group"><label htmlFor={`${prefix}-bytes`} className="form-label">单任务记忆大小上限（字节）</label>
      <input id={`${prefix}-bytes`} className="form-input" type="number" min="256" max="32768" step="1" value={bytes}
        disabled={disabled} onChange={event => onBytes(Number(event.target.value))} />
      </div>}
    </div>
    <p className="form-help">{choice === 'full' ? '保留全部工具历史，适合短任务。'
      : choice === 'memory' ? '带回早期成功工具数据；超大结果整条跳过。' : '仅保留近期交互，可能遗忘早期信息。'}</p>
    <details className="context-help"><summary>策略说明与限制</summary>
      <p>Trace 与安全点仍保存完整历史。字节上限不是 Token 预算；记忆可能增加输入量，不保证效果。</p>
      {choice === 'memory' && <p>记忆保留窗口外已成功返回的完整工具数据与来源，不做摘要或跨任务记忆。</p>}
    </details>
  </div>;
}
