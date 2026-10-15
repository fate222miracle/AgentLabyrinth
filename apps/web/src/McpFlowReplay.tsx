import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { Background, BaseEdge, Controls, Handle, MarkerType, Position, ReactFlow, getBezierPath, getNodesBounds, getViewportForBounds, useReactFlow,
  type Edge, type EdgeProps, type Node, type NodeProps } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { documentEvidence, flowFrames, flowPath, frameIndexAt, type FlowFrame } from './flowFrames';
import { DocumentEvidence } from './DocumentEvidence';
import type { TraceStepEvent } from './traceSteps';
import { ReadableFields } from './ReadableFields';
import { useContentMotion } from './useContentMotion';
import './flowReplay.css';

type VisualNode = Node<{ title: string; subtitle: string; kind: string; active: boolean; failed: boolean;
  step: number; status: string; complete: boolean; frameIndex: number; transport: string }, 'visual'>;
type VisualEdge = Edge<{ active: boolean; playing: boolean; duration: number; failed: boolean }, 'packet'>;
const toolLabels: Record<string, string> = { search_documents: '搜索文档', read_document: '读取文档',
  query_records: '查询记录', submit_answer: '提交答案' };
const phaseLabels: Record<FlowFrame['phase'], string> = { observe: '接收任务', request: '等待模型响应',
  respond: '模型已返回', choose: '选择工具', execute: '调用工具', return: '收到结果',
  reject: '调用被拒绝', update: '环境已更新', finish: '运行结束' };

function VisualCard({ data, sourcePosition, targetPosition }: NodeProps<VisualNode>) {
  return <div className={`flow-node ${data.active ? 'current' : ''} ${data.failed ? 'failed' : ''} ${data.complete ? 'complete' : ''}`}>
    <Handle type="target" position={targetPosition ?? Position.Left} />
    <div className="flow-node-top"><span className="flow-node-step">Step {data.step}</span><span className="flow-node-kind">{data.kind === 'model' ? '模型' : data.kind === 'task' ? '任务' : data.kind === 'finish' ? '终止' : '工具调用'}</span></div>
    <div className="flow-node-heading"><div className="flow-symbol" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.7">
      {data.kind === 'model' ? <><rect x="7" y="7" width="18" height="18" rx="5" /><path d="M12 1v6m8-6v6M12 25v6m8-6v6M1 12h6m-6 8h6m18-8h6m-6 8h6M12 16h8m-4-4v8" /></>
        : data.kind === 'finish' ? <><circle cx="16" cy="16" r="12" /><path d="m10 16 4 4 8-8" /></>
          : data.kind === 'search_documents' ? <><circle cx="13" cy="13" r="8" /><path d="m19 19 9 9" /></>
            : data.kind === 'query_records' ? <><ellipse cx="16" cy="6" rx="11" ry="4" /><path d="M5 6v19c0 5 22 5 22 0V6M5 15c0 5 22 5 22 0" /></>
            : data.kind === 'submit_answer' ? <><rect x="5" y="3" width="22" height="26" rx="4" /><path d="m10 16 4 4 8-9" /></>
              : <><path d="M3 6c5-2 9-1 13 2 4-3 8-4 13-2v21c-5-2-9-1-13 2-4-3-8-4-13-2Z M16 8v21" /></>}
    </svg></div><strong>{data.title}</strong></div>
    <span className="flow-node-subtitle" title={data.subtitle}>{data.subtitle}</span>
    <div className="flow-node-footer"><span className="flow-node-status">{data.failed ? '× ' : data.complete ? '✓ ' : '· '}{data.status}</span>{data.transport && <span>{data.transport}</span>}</div>
    <Handle type="source" position={sourcePosition ?? Position.Right} />
  </div>;
}

function PacketEdge(props: EdgeProps<VisualEdge>) {
  const [path] = getBezierPath(props);
  return <><BaseEdge path={path} markerEnd={props.markerEnd} style={{ stroke: props.data?.failed ? 'var(--fail-text)' : props.data?.active ? 'var(--brand-action)' : 'var(--border-control)',
    strokeWidth: props.data?.active ? 2 : 1.5, opacity: props.data?.active ? 1 : 0.5 }} />
    {props.data?.active && props.data.playing && <circle className="flow-packet" r="4" fill="var(--brand-action)">
      <animateMotion dur={`${Math.min(240, props.data.duration)}ms`} repeatCount="1" path={path} fill="freeze" />
    </circle>}</>;
}
const nodeTypes = { visual: VisualCard };
const edgeTypes = { packet: PacketEdge };

function FitCanvas({ canvas, columns, activeId, reducedMotion }: { canvas: RefObject<HTMLDivElement | null>;
  columns: number; activeId: string; reducedMotion: boolean }) {
  const { getNodes, setViewport, viewportInitialized } = useReactFlow();
  useEffect(() => {
    if (!viewportInitialized || !canvas.current) return;
    let pending = 0;
    const resize = () => {
      cancelAnimationFrame(pending);
      pending = requestAnimationFrame(() => {
        const target = canvas.current;
        const nodes = getNodes();
        if (!target || !nodes.length) return;
        const active = nodes.findIndex((node) => node.id === activeId);
        const row = Math.floor(Math.max(0, active) / columns);
        const visible = nodes.filter((_, i) => Math.floor(i / columns) >= Math.max(0, row - 1) && Math.floor(i / columns) <= row);
        void setViewport(getViewportForBounds(getNodesBounds(visible), target.clientWidth, target.clientHeight, 0.85, 1, 0.08),
          { duration: reducedMotion ? 0 : 180 });
      });
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas.current);
    resize();
    return () => { observer.disconnect(); cancelAnimationFrame(pending); };
  }, [canvas, viewportInitialized, getNodes, setViewport, columns, activeId, reducedMotion]);
  return null;
}

function savedRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
}

function callLabel(call: Record<string, unknown>): string {
  return `${call.name}(${Object.entries(savedRecord(call.arguments))
    .map(([name, value]) => `${name}=${JSON.stringify(value)}`).join(', ')})`;
}

/** Read-only visual replay; playback controls never issue API requests. */
export function McpFlowReplay({ events, environmentVersion, model, finalState, termination, detail, evaluation, displayMode = 'replay',
  eventIndex = 0, onSelectEvent }: {
  events: TraceStepEvent[]; environmentVersion: string; model: string;
  finalState: Record<string, unknown>; termination: string; detail: string;
  displayMode?: 'live' | 'completed' | 'replay';
  evaluation?: { success: boolean; reason: string };
  eventIndex?: number; onSelectEvent?: (index: number) => void;
}) {
  const live = displayMode === 'live';
  const following = displayMode !== 'replay';
  const frames = useMemo(() => flowFrames(events, environmentVersion), [events, environmentVersion]);
  const index = following ? frames.length - 1 : frameIndexAt(frames, eventIndex);
  const selectFrame = (next: number) => {
    if (frames[next]) onSelectEvent?.(frames[next].eventIndex);
  };
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(1400);
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  const section = useRef<HTMLElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const inspector = useRef<HTMLElement>(null);
  const focusButton = useRef<HTMLButtonElement>(null);
  const [focused, setFocused] = useState(false);
  const [focusError, setFocusError] = useState('');
  useEffect(() => {
    const update = () => {
      const active = document.fullscreenElement === section.current;
      setFocused(active);
      if (active && section.current) section.current.scrollTop = 0;
      else focusButton.current?.focus({ preventScroll: true });
    };
    document.addEventListener('fullscreenchange', update);
    return () => document.removeEventListener('fullscreenchange', update);
  }, []);
  const toggleFocus = async () => {
    setFocusError('');
    try {
      if (document.fullscreenElement === section.current) await document.exitFullscreen();
      else await section.current?.requestFullscreen();
    } catch {
      setFocusError('浏览器未允许全屏；仍可在当前区域播放。');
    }
  };
  const [compact, setCompact] = useState(() => window.innerWidth < 640);
  const candidate = frames[live ? frames.length - 1 : Math.min(index, Math.max(0, frames.length - 1))];
  const frame: FlowFrame | undefined = !following && candidate && candidate.eventIndex > eventIndex
    ? { step: events[eventIndex]?.step_index ?? 0, phase: 'observe', eventIndex, durationMs: null,
      arguments: null, feedback: [], stateChanges: [], tool: null, transport: 'unknown', failed: false,
      payload: events[eventIndex]?.payload ?? {} } : candidate;
  const isBfcl = environmentVersion.startsWith('bfcl-adapted');
  const isMcp = environmentVersion === 'tool-lab-mcp-v1';
  const isToolLab = isMcp || environmentVersion === 'tool-lab-m0-v1';
  const deliveryRequirement = isBfcl ? '提交符合题意的函数调用与参数。'
    : isToolLab ? '提交任务结论，并引用实际获取的证据。' : '以任务说明及对应评测协议为准。';
  const remoteFrame = isMcp && frame?.transport === 'mcp' && frame.tool
    && (frame.phase === 'execute' || frame.phase === 'return');
  const networkArrow = remoteFrame && frame.failed ? '×' : remoteFrame && frame.phase === 'return' ? '←' : '→';
  const initialInput = savedRecord(events.find((event) => event.event_type === 'OBSERVATION_CREATED')?.payload.observation);
  const submission = savedRecord(finalState.submission);
  const proposedCall = savedRecord(finalState.proposed_call);
  const proposedName = typeof proposedCall.name === 'string' ? proposedCall.name : null;
  const proposedArgs = Object.entries(savedRecord(proposedCall.arguments))
    .map(([name, value]) => `${name}=${JSON.stringify(value)}`).join(' · ');
  const answer = typeof submission.answer === 'string' ? submission.answer : null;
  const evidence = Array.isArray(submission.evidence) ? submission.evidence.filter((value): value is string => typeof value === 'string') : [];
  const inputContext = [
    { label: '搜索关键词', value: initialInput.document_query },
    { label: '目标订单', value: initialInput.target_order_id },
  ].filter((item): item is { label: string; value: string } => typeof item.value === 'string' && item.value.length > 0);
  const cutoff = following ? frame?.eventIndex ?? -1 : eventIndex;
  const documents = useMemo(() => documentEvidence(isToolLab ? events : [], cutoff), [events, cutoff, isToolLab]);
  const hasDocuments = documents.documents.length > 0;
  const path = useMemo(() => flowPath(frames, cutoff), [frames, cutoff]);
  const recordedState = savedRecord(frames.filter((beat) => beat.eventIndex <= cutoff
    && beat.phase === 'update').at(-1)?.payload.state);
  const recordedCall = savedRecord(recordedState.proposed_call);
  const recordedSubmission = savedRecord(recordedState.submission);
  const hasRecordedCall = typeof recordedCall.name === 'string';
  const recordedAnswer = typeof recordedSubmission.answer === 'string' ? recordedSubmission.answer : null;
  const [columns, setColumns] = useState(2);
  useEffect(() => {
    const target = canvas.current;
    if (!target) return;
    const update = () => setColumns(Math.max(1, Math.min(3, Math.floor((target.clientWidth - 24) / 248))));
    const observer = new ResizeObserver(update);
    observer.observe(target); update();
    return () => observer.disconnect();
  }, [Boolean(frame), focused]);
  useContentMotion(inspector, `${frame?.eventIndex ?? -1}`, index);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 639px)');
    const update = () => setCompact(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => {
      if (index >= frames.length - 1) setPlaying(false);
      else selectFrame(index + 1);
    }, duration);
    return () => window.clearTimeout(timer);
  }, [playing, index, duration, frames, onSelectEvent]);
  const activeNode = path.find((node) => node.frameIndex === index)?.id ?? path.at(-1)?.id ?? '';
  const nodes: VisualNode[] = path.map((node, i) => {
    const beat = node.frame;
    const row = Math.floor(i / columns), column = i % columns;
    const status = beat.failed ? beat.phase === 'reject' ? '校验拒绝' : '已记录失败'
      : node.kind === 'model' ? beat.phase === 'request' ? '请求已发出' : '响应已记录'
        : node.kind === 'tool' ? beat.phase === 'choose' ? '已提议' : beat.phase === 'execute' ? isBfcl ? '记录提议' : '调用已开始' : isBfcl ? '提议已接收' : '结果已返回'
          : node.kind === 'finish' ? '已结束' : '输入已记录';
    return { id: node.id, position: { x: (row % 2 ? columns - 1 - column : column) * 248, y: row * 190 },
      sourcePosition: columns === 1 ? Position.Bottom : row % 2 ? Position.Left : Position.Right,
      targetPosition: columns === 1 ? Position.Top : row % 2 ? Position.Right : Position.Left,
      width: 224, height: 152, type: 'visual', ariaLabel: `Step ${beat.step} · ${node.kind === 'tool' ? beat.tool ?? '调用校验' : node.kind === 'model' ? '模型请求' : node.kind === 'task' ? '接收任务' : '运行结束'} · ${status}`,
      data: { title: node.kind === 'model' ? '模型请求' : node.kind === 'task' ? '接收任务' : node.kind === 'finish' ? isBfcl && hasRecordedCall ? '函数调用输出' : recordedAnswer !== null ? '任务答案' : '运行结束' : toolLabels[beat.tool ?? ''] ?? beat.tool ?? '调用校验',
        subtitle: node.kind === 'model' ? model : node.kind === 'task' ? '任务输入与初始观察' : node.kind === 'finish' ? isBfcl && hasRecordedCall ? callLabel(recordedCall) : recordedAnswer ?? String(beat.payload.termination_reason ?? '终止原因未记录') : beat.tool === 'read_document' && typeof beat.arguments?.document_id === 'string' ? beat.arguments.document_id : beat.tool ?? '工具名未记录',
        kind: node.kind === 'tool' ? beat.tool ?? 'gateway' : node.kind, step: beat.step, status, active: activeNode === node.id,
        complete: !beat.failed && ['respond', 'return', 'observe'].includes(beat.phase), failed: beat.failed, frameIndex: node.frameIndex,
        transport: node.kind !== 'tool' || isBfcl ? '' : beat.phase === 'reject' ? '未执行' : beat.phase === 'choose' ? '待校验'
          : beat.transport === 'mcp' ? 'MCP HTTP' : beat.transport === 'local' ? '本地' : '传输未记录' } };
  });
  const edges: VisualEdge[] = path.slice(1).map((node, i) => ({ id: `path:${node.id}`, source: path[i].id,
    target: node.id, type: 'packet', markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--border-control)', width: 16, height: 16 },
    data: { active: activeNode === node.id, playing: (live && termination !== '连接中断' || playing) && !reducedMotion, duration, failed: node.frame.failed } }));
  if (!frame) return <p>{live ? '正在等待第一条可视化事件…' : '没有可回放的工具记录。'}</p>;
  return <section ref={section} className={`flow-replay ${compact ? 'compact' : ''}`} aria-label={live ? '实时工具调用流程' : displayMode === 'completed' ? '本次工具执行过程' : '工具调用动画回放'}
    onKeyDown={(event) => { if (event.key === 'Escape' && document.fullscreenElement === section.current) { event.preventDefault(); void toggleFocus(); } }}>
    <div className="flow-caption"><span className="flow-replay-label">{live ? termination === '连接中断' ? '连接中断 · 已收到的轨迹' : '实时轨迹 · 记录中' : displayMode === 'completed' ? '本次执行已完成 · 已保存' : '已保存轨迹 · 动画回放'}</span>
      <strong aria-live="polite">{isBfcl && frame.phase === 'execute' ? '记录函数调用' : isBfcl && frame.phase === 'return' ? '调用已接收' : phaseLabels[frame.phase]}{frame.tool ? ` · ${toolLabels[frame.tool] ?? frame.tool}` : ''}</strong>
      <span className={frame.failed ? 'flow-failure' : ''}>{frame.failed ? '失败' : frame.transport === 'mcp' ? 'MCP HTTP' : frame.transport === 'local' ? '本地' : `Step ${frame.step}`}</span>
      {document.fullscreenEnabled && <button ref={focusButton} type="button" className="btn-secondary" aria-pressed={focused}
        onClick={toggleFocus}>{focused ? '退出专注查看' : '专注查看'}</button>}
      {focused && <span>Esc 返回</span>}
      {focusError && <span role="status">{focusError}</span>}
    </div>
    {isMcp && <div className="mcp-network" aria-label="MCP 网络链路">
      <div className="mcp-network-heading"><strong>MCP 网络链路</strong><span aria-live="polite">{remoteFrame
        ? `${frame.tool} · ${frame.phase === 'execute' ? '远程调用开始' : frame.failed ? '远程调用失败' : '远程结果已返回'}`
        : frame.transport === 'local' ? '当前工具在平台本地执行' : '回放到远程工具步骤时显示调用状态'}</span></div>
      <div className={`mcp-network-path ${remoteFrame ? frame.failed ? 'failed' : 'active' : ''}`}>
        <div><small>平台进程</small><strong>MCP Client</strong></div><span aria-hidden="true">{networkArrow}</span>
        <div><small>Streamable HTTP</small><strong>127.0.0.1:8765/mcp</strong></div><span aria-hidden="true">{networkArrow}</span>
        <div><small>独立进程</small><strong>MCP Server</strong></div>
      </div>
      <p>按已保存的工具调用与结果展示；Trace 未记录协议握手或 tools/list 报文。</p>
    </div>}
    <div className={`flow-bookend input ${frame.phase === 'observe' ? 'current' : ''}`} aria-label="最初输入">
      <span className="flow-input-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M6 4h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 3V6a2 2 0 0 1 2-2Z" /><path d="M8 9h8M8 13h5" /></svg></span>
      <div><span className="flow-bookend-label">{isBfcl ? 'BFCL 原题' : '这次要做什么'}</span>
        <p>{typeof initialInput.description === 'string' ? initialInput.description : typeof initialInput.question === 'string' ? initialInput.question : '此记录未保存输入描述'}</p>
        <span className="flow-bookend-meta">交付要求：{deliveryRequirement}</span>
        {inputContext.length > 0 && <div className="flow-input-context">{inputContext.map((item) => <span key={item.label}>{item.label}<strong>{item.value}</strong></span>)}</div>}
      </div>
    </div>
    <div className="flow-path-nav"><div className="flow-path-heading"><div><span className="story-section-label">执行路径</span><p>每次调用独立呈现，沿记录顺序展开。</p></div>
      <span>{path.filter((node) => node.kind === 'model').length} 个模型节点 · {path.filter((node) => node.kind === 'tool').length} 次调用</span></div>
    <div className="flow-call-trail" aria-label="已记录执行节点">{path.map((node) => <button key={node.id} type="button" disabled={following}
      className={`${node.id === activeNode ? 'active' : ''} ${node.frame.failed ? 'failed' : ''}`} aria-current={node.id === activeNode ? 'step' : undefined}
      onClick={() => { setPlaying(false); selectFrame(node.frameIndex); }}>{node.kind === 'tool' ? toolLabels[node.frame.tool ?? ''] ?? node.frame.tool ?? '调用校验' : node.kind === 'model' ? `模型 ${node.frame.step}` : node.kind === 'task' ? '任务' : '结束'}{node.frame.failed ? ' · 失败' : ''}</button>)}</div></div>
    <div className={`flow-workspace ${hasDocuments ? 'with-documents' : ''}`}>
    <div className="flow-canvas" ref={canvas}>
      {path.length === 0 && <p className="flow-empty-path">当前记录尚未出现模型请求或工具调用。</p>}
      <ReactFlow key={`${compact ? 'mobile' : 'desktop'}-${focused}`} nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        minZoom={0.3} maxZoom={1.4}
        nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null} panOnDrag={false}
        zoomOnScroll={false} panOnScroll={false} preventScrolling={false}
        onNodeClick={(_, node) => { if (!following) { setPlaying(false); selectFrame(node.data.frameIndex); } }}>
        <FitCanvas canvas={canvas} columns={columns} activeId={activeNode} reducedMotion={reducedMotion} />
        <Background gap={24} size={1} color="var(--border-highlight)" /><Controls showInteractive={false} />
      </ReactFlow>
    </div>
    <div className="flow-sidebar">
    {hasDocuments && <DocumentEvidence source={documents} running={live && termination !== '连接中断'} />}
    <aside ref={inspector} className={`flow-inspector ${frame.failed ? 'failed' : ''}`} aria-label="当前阶段摘要" tabIndex={0}>
      <span className="story-section-label">Step {frame.step} · 当前阶段</span>
      <h3>{phaseLabels[frame.phase]}</h3>
      <span className={`flow-inspector-status ${frame.failed ? 'failed' : ''}`}>{frame.failed ? '此阶段已记录异常' : live ? '已收到的实时事件' : '已保存事件 · 只读'}</span>
      {frame.tool && <p className="story-tool-name">{frame.tool}</p>}
      {frame.phase === 'request' && <p>已记录模型请求，等待响应；不显示模型内部思考或推测进度。</p>}
      {frame.phase === 'request' && Object.keys(savedRecord(frame.payload.context)).length > 0 && <section aria-label="已保存模型输入诊断">
        <h4>模型可见上下文</h4>
        <ReadableFields entries={Object.entries(savedRecord(frame.payload.context)).filter(([key]) =>
          ['mode', 'max_tool_rounds', 'history_messages_count', 'visible_messages_count', 'dropped_messages_count', 'input_messages_bytes',
            'memory_max_bytes', 'memory_entries_count', 'memory_omitted_entries_count', 'memory_bytes', 'memory_source_call_ids'].includes(key))} />
        <p>字节仅为序列化消息 UTF-8 大小，不是 Token 或 HTTP 包大小；完整历史仍保留。</p>
      </section>}
      {frame.phase === 'respond' && <p>已收到模型响应，后续调用以记录的校验与执行事件为准。</p>}
      {frame.phase === 'reject' && <section><h4>校验未通过 · 工具未执行</h4>
        <ReadableFields entries={['error_code', 'message', 'arguments_valid', 'permitted']
          .filter((key) => key in frame.payload).map((key) => [key, frame.payload[key]])} /></section>}
      {frame.feedback.length > 0 && <section><h4>{frame.failed ? '失败反馈' : isBfcl ? '调用记录反馈' : '工具返回'}</h4>
        <ReadableFields entries={frame.feedback} /></section>}
      {frame.arguments && <section><h4>调用参数</h4>{Object.keys(frame.arguments).length
        ? <ReadableFields entries={Object.entries(frame.arguments)} /> : <p>无参数。</p>}</section>}
      {frame.phase === 'execute' && <p>{isBfcl ? '记录函数调用提议，不执行上游函数。' : '已记录调用开始，尚未收到本次工具返回。'}</p>}
      {frame.phase === 'update' && <section><h4>已保存的状态变化</h4>{frame.stateChanges.length > 0
        ? <ReadableFields entries={frame.stateChanges} /> : <p>未记录关键字段变化。</p>}</section>}
      {isBfcl && frame.phase === 'finish' && <section><h4>模型的函数调用输出</h4>
        <p>{hasRecordedCall ? callLabel(recordedCall) : '当前轨迹未保存已接收的函数调用。'}</p>
        {hasRecordedCall && <ReadableFields entries={Object.entries(savedRecord(recordedCall.arguments))} />}
        <p>当前 BFCL 子集只评测函数选择与参数，不执行函数；未产生数值计算结果或其他函数执行结果。</p>
      </section>}
      {!isBfcl && frame.phase === 'finish' && <section><h4>本次提交的答案与证据</h4>
        {recordedAnswer !== null ? <ReadableFields entries={Object.entries(recordedSubmission)} />
          : <p>当前轨迹未保存已提交的答案。</p>}
      </section>}
      {frame.phase === 'finish' && <ReadableFields entries={Object.entries(frame.payload).filter(([key]) => ['termination_reason', 'detail', 'success'].includes(key))} />}
      {frame.durationMs !== null && <p className="flow-recorded-duration">本事件记录耗时 {frame.durationMs} ms</p>}
      <p className="flow-inspector-note">摘要取自当前保存事件；完整数据可在技术 Trace 中核查。</p>
    </aside>
    </div>
    </div>
    {displayMode === 'replay' && <div className="flow-player">
      <button type="button" className="btn-secondary" disabled={index === 0} onClick={() => { setPlaying(false); selectFrame(index - 1); }} aria-label="动画上一帧">←</button>
      <button type="button" className="btn-primary" onClick={() => { if (!playing && index === frames.length - 1) selectFrame(0); setPlaying(!playing); }}>{playing ? '暂停' : index === 0 ? '播放全过程' : '播放'}</button>
      <button type="button" className="btn-secondary" disabled={index === frames.length - 1} onClick={() => { setPlaying(false); selectFrame(index + 1); }} aria-label="动画下一帧">→</button>
      <label className="flow-scrubber"><span className="sr-only">动画进度</span><input type="range" min="0" max={frames.length - 1} value={index} onChange={(event) => { setPlaying(false); selectFrame(Number(event.target.value)); }} /></label>
      <span className="flow-position">{index + 1}/{frames.length}</span>
      <select aria-label="动画速度" value={duration} onChange={(event) => setDuration(Number(event.target.value))}><option value={2800}>0.5×</option><option value={1400}>1×</option><option value={700}>2×</option></select>
    </div>}
    {displayMode === 'replay' && <p className="flow-playback-note">按事件阶段播放 · 播放速度用于阅读，不代表实际执行耗时。</p>}
    <div className={`flow-bookend output ${frame.phase === 'finish' ? 'current' : ''} ${!live && (termination !== 'SUCCESS' || evaluation?.success === false) ? 'failed' : ''}`} aria-label="最终输出">
      <span className="flow-bookend-icon" aria-hidden="true">↗</span>
      <div><span className="flow-bookend-label">{live ? '等待最终产物' : isBfcl ? '函数调用提议 · 已保存' : '最终输出 · 已保存'}</span>
        <span className="flow-bookend-meta">交付要求：{deliveryRequirement}</span>
        <p>{live ? termination === '连接中断' ? '请稍后按 Episode ID 回读最终产物' : '运行完成后显示评测结果' : isBfcl ? proposedName ? callLabel(proposedCall) : '未保存函数调用提议' : answer ?? '未保存已提交的答案'}</p>
        {!live && isBfcl && proposedArgs && <span className="flow-bookend-meta">参数：{proposedArgs}</span>}
        {!live && isBfcl && <span className="flow-bookend-meta">评测函数选择与参数；未执行函数，未产生数值计算结果。</span>}
        {!live && !isBfcl && evidence.length > 0 && <span className="flow-bookend-meta">证据：{evidence.join(' · ')}</span>}
        {!live && !isBfcl && answer !== null && evidence.length === 0 && <span className="flow-bookend-meta">未保存引用证据。</span>}
        {!live && evaluation && <span className="flow-bookend-meta">评测结论：{evaluation.success ? '通过' : '未通过'} · {evaluation.reason}</span>}
        {!live && (isBfcl || answer === null) && <span className="flow-bookend-meta">{termination}{detail ? ` · ${detail}` : ''}</span>}
      </div>
    </div>
    <details className="flow-detail"><summary>查看当前记录</summary><pre>{JSON.stringify(frame.payload, null, 2)}</pre></details>
  </section>;
}
