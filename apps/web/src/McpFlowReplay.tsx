import { useEffect, useMemo, useState } from 'react';
import { Background, BaseEdge, Controls, Handle, Position, ReactFlow, getBezierPath,
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

function savedRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
}

/** Read-only visual replay; playback controls never issue API requests. */
export function McpFlowReplay({ events, environmentVersion, model, finalState, termination, detail }: {
  events: TraceStepEvent[]; environmentVersion: string; model: string;
  finalState: Record<string, unknown>; termination: string; detail: string;
}) {
  const frames = useMemo(() => flowFrames(events, environmentVersion), [events, environmentVersion]);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(1400);
  const [compact, setCompact] = useState(() => window.innerWidth < 640);
  const frame = frames[Math.min(index, Math.max(0, frames.length - 1))];
  const initialInput = savedRecord(events.find((event) => event.event_type === 'OBSERVATION_CREATED')?.payload.observation);
  const submission = savedRecord(finalState.submission);
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
    { id: 'model', position: { x: 0, y: 140 }, type: 'visual', data: { title: '模型', subtitle: model, kind: 'model', active: activeNode === 'model', failed: Boolean(frame?.failed && activeNode === 'model') } },
    { id: 'gateway', position: { x: 260, y: 140 }, type: 'visual', data: { title: '工具调度', subtitle: frame?.transport === 'mcp' ? 'MCP · HTTP' : frame?.transport === 'local' ? '本地执行' : '校验与路由', kind: 'gateway', active: activeNode === 'gateway', failed: Boolean(frame?.failed && activeNode === 'gateway') } },
    ...displayTools.map((tool, i): VisualNode => ({ id: `tool:${tool}`, position: { x: 540, y: i * 145 }, type: 'visual',
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
  if (!frame) return <p>没有可回放的工具记录。</p>;
  return <section className={`flow-replay ${compact ? 'compact' : ''}`} aria-label="工具调用动画回放">
    <div className="flow-caption"><span className="flow-replay-label">已保存轨迹 · 动画回放</span>
      <strong aria-live="polite">{phaseLabels[frame.phase]}{frame.tool ? ` · ${toolLabels[frame.tool] ?? frame.tool}` : ''}</strong>
      <span className={frame.failed ? 'flow-failure' : ''}>{frame.failed ? '失败' : frame.transport === 'mcp' ? 'MCP HTTP' : frame.transport === 'local' ? '本地' : `Step ${frame.step}`}</span></div>
    <div className={`flow-bookend input ${frame.phase === 'observe' ? 'current' : ''}`} aria-label="最初输入">
      <span className="flow-input-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M6 4h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 3V6a2 2 0 0 1 2-2Z" /><path d="M8 9h8M8 13h5" /></svg></span>
      <div><span className="flow-bookend-label">这次要做什么</span>
        <p>{typeof initialInput.description === 'string' ? initialInput.description : '此记录未保存输入描述'}</p>
        {inputContext.length > 0 && <div className="flow-input-context">{inputContext.map((item) => <span key={item.label}>{item.label}<strong>{item.value}</strong></span>)}</div>}
      </div>
    </div>
    <div className="flow-canvas">
      <ReactFlow key={compact ? 'mobile' : 'desktop'} nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
        fitView fitViewOptions={{ padding: compact ? 0.08 : 0.2 }} minZoom={0.3} maxZoom={1.4}
        nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null}
        zoomOnScroll={false} panOnScroll={false} preventScrolling={false}
        onNodeClick={(_, node) => { const next = frames.findIndex((beat) => node.id === `tool:${beat.tool}`);
          if (next >= 0) { setPlaying(false); setIndex(next); } }}>
        <Background gap={22} size={1} color="#d5d0c7" /><Controls showInteractive={false} />
      </ReactFlow>
    </div>
    <div className="flow-player">
      <button type="button" className="btn-secondary" disabled={index === 0} onClick={() => { setPlaying(false); setIndex(index - 1); }} aria-label="动画上一帧">←</button>
      <button type="button" className="btn-primary" onClick={() => { if (!playing && index === frames.length - 1) setIndex(0); setPlaying(!playing); }}>{playing ? '暂停' : index === 0 ? '播放全过程' : '播放'}</button>
      <button type="button" className="btn-secondary" disabled={index === frames.length - 1} onClick={() => { setPlaying(false); setIndex(index + 1); }} aria-label="动画下一帧">→</button>
      <label className="flow-scrubber"><span className="sr-only">动画进度</span><input type="range" min="0" max={frames.length - 1} value={index} onChange={(event) => { setPlaying(false); setIndex(Number(event.target.value)); }} /></label>
      <span className="flow-position">{index + 1}/{frames.length}</span>
      <select aria-label="动画速度" value={duration} onChange={(event) => setDuration(Number(event.target.value))}><option value={2800}>0.5×</option><option value={1400}>1×</option><option value={700}>2×</option></select>
    </div>
    <div className={`flow-bookend output ${frame.phase === 'finish' ? 'current' : ''} ${termination === 'FAILED' ? 'failed' : ''}`} aria-label="最终输出">
      <span className="flow-bookend-icon" aria-hidden="true">↗</span>
      <div><span className="flow-bookend-label">最终输出 · 已保存</span>
        <p>{answer ?? '未保存已提交的答案'}</p>
        {evidence.length > 0 && <span className="flow-bookend-meta">证据：{evidence.join(' · ')}</span>}
        {answer === null && <span className="flow-bookend-meta">{termination}{detail ? ` · ${detail}` : ''}</span>}
      </div>
    </div>
    <details className="flow-detail"><summary>查看当前记录</summary><pre>{JSON.stringify(frame.payload, null, 2)}</pre></details>
  </section>;
}
