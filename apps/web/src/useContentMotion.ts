import { useLayoutEffect, useRef, type RefObject } from 'react';

/** Animate committed UI changes; navigation never waits for this optional feedback. */
export function useContentMotion(
  ref: RefObject<HTMLElement | null>, key: string, position: number,
): void {
  const previous = useRef({ key, position });
  const interrupted = useRef<{ node: HTMLElement; transform: string; opacity: string } | null>(null);
  useLayoutEffect(() => {
    const old = previous.current;
    previous.current = { key, position };
    if (old.key === key) return;
    const node = ref.current;
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!node || preference.matches || typeof node.animate !== 'function') return;
    const direction = position < old.position ? -1 : 1;
    const tokens = getComputedStyle(node);
    const milliseconds = Number.parseFloat(tokens.getPropertyValue('--motion-default'));
    const duration = Number.isFinite(milliseconds) ? Math.max(0, Math.min(300, milliseconds)) : 180;
    const easing = tokens.getPropertyValue('--motion-ease').trim() || 'ease-out';
    const start = interrupted.current?.node === node ? interrupted.current : null;
    interrupted.current = null;
    // Animation owns no application state and leaves no final inline styles behind.
    let animation: Animation;
    try {
      animation = node.animate([
        { opacity: start?.opacity ?? 0.78, transform: start?.transform ?? `translateY(${direction * 6}px)` },
        { opacity: 1, transform: 'translateY(0)' },
      ], { duration, easing });
    } catch {
      return; // A browser without working animation support still shows the committed UI.
    }
    const stop = () => {
      if (preference.matches) { interrupted.current = null; animation.cancel(); }
    };
    preference.addEventListener('change', stop);
    return () => {
      if (animation.playState === 'running' && !preference.matches) {
        const style = getComputedStyle(node);
        interrupted.current = { node, transform: style.transform, opacity: style.opacity };
      }
      preference.removeEventListener('change', stop);
      animation.cancel();
    };
  }, [ref, key, position]);
}
