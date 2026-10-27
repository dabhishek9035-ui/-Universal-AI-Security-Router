'use client';
import { Suspense, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import type { Group } from 'three';
import { motion } from '@/lib/motion';
import { SUBJECT } from '@/lib/subject';
import { getTheme } from '@/lib/themes';
import { useThemeColors } from '@/lib/useThemeColors';
import { useStore } from '@/state/store';
import Backdrop from './Backdrop';
import Model, { preloadSubject } from './Model';
import Orb from './Orb';
import ParticleFigure from './ParticleFigure';
import Particles from './Particles';
import Rig from './Rig';
import Stage from './Stage';

preloadSubject(SUBJECT.url);

/** The subject drifts across the layout with scroll and turns slightly toward the pointer. */
function SubjectRig({ children }: { children: React.ReactNode }) {
  const g = useRef<Group>(null);
  useFrame((_, dt) => {
    if (!g.current) return;
    const k = 1 - Math.exp(-Math.min(dt, 0.05) * 3);
    g.current.position.x += (1.15 - motion.progress * 2.3 - g.current.position.x) * k;
    g.current.position.y += (-1.25 - motion.progress * 0.9 - g.current.position.y) * k;
    g.current.rotation.y += (SUBJECT.rotationY + motion.mx * 0.35 - g.current.rotation.y) * k;
  });
  return <group ref={g}>{children}</group>;
}

/** Compose back-to-front: backdrop -> ambient particles -> SUBJECT (real model, or the abstract orb when url is null). */
export default function Scene() {
  const theme = getTheme(useStore((s) => s.themeId));
  const quality = useStore((s) => s.quality);
  const reduced = useStore((s) => s.reducedMotion);
  const colors = useThemeColors(theme);
  const shadows = quality === 'high';
  return (
    <>
      <Rig reduced={reduced} />
      <Backdrop colors={colors} warp={theme.scene.warp} reduced={reduced} />
      <Particles colors={colors} additive={theme.scene.additive} reduced={reduced} count={quality === 'high' ? 900 : quality === 'medium' ? 450 : 160} />
      {SUBJECT.url ? (
        <Suspense fallback={null}>
          <Stage colors={colors} shadows={shadows} />
          <SubjectRig>
            {SUBJECT.mode === 'particles'
              ? <ParticleFigure subject={SUBJECT} colors={colors} additive={theme.scene.additive} reduced={reduced} count={quality === 'high' ? 24000 : quality === 'medium' ? 12000 : 5000} />
              : <Model subject={SUBJECT} reduced={reduced} shadows={shadows} />}
          </SubjectRig>
        </Suspense>
      ) : (
        <Orb colors={colors} reduced={reduced} detail={quality === 'low' ? 24 : 48} />
      )}
    </>
  );
}
