/// <reference types="vite/client" />
import {
  AmbientLight, AnimationMixer, CircleGeometry, Color, DirectionalLight, Group, HemisphereLight,
  LoopOnce, LoopRepeat, Mesh, MeshBasicMaterial, NeutralToneMapping, OrthographicCamera,
  RingGeometry, Scene, WebGLRenderer,
} from 'three';
import type { AnimationAction, AnimationClip, MeshStandardMaterial, Object3D } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import type { PublicGridState } from './GridWorldMap';
import { gridMotion, type GridMotion } from './gridWorldMotion';

type Clip = GridMotion | 'Idle' | 'TurnLeft' | 'TurnRight';
type Cell = PublicGridState['knownCells'][number];
type Position = PublicGridState['position'];
type Tile = { root: Group; door: Group | null; doorAngle: number };

const clipNames = ['Idle', 'Walk', 'TurnLeft', 'TurnRight', 'PickUp', 'OpenDoor'] as const;
const moveDuration = { Walk: 0.43, PickUp: 0.59, OpenDoor: 0.62 };
const openAngle = -Math.PI / 2;
const ease = (value: number) => value * value * (3 - 2 * value);
const cellKey = (x: number, z: number) => `${x},${z}`;
const heading = (from: Position, to: Position) => Math.atan2(to[0] - from[0], to[1] - from[1]);
const shortestAngle = (angle: number) => Math.atan2(Math.sin(angle), Math.cos(angle));
const floorHeight = ({ position: [x, y], knownCells }: PublicGridState) =>
  knownCells.some(cell => cell.x === x && cell.y === y && cell.kind === 'goal') ? 0.1 : 0;

export type GridScene = {
  show: (states: PublicGridState[], animate: boolean) => void;
  dispose: () => void;
};

function makeTileFactory(kit: Group) {
  const sources = new Map(kit.children.map(part => [part.name, part]));
  const dimmed = new Map<MeshStandardMaterial, MeshStandardMaterial>();
  function muted(material: MeshStandardMaterial) {
    if (!dimmed.has(material)) {
      const copy = material.clone();
      copy.color.multiplyScalar(0.58);
      dimmed.set(material, copy);
    }
    return dimmed.get(material)!;
  }
  function add(parent: Group, name: string, visible: boolean, x = 0, z = 0) {
    const source = sources.get(name);
    if (!source) throw new Error(`Missing GridWorld prop: ${name}`);
    const prop = source.clone();
    prop.position.x -= x;
    prop.position.z -= z;
    if (!visible) {
      prop.traverse(part => {
        if (!(part instanceof Mesh)) return;
        const material = part.material as MeshStandardMaterial | MeshStandardMaterial[];
        part.material = Array.isArray(material) ? material.map(muted) : muted(material);
      });
    }
    parent.add(prop);
    return prop;
  }

  function makeTile(cell: Cell): Tile {
    const root = new Group();
    root.position.set(cell.x, 0, cell.y);
    const { kind, visible } = cell;
    const alternate = (cell.x + cell.y) % 2 !== 0;
    add(root, alternate ? 'Floor_1_0' : 'Floor_0_0', visible, alternate ? 1 : 0);
    if (kind === 'wall') {
      const wall = new Group();
      add(wall, 'Wall_0', visible, 0, -1);
      wall.scale.z = 1.14;
      root.add(wall);
    }
    if (kind === 'key') {
      for (const part of ['Key_bow', 'Key_shaft', 'Key_tooth']) add(root, part, visible, -1.29);
    }
    if (kind === 'goal') {
      add(root, 'Goal_tile', visible, 2);
      const ring = add(root, 'Goal_marker', visible, 2);
      ring.rotation.set(0, 0, 0);
      ring.position.y = 0.135;
    }
    if (kind !== 'closed_door' && kind !== 'open_door') return { root, door: null, doorAngle: 0 };

    for (const part of ['Door_jamb', 'Door_jamb001', 'Door_lintel']) add(root, part, visible);
    const door = new Group();
    door.position.z = -0.36;
    add(door, 'Door_panel', visible, 0, door.position.z);
    add(door, 'Door_handle', visible, 0, door.position.z);
    const doorAngle = kind === 'open_door' ? openAngle : 0;
    door.rotation.y = doorAngle;
    root.add(door);
    return { root, door, doorAngle };
  }
  return { makeTile, dispose: () => dimmed.forEach(material => material.dispose()) };
}

export async function createGridScene(
  host: HTMLDivElement, [columns, rows]: PublicGridState['size'], signal: AbortSignal, onFailure: () => void,
): Promise<GridScene> {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const gallery = columns === 9;
  const loader = new GLTFLoader();
  const load = async (asset: string) => {
    const response = await fetch(`${import.meta.env.BASE_URL}gridworld/${asset}`, { signal });
    if (!response.ok) throw new Error(`Cannot load GridWorld asset (${response.status})`);
    return loader.parseAsync(await response.arrayBuffer(), '');
  };
  const [kit, avatar] = await Promise.all([
    load(gallery ? 'gallery-kit.glb' : 'key-door-kit.glb'),
    load('iuno-chibi.glb'),
  ]);
  signal.throwIfAborted();
  const clips = new Map<string, AnimationClip>(avatar.animations.map(clip => [clip.name, clip]));
  for (const name of clipNames) {
    const clip = clips.get(name);
    if (!clip) throw new Error(`Missing GridWorld animation: ${name}`);
    // The board rotates the actor. Keep the Blender turn pose without applying root yaw twice.
    if (name === 'TurnLeft' || name === 'TurnRight') {
      clip.tracks = clip.tracks.filter(track => track.name !== 'Root.quaternion');
    }
  }
  const tiles = makeTileFactory(kit.scene);
  const world = new Group();
  const scene = new Scene();
  scene.background = new Color(gallery ? '#223c46' : '#182b3a');
  scene.add(world, new HemisphereLight(0xf3faff, 0x587583, gallery ? 1.6 : 2.0), new AmbientLight(0xffffff, 0.28));
  const key = new DirectionalLight(0xfff5df, gallery ? 1.9 : 2.2);
  key.position.set(-3, 8, 5);
  scene.add(key);

  const agent = new Group();
  agent.visible = false;
  avatar.scene.scale.setScalar(0.44);
  agent.add(avatar.scene);
  const marker = new Mesh(new RingGeometry(0.34, 0.39, 32), new MeshBasicMaterial({
    color: 0xb3edeb, transparent: true, opacity: 0.75, depthWrite: false,
  }));
  const shadow = new Mesh(new CircleGeometry(0.31, 24), new MeshBasicMaterial({
    color: 0x10222e, transparent: true, opacity: 0.28, depthWrite: false,
  }));
  for (const mesh of [marker, shadow]) {
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = 0.012;
    agent.add(mesh);
  }
  scene.add(agent);

  const mixer = new AnimationMixer(avatar.scene);
  let action: AnimationAction | undefined;
  function play(clip: Clip, duration?: number) {
    const next = mixer.clipAction(clips.get(clip)!);
    if (next === action) return;
    action?.fadeOut(0.08);
    const loop = clip === 'Idle' || clip === 'Walk';
    next.reset().setEffectiveTimeScale(1).setEffectiveWeight(1);
    next.setLoop(loop ? LoopRepeat : LoopOnce, loop ? Infinity : 1);
    next.clampWhenFinished = !loop;
    if (duration !== undefined) next.setDuration(duration);
    if (action) next.fadeIn(0.08);
    next.play();
    action = next;
    canvas.dataset.clip = clip;
  }

  const canvas = document.createElement('canvas');
  const renderer = new WebGLRenderer({ canvas, antialias: true });
  renderer.toneMapping = NeutralToneMapping;
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  const camera = new OrthographicCamera(-5, 5, 4, -4, 0.1, 50);
  const centerX = (columns - 1) / 2;
  const centerZ = (rows - 1) / 2;
  camera.position.set(centerX + 6.7, 6.7, centerZ + 7.2);
  camera.lookAt(centerX, 0, centerZ);
  canvas.addEventListener('webglcontextlost', onFailure);
  host.append(canvas);

  const board = new Map<string, { cell: Cell; tile: Tile }>();
  function place(state: PublicGridState) {
    const keep = new Set<string>();
    for (const cell of state.knownCells) {
      const id = cellKey(cell.x, cell.y);
      keep.add(id);
      const entry = board.get(id);
      if (entry?.cell.kind === cell.kind && entry.cell.visible === cell.visible) {
        if (entry.tile.door) entry.tile.door.rotation.y = entry.tile.doorAngle;
        continue;
      }
      if (entry) world.remove(entry.tile.root);
      const tile = tiles.makeTile(cell);
      world.add(tile.root);
      board.set(id, { cell, tile });
    }
    for (const [id, entry] of board) {
      if (keep.has(id)) continue;
      world.remove(entry.tile.root);
      board.delete(id);
    }
    agent.visible = true;
    agent.position.set(state.position[0], floorHeight(state), state.position[1]);
    canvas.dataset.position = cellKey(...state.position);
    canvas.dataset.action = String(state.actionCount);
  }

  type Transition = {
    from: PublicGridState; to: PublicGridState; clip: GridMotion;
    yaw: number; turn: number; turnDuration: number; elapsed: number; started: boolean;
    door: Group | null;
  };
  let current: PublicGridState | undefined;
  let transition: Transition | undefined;
  let queued: PublicGridState[] = [];

  function begin() {
    while (current && !transition && queued.length) {
      const target = queued.shift()!;
      const move = gridMotion(current, target);
      if (!move) {
        place(target);
        current = target;
        continue;
      }
      const yaw = agent.rotation.y;
      const turn = move.facing ? shortestAngle(heading(current.position, move.facing) - yaw) : 0;
      const turnDuration = Math.abs(turn) > 0.01 ? 0.22 : 0;
      const door = move.clip === 'OpenDoor' && move.facing
        ? board.get(cellKey(...move.facing))?.tile.door ?? null : null;
      transition = { from: current, to: target, clip: move.clip, yaw, turn, turnDuration, elapsed: 0, started: false, door };
      if (turnDuration) play(turn > 0 ? 'TurnLeft' : 'TurnRight', turnDuration);
    }
    if (!transition) play('Idle');
  }

  function advance(delta: number) {
    begin();
    const movement = transition;
    if (!movement) return;
    movement.elapsed += delta;
    const { from, to, yaw, turn, turnDuration, elapsed, clip, door } = movement;
    agent.rotation.y = yaw + turn * (turnDuration ? ease(Math.min(1, elapsed / turnDuration)) : 1);
    if (elapsed < turnDuration) return;
    if (!movement.started) {
      play(clip, moveDuration[clip]);
      movement.started = true;
    }
    const progress = Math.min(1, (elapsed - turnDuration) / moveDuration[clip]);
    if (clip === 'Walk') {
      agent.position.x = from.position[0] + (to.position[0] - from.position[0]) * progress;
      agent.position.z = from.position[1] + (to.position[1] - from.position[1]) * progress;
      const start = floorHeight(from);
      agent.position.y = start + (floorHeight(to) - start) * progress;
    }
    if (door) door.rotation.y = openAngle * ease(Math.max(0, (progress - 0.39) / 0.61));
    if (progress === 1) {
      place(to);
      current = to;
      transition = undefined;
      play('Idle');
    }
  }

  function reset(states: PublicGridState[]) {
    current = states[states.length - 1];
    transition = undefined;
    queued = [];
    if (!current) return;
    let yaw = 0;
    for (let i = 1; i < states.length; i++) {
      const motion = gridMotion(states[i - 1], states[i]);
      if (motion?.facing) yaw = heading(states[i - 1].position, motion.facing);
    }
    agent.rotation.y = yaw;
    place(current);
    play('Idle');
    if (reducedMotion.matches && action) {
      action.time = 0;
      mixer.update(0);
    }
  }

  function render() { renderer.render(scene, camera); }
  function resize() {
    const { clientWidth: width, clientHeight: height } = host;
    if (!width || !height) return;
    const aspect = width / height;
    const span = Math.max(rows + (gallery ? 0.2 : 0.8), (columns + 2.2) / aspect);
    camera.top = span / 2;
    camera.bottom = -camera.top;
    camera.right = camera.top * aspect;
    camera.left = -camera.right;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    render();
  }

  const observer = new ResizeObserver(resize);
  observer.observe(host);
  let latest: PublicGridState[] = [];
  let lastFrame = 0;
  let frame = 0;
  let visible = true;
  const intersection = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
  });
  intersection.observe(host);
  function tick(now: number) {
    frame = requestAnimationFrame(tick);
    if (now - lastFrame < 30) return;
    const delta = Math.min(0.06, (now - lastFrame) / 1000);
    lastFrame = now;
    if (!current || reducedMotion.matches) return;
    advance(delta);
    mixer.update(delta);
    if (visible) render();
  }
  frame = requestAnimationFrame(tick);
  const onMotionChange = () => { reset(latest); render(); };
  reducedMotion.addEventListener('change', onMotionChange);
  resize();

  return {
    show(states, animate) {
      latest = states;
      const next = states[states.length - 1];
      if (!next) return;
      const tail = queued[queued.length - 1] ?? transition?.to ?? current;
      if (!tail || next.actionCount < tail.actionCount || (!animate && next.actionCount !== tail.actionCount)
        || (reducedMotion.matches && next.actionCount !== tail.actionCount)) {
        reset(states);
        render();
      } else if (next.actionCount > tail.actionCount) {
        queued.push(...states.filter(state => state.actionCount > tail.actionCount));
      }
    },
    dispose() {
      cancelAnimationFrame(frame);
      observer.disconnect();
      intersection.disconnect();
      reducedMotion.removeEventListener('change', onMotionChange);
      canvas.removeEventListener('webglcontextlost', onFailure);
      mixer.stopAllAction();
      mixer.uncacheRoot(avatar.scene);
      tiles.dispose();
      for (const root of [kit.scene, avatar.scene, marker, shadow]) {
        root.traverse((part: Object3D) => {
          if (!(part instanceof Mesh)) return;
          part.geometry.dispose();
          const materials = Array.isArray(part.material) ? part.material : [part.material];
          materials.forEach(material => material.dispose());
        });
      }
      renderer.dispose();
      canvas.remove();
    },
  };
}
