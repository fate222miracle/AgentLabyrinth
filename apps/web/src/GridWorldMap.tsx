import { useMemo, useState } from 'react';
import type { TraceEvent } from './apiContracts';
import { GridWorldStage } from './GridWorldStage';
import './gridworld.css';

type KnownCell = {
  x: number;
  y: number;
  kind: 'wall' | 'floor' | 'key' | 'closed_door' | 'open_door' | 'goal';
  visible: boolean;
  observedAtAction: number;
};

export type PublicGridState = {
  size: [number, number];
  position: [number, number];
  inventory: string[];
  actionCount: number;
  illegalActionCount: number;
  knownCells: KnownCell[];
  lastAction: { action: string; accepted: boolean; feedback: string } | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isCoordinate(value: unknown, maximum: number): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= maximum;
}

function isCellKind(value: unknown): value is KnownCell['kind'] {
  return value === 'wall' || value === 'floor' || value === 'key'
    || value === 'closed_door' || value === 'open_door' || value === 'goal';
}

function parsePublicState(value: unknown): PublicGridState | null {
  if (!isRecord(value) || value.environment_version !== 'gridworld-key-door-v1') return null;
  const size: [number, number] = value.task_id === '2d70465a-2b9e-4c8f-8f2f-7f07d5ad4f9c' ? [9, 7] : [7, 5];
  const [width, height] = size;
  if (
    !Array.isArray(value.position) || value.position.length !== 2
    || !isCoordinate(value.position[0], width - 1) || !isCoordinate(value.position[1], height - 1)
    || !Array.isArray(value.inventory) || !value.inventory.every((item) => typeof item === 'string')
    || typeof value.action_count !== 'number' || !Number.isInteger(value.action_count)
    || typeof value.illegal_action_count !== 'number' || !Number.isInteger(value.illegal_action_count)
    || !Array.isArray(value.known_cells)) return null;

  const knownCells: KnownCell[] = [];
  for (const cell of value.known_cells) {
    if (!isRecord(cell) || !isCoordinate(cell.x, width - 1) || !isCoordinate(cell.y, height - 1)
      || !isCellKind(cell.kind)
      || typeof cell.visible !== 'boolean'
      || typeof cell.observed_at_action !== 'number' || !Number.isInteger(cell.observed_at_action)) {
      return null;
    }
    knownCells.push({
      x: cell.x,
      y: cell.y,
      kind: cell.kind,
      visible: cell.visible,
      observedAtAction: cell.observed_at_action,
    });
  }

  let lastAction: PublicGridState['lastAction'] = null;
  if (value.last_action !== null) {
    if (!isRecord(value.last_action) || typeof value.last_action.action !== 'string'
      || typeof value.last_action.accepted !== 'boolean'
      || typeof value.last_action.feedback !== 'string') return null;
    lastAction = {
      action: value.last_action.action,
      accepted: value.last_action.accepted,
      feedback: value.last_action.feedback,
    };
  }
  return {
    size,
    position: [value.position[0], value.position[1]],
    inventory: value.inventory,
    actionCount: value.action_count,
    illegalActionCount: value.illegal_action_count,
    knownCells,
    lastAction,
  };
}

export function publicStates(events: TraceEvent[], cutoff = events.length - 1): {
  states: PublicGridState[];
  invalid: boolean;
} {
  const states: PublicGridState[] = [];
  let invalid = false;
  for (const [index, event] of events.entries()) {
    if (index > cutoff) break;
    const observation = isRecord(event.payload.observation) ? event.payload.observation : null;
    const candidate = event.event_type === 'OBSERVATION_CREATED'
      ? event.payload.initial_state
      : event.event_type === 'ENVIRONMENT_UPDATED' ? event.payload.state
        : event.event_type === 'TOOL_SUCCEEDED' ? observation?.world : undefined;
    if (candidate === undefined) continue;
    const parsed = parsePublicState(candidate);
    if (parsed) {
      if (states[states.length - 1]?.actionCount === parsed.actionCount) states[states.length - 1] = parsed;
      else states.push(parsed);
      invalid = false;
    } else {
      invalid = true;
    }
  }
  return { states, invalid };
}

function ruleRejections(events: TraceEvent[], cutoff: number) {
  const rejections: { step: number; action: string; feedback: string }[] = [];
  for (const [index, event] of events.entries()) {
    if (index > cutoff || event.event_type !== 'TOOL_SUCCEEDED') continue;
    const observation = isRecord(event.payload.observation) ? event.payload.observation : null;
    const result = observation && isRecord(observation.action_result) ? observation.action_result : null;
    if (result?.accepted !== false || typeof result.feedback !== 'string'
      || typeof result.action !== 'string') continue;
    rejections.push({ step: event.step_index, action: result.action, feedback: result.feedback });
  }
  return rejections;
}

const cellMarks: Record<KnownCell['kind'], string> = {
  wall: '#',
  floor: '.',
  key: 'K',
  closed_door: 'D',
  open_door: '/',
  goal: 'G',
};

const cellLabels: Record<KnownCell['kind'], string> = {
  wall: '墙',
  floor: '地面',
  key: '钥匙',
  closed_door: '关闭的门',
  open_door: '已打开的门',
  goal: '目标',
};

/** Render only public GridWorld snapshots that have arrived in this Trace prefix. */
export function GridWorldMap({ events, cutoff = events.length - 1, animate = false }: {
  events: TraceEvent[];
  cutoff?: number;
  animate?: boolean;
}) {
  const [view, setView] = useState<'3d' | '2d'>('3d');
  const [stageStatus, setStageStatus] = useState<'loading' | 'ready' | 'failed'>('loading');
  const { states, invalid } = useMemo(() => publicStates(events, cutoff), [events, cutoff]);
  const state = states[states.length - 1];
  const rejections = ruleRejections(events, cutoff);
  if (!state) return <section className="gridworld-panel" aria-label="Agent 可见地图">
    <h3>Agent 当前视野与已知格</h3>
    <p role={invalid ? 'alert' : 'status'}>{invalid
      ? '收到的环境投影格式无效；为避免泄露，未展示地图。'
      : '等待真实到达的 Agent 可见环境事件。'}</p>
  </section>;

  const [agentX, agentY] = state.position;
  const showStage = view === '3d' && stageStatus !== 'failed';
  const byCoordinate = new Map(state.knownCells.map((cell) => [`${cell.x},${cell.y}`, cell]));
  const width = Math.max(agentX, ...state.knownCells.map((cell) => cell.x)) + 1;
  const height = Math.max(agentY, ...state.knownCells.map((cell) => cell.y)) + 1;
  const cells = Array.from({ length: width * height }, (_, index) => {
    const x = index % width;
    const y = Math.floor(index / width);
    const cell = byCoordinate.get(`${x},${y}`);
    const isAgent = x === agentX && y === agentY;
    const label = cell ? `${cellLabels[cell.kind]}，坐标 (${x}, ${y})${cell.visible ? '，当前可见' : '，最后已知'}` :
      `坐标 (${x}, ${y})，尚无观察`;
    return <span key={`${x},${y}`} className={`gridworld-cell ${cell ? `kind-${cell.kind}` : 'kind-unknown'}${cell?.visible ? ' is-visible' : ''}${isAgent ? ' is-agent' : ''}`}
      aria-label={isAgent ? `Agent，${label}` : label} title={label}>
      {isAgent ? 'A' : cell ? cellMarks[cell.kind] : ''}
    </span>;
  });
  return <section className="gridworld-panel" aria-label="Agent 可见地图">
    <div className="gridworld-heading">
      <div><h3>Agent 当前视野与已知格</h3>
        <p>已探索格会留在地图上，较暗的格子是上次看到的状态。</p></div>
      <span>{state.actionCount} 个环境动作 · {state.illegalActionCount} 次规则拒绝</span>
    </div>
    {stageStatus !== 'failed' && <div className="gridworld-view-control" role="group" aria-label="地图显示方式">
      <button type="button" className="btn-secondary" aria-pressed={view === '3d'} onClick={() => {
        if (view === '3d') return;
        setStageStatus('loading');
        setView('3d');
      }}>三维场景</button>
      <button type="button" className="btn-secondary" aria-pressed={view === '2d'} onClick={() => setView('2d')}>二维地图</button>
    </div>}
    {showStage && <GridWorldStage states={states} animate={animate} onStatus={setStageStatus} />}
    {showStage && stageStatus === 'loading' && <p role="status">正在加载角色与场景，二维地图可先查看。</p>}
    {stageStatus === 'failed' && <p role="status">三维场景暂不可用，已切换到二维地图。</p>}
    <div className={showStage && stageStatus === 'ready' ? 'sr-only' : undefined}>
      <div className="gridworld-board" role="img" aria-label={`Agent 可见地图，当前位置 (${agentX}, ${agentY})`}
        style={{ gridTemplateColumns: `repeat(${width}, minmax(0, 1fr))` }}>
        {cells}
      </div>
      <div className="gridworld-legend" aria-label="地图图例">
        <span><b>A</b> Agent</span><span><b>#</b> 墙</span><span><b>.</b> 地面</span>
        <span><b>K</b> 钥匙</span><span><b>D</b> 关闭的门</span><span><b>/</b> 已打开的门</span><span><b>G</b> 目标</span>
      </div>
    </div>
    {showStage && stageStatus === 'ready' && <p>最新收到的位置 ({agentX}, {agentY}) · {state.inventory.length > 0 ? '已持有钥匙' : '未持有钥匙'}</p>}
    {state.lastAction && <p className={`gridworld-feedback ${state.lastAction.accepted ? '' : 'is-rejected'}`}
      role="status">{state.lastAction.action}：{state.lastAction.feedback}</p>}
    {rejections.length > 0 && <div className="gridworld-rejections" aria-label="规则内拒绝记录">
      <strong>规则内拒绝 · {rejections.length}</strong>
      <ul>{rejections.map((item, index) => <li key={`${item.step}:${item.action}:${index}`}>
        第 {item.step} 轮 · {item.action}：{item.feedback}
      </li>)}</ul>
    </div>}
    {invalid && <p role="alert" className="gridworld-error">后续环境投影格式无效，当前仅保留最后已验证的公开视图。</p>}
  </section>;
}
