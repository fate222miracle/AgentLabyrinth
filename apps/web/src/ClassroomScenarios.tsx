import type { TaskOption } from './apiContracts';

const scenarios = [
  { name: 'return-evidence-chain-001', title: '退货审核', count: 3, summary: '从登记、政策到审批，找齐退货结论的依据。' },
  { name: 'delivery-evidence-chain-002', title: '配送争议', count: 4, summary: '沿投诉、配送与签收记录，核查最终处理结论。' },
  { name: 'refund-evidence-chain-003', title: '退款审批', count: 5, summary: '跨支付、验收与风控记录，形成完整退款证据链。' },
];

/** Configure existing public scenarios without starting inference or editing history. */
export function ClassroomScenarios({ tasks, disabled, hasSavedResult, selectedTaskNames, onConfigure }: {
  tasks: TaskOption[];
  disabled: boolean;
  hasSavedResult: boolean;
  selectedTaskNames: string[];
  onConfigure: (task: TaskOption, target: 'single' | 'experiment') => void;
}) {
  return <details className="classroom-scenarios card" open={!hasSavedResult}>
    <summary><strong>课堂演示 · 快速配置</strong><span>选择场景后，在下方确认并运行</span></summary>
    <div className="classroom-grid">
      {scenarios.map((scenario) => {
        const task = tasks.find((item) => item.name === scenario.name && item.suite === 'tool_lab_core' && item.category === 'evidence_chain');
        return <article className={`classroom-scenario ${selectedTaskNames.includes(scenario.name) ? 'selected' : ''}`} key={scenario.name}>
          <div className="classroom-scenario-copy">
          <div className="classroom-scenario-heading"><h2>{scenario.title}</h2><span>{scenario.count} 份关联依据</span></div>
          <p>{scenario.summary}</p>
          <small>{task ? `最多 ${task.max_steps} 步 · 单次 Token 预算 ${task.token_budget}` : '当前任务目录未提供此场景'}</small>
          </div>
          <div className="classroom-actions">
            <button type="button" className="btn-secondary classroom-configure" disabled={disabled || !task}
              aria-label={`配置${scenario.title}实时演示`} onClick={() => task && onConfigure(task, 'single')}>实时演示</button>
            <button type="button" className="btn-text" disabled={disabled || !task}
              aria-label={`配置${scenario.title}上下文对照`} onClick={() => task && onConfigure(task, 'experiment')}>上下文对照</button>
          </div>
        </article>;
      })}
    </div>
    <details className="classroom-help"><summary>场景与对照说明</summary><p className="classroom-footnote">自建仿真 · 沿用当前模型，仅填写下次运行配置。上下文对照为同任务、Seed 1、各运行一次，共 2 个 Episode；结果可能成功或失败。</p></details>
  </details>;
}
