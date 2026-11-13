import { useEffect, useLayoutEffect, useRef, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.(QUERY).matches === true;
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(prefersReducedMotion);
  useEffect(() => {
    const mq = window.matchMedia?.(QUERY);
    if (!mq) return;
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&";

/**
 * Decodes `text` from random glyphs, one letter at a time, left to right.
 * Used once for a token label that has just arrived, to show that a value was replaced.
 */
export function useScramble(text: string, active: boolean, duration = 420): string {
  const [out, setOut] = useState(active && !prefersReducedMotion() ? scramble(text, 0) : text);

  useEffect(() => {
    if (!active || prefersReducedMotion()) {
      setOut(text);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setOut(scramble(text, Math.floor(t * text.length)));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // run once per label; later re-renders of a streaming message must not restart it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  return out;
}

function scramble(text: string, settled: number): string {
  let s = text.slice(0, settled);
  for (let i = settled; i < text.length; i++) {
    s += text[i] === "_" ? "_" : GLYPHS[(Math.random() * GLYPHS.length) | 0];
  }
  return s;
}

/**
 * Position of a marker that slides to the active item of a list or tab row.
 * Returns a ref for the container and the style for the marker element.
 */
export function useSlidingMarker<T extends HTMLElement>(
  activeKey: string | null,
  axis: "x" | "y",
  deps: unknown[] = [],
) {
  const containerRef = useRef<T>(null);
  const [style, setStyle] = useState<React.CSSProperties>({ opacity: 0 });
  const firstRef = useRef(true);
  // re-measure when the layout can shift under the marker: web fonts arrive, window resizes
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const bump = () => setTick((t) => t + 1);
    document.fonts?.ready.then(bump).catch(() => {});
    window.addEventListener("resize", bump);
    return () => window.removeEventListener("resize", bump);
  }, []);

  useLayoutEffect(() => {
    const el = containerRef.current?.querySelector<HTMLElement>(
      activeKey ? `[data-key="${CSS.escape(activeKey)}"]` : "[data-never]",
    );
    if (!el) {
      setStyle((s) => ({ ...s, opacity: 0 }));
      return;
    }
    const next: React.CSSProperties =
      axis === "y"
        ? { transform: `translateY(${el.offsetTop}px)`, height: el.offsetHeight, opacity: 1 }
        : { transform: `translateX(${el.offsetLeft}px)`, width: el.offsetWidth, opacity: 1 };
    // the first placement must not animate in from 0
    if (firstRef.current) {
      next.transition = "none";
      firstRef.current = false;
    }
    setStyle(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey, axis, tick, ...deps]);

  return { containerRef, markerStyle: style };
}
