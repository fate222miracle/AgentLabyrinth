import type { TaskOption } from './apiContracts';

export const bfclDescriptions: Record<string, string> = {
  'bfcl-simple_python_0': '求底边长为 10、高为 5 的三角形面积。',
  'bfcl-simple_python_1': '使用数学函数计算 5 的阶乘。',
  'bfcl-simple_python_2': '已知直角三角形的两条直角边分别为 4 和 5，求斜边长度。',
  'bfcl-simple_python_3': '求二次方程的根，系数为 a=1、b=-3、c=2。',
  'bfcl-simple_python_4': '求解系数为 a=2、b=6、c=5 的二次方程。',
  'bfcl-simple_python_5': '求二次方程的所有根，系数为 a=3、b=-11、c=-4。',
  'bfcl-simple_python_6': '求系数为 a=2、b=5、c=3 的二次方程的根。',
  'bfcl-simple_python_7': '求半径为 4 英寸的圆的周长。',
  'bfcl-simple_java_6': '刷新数据库表格视图的元数据、追加已有数据，并保留当前状态。',
  'bfcl-simple_java_18': '查询系统角色数量的第 3 页，每页 20 条。',
  'bfcl-simple_java_53': '构造谓词：判断 Join 是否为完整主节点，且状态早于本地接受的任期 42、版本 7。',
  'bfcl-simple_java_74': '在 XML 序列化中处理高代理值 55357、低代理值 56832；内容不在 CDATA 内。',
  'bfcl-simple_java_76': '以宽 800、高 600 的尺寸更新开场动画画面。',
};

export const taskCategoryLabels: Record<string, string> = {
  tool_selection: '工具选择',
  parameter_generation: '参数生成',
  multi_step_planning: '多步规划',
  evidence_chain: '跨文档证据链 · 自建仿真',
  error_recovery: '错误恢复',
  reflection_challenge: '停滞反思',
  bfcl_single_call: '单次函数调用',
};

export function taskDescription(task: TaskOption): string {
  return task.suite !== 'tool_lab_core' ? bfclDescriptions[task.id] ?? task.description : task.description;
}

export const taskTitles: Record<string, string> = {
  'return-evidence-chain-001': '退货审批 · 查齐依据',
  'delivery-evidence-chain-002': '配送争议 · 核查处理结论',
  'refund-evidence-chain-003': '退款审批 · 追踪审核链',
  'memory-fact-reuse-001': '批次资格 · 复用数量事实',
  'memory-large-return-002': '批次资格 · 大文档检索',
  'memory-policy-version-003': '批次资格 · 辨别政策版本',
  'planning-branch-001': '资格核验 · 拆分复合目标',
  'planning-route-002': '资格核验 · 选择政策分支',
  'planning-omit-003': '资格核验 · 补全适用审核',
  'reflection-stale-alias-001': '订单查询 · 修正停滞行动',
  'order-status-001': '查询订单状态',
  'order-status-002': '在干扰记录中定位订单',
  'order-status-003': '核查已取消的订单',
  'order-status-004': '在紧凑预算内完成查询',
  'order-status-005': '生成精确订单查询参数',
  'order-status-006': '使用嵌套条件查询订单',
  'order-status-007': '检索并阅读订单政策',
  'order-status-008': '定位配送政策与依据',
  'order-status-009': '检索退款帮助并提交证据',
  'order-status-010': '修正参数后查询订单',
  'order-status-011': '修正嵌套过滤条件',
  'order-status-012': '完成一次受限参数纠错',
};

export function taskTitle(task: TaskOption): string {
  return taskTitles[task.name] ?? bfclDescriptions[task.id] ?? task.name;
}

