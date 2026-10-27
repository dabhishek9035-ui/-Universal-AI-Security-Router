'use client';
import { useEffect, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { usePathname } from 'next/navigation';
import { NeutralToneMapping } from 'three';
import { useQualityProbe } from '@/hooks/useQualityProbe';
import { useScrollMotion } from '@/hooks/useScrollMotion';
import { useStore } from '@/state/store';
import Post from './scene/Post';
import Scene from './scene/Scene';
import InspectionScene from './scene/InspectionScene';

function webglOk() {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch { return false; }
}

/** One persistent, fixed canvas behind the whole site. Pages never mount their own <Canvas>. */
export default function SceneCanvas() {
  const pathname = usePathname();
  const isViewer = pathname === '/viewer';
  const [ok, setOk] = useState<boolean | null>(null);
  const [visible, setVisible] = useState(true);
  const reduced = useStore((s) => s.reducedMotion);
  const quality = useStore((s) => s.quality);
  const setReduced = useStore((s) => s.setReducedMotion);
  const setWebglAvailable = useStore((s) => s.setWebglAvailable);
  useScrollMotion(!reduced);
  useQualityProbe();

  useEffect(() => {
    const available = webglOk();
    setOk(available);
    setWebglAvailable(available);
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setReduced(mq.matches);
    sync(); mq.addEventListener('change', sync);
    const vis = () => setVisible(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', vis);
    return () => { mq.removeEventListener('change', sync); document.removeEventListener('visibilitychange', vis); };
  }, [setReduced, setWebglAvailable]);

  useEffect(() => {
    document.body.dataset.experience = isViewer ? 'viewer' : '';
    return () => { delete document.body.dataset.experience; };
  }, [isViewer]);

  if (ok === null) return null;
  if (!ok) return isViewer ? <div className="scene-canvas-fallback" role="status">3D preview needs WebGL. The page content and model credits are still available.</div> : null;
  return (
    <div className={`scene-canvas${isViewer ? ' interactive' : ''}`} aria-hidden={isViewer ? undefined : true}>
      <Canvas
        shadows={quality === 'high'}
        dpr={[1, 1.75]}
        frameloop={visible ? 'always' : 'never'}
        camera={isViewer ? { position: [3.8, 2.35, 5.2], fov: 38, near: 0.1, far: 100 } : { position: [0, 0, 6], fov: 50, near: 0.1, far: 100 }}
        gl={{ antialias: false, alpha: false, powerPreference: 'high-performance', toneMapping: NeutralToneMapping }}
      >
        {isViewer ? <InspectionScene /> : <><Scene /><Post /></>}
      </Canvas>
    </div>
  );
}
