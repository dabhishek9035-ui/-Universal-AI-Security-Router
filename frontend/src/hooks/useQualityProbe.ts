'use client';
import { useEffect } from 'react';
import { useStore } from '@/state/store';

/**
 * Pick a quality tier from real frame times. Skip the first 2.5 s (shader compile + hydration hitch
 * would otherwise force everyone to "low"), then use the MEDIAN frame time. Never auto-upgrades.
 */
export function useQualityProbe() {
  const setQuality = useStore((s) => s.setQuality);
  useEffect(() => {
    if (window.matchMedia('(pointer: coarse)').matches) setQuality('medium');   // phones/tablets start lower
    let raf = 0, last = 0;
    const start = performance.now();
    const samples: number[] = [];
    const tick = (now: number) => {
      if (last && now - start > 2500) samples.push(now - last);
      last = now;
      if (now - start < 5500) { raf = requestAnimationFrame(tick); return; }
      if (samples.length < 20) return;
      samples.sort((a, b) => a - b);
      const fps = 1000 / samples[Math.floor(samples.length / 2)];
      if (fps < 20) setQuality('low'); else if (fps < 38) setQuality('medium');
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [setQuality]);
}
