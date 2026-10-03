import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { Background, BaseEdge, Controls, Handle, Position, ReactFlow, getBezierPath, getNodesBounds, getViewportForBounds, useReactFlow,
  type Edge, type EdgeProps, type Node, type NodeProps } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { flowFrames, type FlowFrame } from './flowFrames';
import type { TraceStepEvent } from './traceSteps';
import './flowReplay.css';

type VisualNode = Node<{ title: string; subtitle: string; kind: string; active: boolean; failed: boolean }, 'visual'>;
type VisualEdge = Edge<{ active: boolean; playing: boolean; duration: number; failed: boolean }, 'packet'>;
const toolLabels: Record<string, string> = { search_documents: '搜索文档', read_document: '读取文档',
  query_records: '查询记录', submit_answer: '提交答案' };
const phaseLabels: Record<FlowFrame['phase'], string> = { observe: '接收任务', choose: '选择工具',
  execute: '调用工具', return: '收到结果', reject: '调用被拒绝', finish: '运行结束' };

function VisualCard({ data }: NodeProps<VisualNode>) {
  return <div className={`flow-node ${data.active ? 'current' : ''} ${data.failed ? 'failed' : ''}`}>
    <Handle type="target" position={Position.Left} />
    <div className="flow-symbol" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.7">
      {data.kind === 'model' ? <><rect x="7" y="7" width="18" height="18" rx="5" /><path d="M12 1v6m8-6v6M12 25v6m8-6v6M1 12h6m-6 8h6m18-8h6m-6 8h6M12 16h8m-4-4v8" /></>
        : data.kind === 'gateway' ? <><circle cx="16" cy="16" r="12" /><path d="m10 16 4 4 8-8M16 1v3m0 24v3" /></>
          : data.kind === 'search_documents' ? <><circle cx="13" cy="13" r="8" /><path d="m19 19 9 9" /></>
            : data.kind === 'submit_answer' ? <><rect x="5" y="3" width="22" height="26" rx="4" /><path d="m10 16 4 4 8-9" /></>
              : <><path d="M3 6c5-2 9-1 13 2 4-3 8-4 13-2v21c-5-2-9-1-13 2-4-3-8-4-13-2Z M16 8v21" /></>}
    </svg></div>
    <strong>{data.title}</strong><span>{data.subtitle}</span>
    <Handle type="source" position={Position.Right} />
  </div>;
}

function PacketEdge(props: EdgeProps<VisualEdge>) {
  const [path] = getBezierPath(props);
  return <><BaseEdge path={path} style={{ stroke: props.data?.failed ? '#b6544b' : props.data?.active ? '#c96442' : '#d5d0c7',
    strokeWidth: props.data?.active ? 3 : 1.5, opacity: props.data?.active ? 1 : props.id.startsWith('return:') ? 0 : 0.6 }} />
    {props.data?.active && props.data.playing && <circle className="flow-packet" r="5" fill={props.data.failed ? '#b6544b' : '#c96442'}>
      <animateMotion dur={`${props.data.duration}ms`} repeatCount="indefinite" path={path} />
    </circle>}</>;
}
const nodeTypes = { visual: VisualCard };
const edgeTypes = { packet: PacketEdge };

function FitCanvas({ canvas, padding, nodeCount }: { canvas: RefObject<HTMLDivElement | null>; padding: number; nodeCount: number }) {
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
        void setViewport(getViewportForBounds(getNodesBounds(nodes), target.clientWidth, target.clientHeight, 0.3, 1.4, padding));
      });
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas.current);
    resize();
    return () => { observer.disconnect(); cancelAnimationFrame(pending); };
  }, [canvas, viewportInitialized, getNodes, setViewport, padding, nodeCount]);
  return null;
}

function savedRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
}

/** Read-only visual replay; playback controls never issue API requests. */
export function McpFlowReplay({ events, environmentVersion, model, finalState, termination, detail, live = false }: {
  events: TraceStepEvent[]; environmentVersion: string; model: string;
  finalState: Record<string, unknown>; termination: string; detail: string; live?: boolean;
}) {
  const frames = useMemo(() => flowFrames(events, environmentVersion), [events, environmentVersion]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(1400);
  const section = useRef<HTMLElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
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
  const frame = frames[live ? frames.length - 1 : Math.min(index, Math.max(0, frames.length - 1))];
  const isBfcl = environmentVersion.startsWith('bfcl-adapted');
  const isMcp = environmentVersion === 'tool-lab-mcp-v1';
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
  const tools = Array.from(new Set(frames.flatMap((beat) => beat.tool ? [beat.tool] : [])));
  const displayTools = compact ? (frame?.tool ? [frame.tool] : tools.slice(0, 1)) : tools;
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
      else setIndex(index + 1);
    }, duration);
    return () => window.clearTimeout(timer);
  }, [playing, index, duration, frames.length]);
  const activeNode = frame?.phase === 'observe' || frame?.phase === 'choose' || frame?.phase === 'finish'
    ? 'model' : frame?.phase === 'reject' ? 'gateway' : `tool:${frame?.tool}`;
  const nodes: VisualNode[] = [
    { id: 'model', position: { x: 0, y: 140 }, width: 180, height: 116, type: 'visual', data: { title: '模型', subtitle: model, kind: 'model', active: activeNode === 'model', failed: Boolean(frame?.failed && activeNode === 'model') } },
    { id: 'gateway', position: { x: 260, y: 140 }, width: 180, height: 116, type: 'visual', data: { title: isBfcl ? '调用校验' : '工具调度', subtitle: isBfcl ? '函数名与参数' : frame?.transport === 'mcp' ? 'MCP · HTTP' : frame?.transport === 'local' ? '本地执行' : '校验与路由', kind: 'gateway', active: activeNode === 'gateway', failed: Boolean(frame?.failed && activeNode === 'gateway') } },
    ...displayTools.map((tool, i): VisualNode => ({ id: `tool:${tool}`, position: { x: 540, y: i * 145 }, width: 180, height: 116, type: 'visual',
      data: { title: toolLabels[tool] ?? tool, subtitle: `${frames.some((beat) => beat.tool === tool && beat.transport === 'mcp') ? 'MCP · ' : ''}${tool}`, kind: tool, active: activeNode === `tool:${tool}`, failed: Boolean(frame?.failed && frame.tool === tool) } })),
  ];
  if (compact) nodes.forEach((node, i) => { node.position = { x: 0, y: i * 180 }; });
  const activeLink = frame?.phase === 'choose' ? 'choose' : frame?.phase === 'execute' ? `invoke:${frame.tool}`
    : frame?.phase === 'return' ? `return:${frame.tool}` : '';
  const edge = (id: string, source: string, target: string): VisualEdge => ({ id, source, target, type: 'packet',
    data: { active: activeLink === id, playing, duration, failed: Boolean(frame?.failed) } });
  const edges = [edge('choose', 'model', 'gateway'), ...displayTools.flatMap((tool) => [
    edge(`invoke:${tool}`, 'gateway', `tool:${tool}`), edge(`return:${tool}`, `tool:${tool}`, 'model'),
  ])];
  if (!frame) return <p>{live ? '正在等待第一条可视化事件…' : '没有可回放的工具记录。'}</p>;
  return <section ref={section} className={`flow-replay ${compact ? 'compact' : ''}`} aria-label={live ? '实时工具调用流程' : '工具调用动画回放'}
    onKeyDown={(event) => { if (event.key === 'Escape' && document.fullscreenElement === section.current) { event.preventDefault(); void toggleFocus(); } }}>
    <div className="flow-caption"><span className="flow-replay-label">{live ? termination === '连接中断' ? '连接中断 · 已收到的轨迹' : '实时轨迹 · 记录中' : '已保存轨迹 · 动画回放'}</span>
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
        {inputContext.length > 0 && <div className="flow-input-context">{inputContext.map((item) => <span key={item.label}>{item.label}<strong>{item.value}</strong></span>)}</div>}
      </div>
    </div>
    <div className="flow-canvas" ref={canvas}>
      <ReactFlow key={`${compact ? 'mobile' : 'desktop'}-${focused}`} nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        minZoom={0.3} maxZoom={1.4}
        nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null} panOnDrag={false}
        zoomOnScroll={false} panOnScroll={false} preventScrolling={false}
        onNodeClick={(_, node) => { if (live) return; const next = frames.findIndex((beat) => node.id === `tool:${beat.tool}`);
          if (next >= 0) { setPlaying(false); setIndex(next); } }}>
        <FitCanvas canvas={canvas} padding={compact || focused ? 0.08 : 0.2} nodeCount={nodes.length} />
        <Background gap={22} size={1} color="#d5d0c7" /><Controls showInteractive={false} />
      </ReactFlow>
    </div>
    {!live && <div className="flow-player">
      <button type="button" className="btn-secondary" disabled={index === 0} onClick={() => { setPlaying(false); setIndex(index - 1); }} aria-label="动画上一帧">←</button>
      <button type="button" className="btn-primary" onClick={() => { if (!playing && index === frames.length - 1) setIndex(0); setPlaying(!playing); }}>{playing ? '暂停' : index === 0 ? '播放全过程' : '播放'}</button>
      <button type="button" className="btn-secondary" disabled={index === frames.length - 1} onClick={() => { setPlaying(false); setIndex(index + 1); }} aria-label="动画下一帧">→</button>
      <label className="flow-scrubber"><span className="sr-only">动画进度</span><input type="range" min="0" max={frames.length - 1} value={index} onChange={(event) => { setPlaying(false); setIndex(Number(event.target.value)); }} /></label>
      <span className="flow-position">{index + 1}/{frames.length}</span>
      <select aria-label="动画速度" value={duration} onChange={(event) => setDuration(Number(event.target.value))}><option value={2800}>0.5×</option><option value={1400}>1×</option><option value={700}>2×</option></select>
    </div>}
    <div className={`flow-bookend output ${frame.phase === 'finish' ? 'current' : ''} ${!live && termination !== 'SUCCESS' ? 'failed' : ''}`} aria-label="最终输出">
      <span className="flow-bookend-icon" aria-hidden="true">↗</span>
      <div><span className="flow-bookend-label">{live ? '等待最终产物' : isBfcl ? '函数调用提议 · 已保存' : '最终输出 · 已保存'}</span>
        <p>{live ? termination === '连接中断' ? '请稍后按 Episode ID 回读最终产物' : '运行完成后显示评测结果' : isBfcl ? proposedName ?? '未保存函数调用提议' : answer ?? '未保存已提交的答案'}</p>
        {!live && isBfcl && proposedArgs && <span className="flow-bookend-meta">参数：{proposedArgs}</span>}
        {!live && !isBfcl && evidence.length > 0 && <span className="flow-bookend-meta">证据：{evidence.join(' · ')}</span>}
        {!live && (isBfcl || answer === null) && <span className="flow-bookend-meta">{termination}{detail ? ` · ${detail}` : ''}</span>}
      </div>
    </div>
    <details className="flow-detail"><summary>查看当前记录</summary><pre>{JSON.stringify(frame.payload, null, 2)}</pre></details>
  </section>;
}
