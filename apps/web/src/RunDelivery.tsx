import { ReadableFields } from './ReadableFields';
import { explainFailure } from './traceSteps';

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

/** Saved delivery is independent of the replay cursor; a live stream never borrows its final state. */
export function RunDelivery({ state, environmentVersion, termination, detail, evaluation, provider, live = false, replay = false,
  label = '最终输出' }: {
  state: Record<string, unknown>; environmentVersion: string; termination: string; detail: string;
  evaluation?: { success: boolean; reason: string }; provider?: string; live?: boolean; replay?: boolean; label?: string;
}) {
  const bfcl = environmentVersion.startsWith('bfcl-adapted');
  const submission = record(state.submission);
  const call = record(state.proposed_call);
  const answer = typeof submission.answer === 'string' ? submission.answer : null;
  const evidence = Array.isArray(submission.evidence) ? submission.evidence.filter((id): id is string => typeof id === 'string') : [];
  const callName = typeof call.name === 'string' ? call.name : null;
  const failed = !live && (termination !== 'SUCCESS' || evaluation?.success === false);
  const requirement = bfcl ? '提交符合题意的函数调用与参数。'
    : ['tool-lab-m0-v1', 'tool-lab-mcp-v1'].includes(environmentVersion) ? '提交任务结论，并引用实际获取的证据。' : '以任务说明及对应评测协议为准。';
  return <section className={`run-delivery flow-bookend output ${live ? 'pending' : 'saved'} ${failed ? 'failed' : ''}`} aria-label={label} tabIndex={-1}>
    <div className="delivery-heading"><h3>{live ? '等待最终产物' : bfcl ? '函数调用提议 · 已保存' : '最终输出 · 已保存'}</h3>
      {!live && evaluation && <span className={`delivery-verdict ${evaluation.success ? 'passed' : 'failed'}`}>评测结论：{evaluation.success ? '通过' : '未通过'}</span>}</div>
    <p className="delivery-boundary">{provider === 'fake' ? 'Fake 离线模拟 · 只验证机制，不代表模型能力' : provider === 'aihubmix' ? '真实模型运行 · 单次结果' : '运行来源未记录'}</p>
    {!live && replay && <p className="delivery-boundary">整次运行的最终结果；下方按选定步骤回放。</p>}
    {live ? <p className="delivery-pending">{termination === '连接中断' ? '请稍后按 Episode ID 回读最终产物' : '运行完成后显示评测结果'}</p>
      : <>
        <div className="delivery-answer">{bfcl ? callName ?? '未保存函数调用提议' : answer ?? '未保存已提交的答案'}</div>
        {bfcl && callName && <div className="delivery-call-arguments"><h4>提交参数</h4><ReadableFields entries={Object.entries(record(call.arguments))} /></div>}
        {bfcl && <p className="delivery-boundary">评测函数选择与参数；未执行函数，未产生数值计算结果。</p>}
        {!bfcl && evidence.length > 0 && <div className="delivery-evidence"><h4>提交引用的证据</h4><ul>{evidence.map((id, index) => <li key={`${index}-${id}`}><code>{id}</code></li>)}</ul>
          <p>引用是否有效以本次评测为准；右侧资料仅按实际读取记录展示。</p></div>}
        {!bfcl && answer !== null && evidence.length === 0 && <p className="delivery-boundary">未保存引用证据。</p>}
        {failed && <p className="delivery-failure">{termination === 'SUCCESS'
          ? '已保存提交，但未通过任务规则检查；具体原因见结果来源。'
          : explainFailure(detail || evaluation?.reason || termination)}</p>}
      </>}
    <details className="delivery-details"><summary>交付要求与结果来源</summary>
      <p>交付要求：{requirement}</p>
      <p>{live ? '当前未取得最终产物；不预测答案或评测结论。' : replay ? '这是整次运行的已保存最终交付，独立于下方回放游标；当前步骤以画布与侧栏为准。' : '答案、引用与规则结论来自本次已保存产物。'}</p>
      {!live && evaluation && <p>规则依据：{evaluation.reason}</p>}
      {!live && <p>{termination}{detail ? ` · ${detail}` : ''}</p>}
    </details>
  </section>;
}
