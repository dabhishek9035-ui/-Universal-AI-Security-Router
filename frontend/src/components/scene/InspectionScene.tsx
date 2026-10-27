'use client';
import { useEffect, useRef } from 'react';
import { ContactShadows, Environment, Html, Lightformer, OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { useStore, type ViewerView } from '@/state/store';
import { SUBJECT } from '@/lib/subject';
import Model from './Model';

const VIEW_POSES: Record<ViewerView, [number, number, number]> = {
  'three-quarter': [3.8, 2.35, 5.2],
  front: [0, 2.1, 6.6],
  side: [6.6, 2.1, 0],
};

/** Interactive model-stage example. Tune the neutral studio and hotspot anchor for the actual asset. */
export default function InspectionScene() {
  const controls = useRef<OrbitControlsImpl>(null);
  const viewerView = useStore((s) => s.viewerView);
  const reduced = useStore((s) => s.reducedMotion);
  const shadows = useStore((s) => s.quality === 'high');
  const selectedHotspot = useStore((s) => s.viewerHotspot);
  const setViewerHotspot = useStore((s) => s.setViewerHotspot);

  useEffect(() => {
    const control = controls.current;
    if (!control) return;
    control.object.position.set(...VIEW_POSES[viewerView]);
    control.target.set(0, SUBJECT.height * 0.48, 0);
    control.update();
  }, [viewerView]);

  return (
    <>
      <color attach="background" args={['#d8d4ce']} />
      <ambientLight intensity={0.32} />
      <directionalLight position={[3.5, 5, 4]} intensity={2.1} castShadow shadow-mapSize={[1024, 1024]} shadow-bias={-0.0003} />
      <directionalLight position={[-4, 2.5, 1]} intensity={0.65} color="#e4e8ed" />
      <Environment resolution={256} frames={1}>
        <Lightformer form="rect" intensity={3.2} position={[0, 5, -3]} scale={[7, 3, 1]} />
        <Lightformer form="rect" intensity={2.1} position={[-4, 2.2, 2]} rotation-y={Math.PI / 2} scale={[4, 3, 1]} />
        <Lightformer form="rect" intensity={1.5} position={[4, 1.8, 1]} rotation-y={-Math.PI / 2} scale={[3, 2, 1]} />
      </Environment>

      <mesh rotation-x={-Math.PI / 2} position-y={-0.015} receiveShadow>
        <planeGeometry args={[200, 200]} />
        <meshStandardMaterial color="#d8d4ce" roughness={0.94} />
      </mesh>
      <ContactShadows position={[0, 0.002, 0]} opacity={0.4} scale={5} blur={2.2} far={3.5} resolution={512} frames={1} />

      <Model subject={SUBJECT} reduced={reduced} shadows={shadows} />

      {/* World-space example anchor: move this to a meaningful point on the replacement model. */}
      <Html position={[0, SUBJECT.height * 0.68, 0.3]} center distanceFactor={7}>
        <button
          className={`viewer-hotspot${selectedHotspot === 'head' ? ' selected' : ''}`}
          aria-label={selectedHotspot === 'head' ? 'Hide head detail' : 'Show head detail'}
          aria-pressed={selectedHotspot === 'head'}
          onClick={() => setViewerHotspot(selectedHotspot === 'head' ? null : 'head')}
        >
          <span>01</span>
        </button>
      </Html>

      <OrbitControls
        ref={controls}
        target={[0, SUBJECT.height * 0.48, 0]}
        enableDamping
        dampingFactor={0.08}
        enablePan={false}
        minDistance={2.8}
        maxDistance={8}
        minPolarAngle={0.45}
        maxPolarAngle={2.35}
        minAzimuthAngle={-Math.PI * 0.92}
        maxAzimuthAngle={Math.PI * 0.92}
      />
    </>
  );
}
