import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { PublicGridState } from './GridWorldMap';
import type { GridScene } from './gridWorldScene';

export function GridWorldStage({ states, animate, onStatus }: {
  states: PublicGridState[];
  animate: boolean;
  onStatus: (status: 'ready' | 'failed') => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const scene = useRef<GridScene>();
  const latest = useRef({ states, animate });
  const [ready, setReady] = useState(false);

  useLayoutEffect(() => {
    latest.current = { states, animate };
    scene.current?.show(states, animate);
  }, [states, animate]);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let disposed = false;
    const initial = latest.current.states[latest.current.states.length - 1];
    const abort = new AbortController();
    void import('./gridWorldScene').then(async ({ createGridScene }) => {
      if (abort.signal.aborted) return;
      const result = await createGridScene(element, initial?.size ?? [7, 5], abort.signal, () => onStatus('failed'));
      if (disposed) { result.dispose(); return; }
      scene.current = result;
      if (initial) result.show([initial], false);
      result.show(latest.current.states, latest.current.animate);
      setReady(true);
      onStatus('ready');
    }).catch(() => {
      if (!disposed) onStatus('failed');
    });
    return () => {
      disposed = true;
      abort.abort();
      scene.current?.dispose();
      scene.current = undefined;
    };
  }, [onStatus]);

  return <div className="gridworld-stage" data-ready={ready} ref={host} aria-hidden="true" />;
}
