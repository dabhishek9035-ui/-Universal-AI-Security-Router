'use client';
import { useEffect } from 'react';
import { motion } from '@/lib/motion';

/** Writes scroll progress/velocity + mouse into `motion` (no React state, no re-renders). */
export function useScrollMotion(enabled = true) {
  useEffect(() => {
    let lastY = window.scrollY, lastT = performance.now(), raf = 0;
    const onScroll = () => {
      const now = performance.now();
      const dy = window.scrollY - lastY;
      const dt = Math.max(12, now - lastT);
      lastY = window.scrollY; lastT = now;
      const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      motion.progress = Math.min(1, Math.max(0, window.scrollY / max));
      if (enabled) motion.velocity = Math.min(3.2, (Math.abs(dy) / dt) * 0.48);
    };
    const decay = () => { motion.velocity *= 0.9; if (motion.velocity < 0.01) motion.velocity = 0; raf = requestAnimationFrame(decay); };
    const onMouse = (e: MouseEvent) => { motion.mx = (e.clientX / window.innerWidth - 0.5) * 2; motion.my = (e.clientY / window.innerHeight - 0.5) * 2; };
    onScroll();
    raf = requestAnimationFrame(decay);
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('mousemove', onMouse, { passive: true });
    return () => { cancelAnimationFrame(raf); window.removeEventListener('scroll', onScroll); window.removeEventListener('mousemove', onMouse); };
  }, [enabled]);
}
