function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export const fieldLabels: Record<string, string> = {
  mode: '上下文策略', max_tool_rounds: '保留工具轮次', history_messages_count: '完整历史消息数',
  visible_messages_count: '模型可见消息数', dropped_messages_count: '剔除消息数', input_messages_bytes: '输入消息字节（UTF-8）',
  memory_max_bytes: '记忆字节上限', memory_entries_count: '记忆条数', memory_omitted_entries_count: '超过上限未保留条数',
  memory_bytes: '实际记忆字节（UTF-8）', memory_source_call_ids: '记忆来源调用 ID',
  error_code: '错误码', arguments_valid: '参数合法', permitted: '允许调用',
  answer: '答案', evidence: '引用证据', acquired_evidence: '已获取证据',
  records: '查询记录', documents: '文档', document: '文档内容',
  document_id: '文档 ID', order_id: '订单 ID', status: '状态',
  evidence_id: '证据 ID', target_order_id: '目标订单', task_kind: '任务类型',
  document_query: '文档检索目标', code: '错误码', message: '错误说明', retryable: '可重试',
  title: '标题', content: '内容', feedback: '反馈',
  submission: '提交内容', accepted: '已接受', proposed_call: '已提交调用',
  table: '数据表', filters: '筛选条件', query: '检索词', top_k: '返回上限',
  search_mode: '检索方式', hint: '检索建议',
  items: '计划项', plan: '计划声明', goal: '子目标', depends_on: '依赖子目标',
  planning_overlay_messages_count: '额外计划消息数',
  description: '任务说明', question: '任务问题', done: '任务结束',
  termination_reason: '终止原因', detail: '详情', success: '成功',
};

function ReadableValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="story-muted">无</span>;
  if (typeof value === 'boolean') return <span>{value ? '是' : '否'}</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="story-muted">空</span>;
    return <div className="story-value-list">{value.map((item, index) =>
      <div className="story-value-item" key={index}><ReadableValue value={item} /></div>)}</div>;
  }
  if (isRecord(value)) return Object.keys(value).length > 0
    ? <ReadableFields entries={Object.entries(value)} /> : <span className="story-muted">空</span>;
  return <span className="story-value-text">{String(value)}</span>;
}

export function ReadableFields({ entries }: { entries: [string, unknown][] }) {
  return <dl className="story-fields">{entries.map(([key, value]) =>
    <div className="story-field" key={key}>
      <dt title={key}>{fieldLabels[key] ?? key.replace(/_/g, ' ')}</dt>
      <dd><ReadableValue value={key === 'status' && typeof value === 'string'
        ? ({ pending: '声明待办', active: '声明进行中', done: '声明完成', cancelled: '声明取消' }[value] ?? value) : value} /></dd>
    </div>)}</dl>;
}
