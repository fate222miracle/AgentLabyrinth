import type { PublicGridState } from './GridWorldMap';

type Position = PublicGridState['position'];
export type GridMotion = 'Walk' | 'PickUp' | 'OpenDoor';

function samePosition(a: Position, b: Position) {
  return a[0] === b[0] && a[1] === b[1];
}

export function gridMotion(previous: PublicGridState, next: PublicGridState): {
  clip: GridMotion;
  facing?: Position;
} | null {
  if (next.actionCount !== previous.actionCount + 1 || !next.lastAction?.accepted) return null;
  const action = next.lastAction.action;
  const dx = next.position[0] - previous.position[0];
  const dz = next.position[1] - previous.position[1];
  if ((action === 'move_up' && dx === 0 && dz === -1)
    || (action === 'move_down' && dx === 0 && dz === 1)
    || (action === 'move_left' && dx === -1 && dz === 0)
    || (action === 'move_right' && dx === 1 && dz === 0)) {
    return { clip: 'Walk', facing: next.position };
  }
  if (!samePosition(previous.position, next.position)) return null;
  if (action === 'pickup' && next.inventory.some(item => !previous.inventory.includes(item))) {
    return { clip: 'PickUp' };
  }
  if (action === 'use') {
    const door = next.knownCells.find(cell => cell.kind === 'open_door'
      && Math.abs(cell.x - next.position[0]) + Math.abs(cell.y - next.position[1]) === 1
      && previous.knownCells.some(old => old.x === cell.x && old.y === cell.y && old.kind === 'closed_door'));
    if (door) return { clip: 'OpenDoor', facing: [door.x, door.y] };
  }
  return null;
}
