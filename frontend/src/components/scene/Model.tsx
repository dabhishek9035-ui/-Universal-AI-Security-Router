'use client';
import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { useAnimations, useGLTF } from '@react-three/drei';
import { AnimationClip, Box3, Group, LoopRepeat, Mesh, MeshStandardMaterial, Object3D, Vector3 } from 'three';
import { clone as cloneWithSkeleton } from 'three/examples/jsm/utils/SkeletonUtils.js';
import { motion } from '@/lib/motion';
import type { Subject } from '@/lib/subject';

type Loaded = { scene: Group; animations: AnimationClip[] };

/**
 * Loads a glTF and makes it stage-ready:
 *  - clones it (skeleton-safe) so the same file can appear several times
 *  - auto-fits: scales to `height`, centres on X/Z, puts the feet on y = 0
 *  - enables shadows, tames over-bright env reflections
 *  - plays a looping clip (or scrubs one with scroll), pauses everything under reduced motion
 * Compressed files: meshopt works out of the box with drei; Draco loads its decoder from a CDN unless you
 * host it (`useGLTF.setDecoderPath('/draco/')`). Prefer meshopt (`gltf-transform optimize --compress meshopt`).
 */
export default function Model({ subject, reduced, shadows }: { subject: Subject; reduced: boolean; shadows: boolean }) {
  const gltf = useGLTF(subject.url as string) as unknown as Loaded;
  const root = useRef<Group>(null);
  const object = useMemo<Object3D>(() => cloneWithSkeleton(gltf.scene), [gltf.scene]);
  const { actions, mixer } = useAnimations(gltf.animations, root);

  // auto-fit (bind-pose bounds are fine for a stage)
  const fit = useMemo(() => {
    object.updateMatrixWorld(true);                 // REQUIRED: a fresh clone has stale world matrices -> wrong bounds -> tiny/huge model
    const box = new Box3().setFromObject(object);
    const size = box.getSize(new Vector3());
    const centre = box.getCenter(new Vector3());
    const s = subject.height / Math.max(size.y, 1e-3);
    return { s, x: -centre.x * s, y: -box.min.y * s, z: -centre.z * s };
  }, [object, subject.height]);

  useEffect(() => {
    object.traverse((o) => {
      const m = o as Mesh;
      if (!m.isMesh) return;
      m.castShadow = shadows; m.receiveShadow = shadows;
      const mat = m.material as MeshStandardMaterial;
      if (mat && 'envMapIntensity' in mat) mat.envMapIntensity = 0.9;
    });
  }, [object, shadows]);

  useEffect(() => {
    const names = Object.keys(actions);
    const pick = subject.clip && actions[subject.clip] ? subject.clip : actions['Idle'] ? 'Idle' : names[0];
    const play = pick ? actions[pick] : null;
    const scrub = subject.scrub ? actions[subject.scrub] : null;
    if (scrub) { scrub.reset().play(); scrub.paused = true; return () => { scrub.stop(); }; }
    if (!play) return;
    play.reset().setLoop(LoopRepeat, Infinity).fadeIn(0.4).play();
    if (reduced) play.paused = true;           // freeze on the first pose
    return () => { play.fadeOut(0.3); };
  }, [actions, subject.clip, subject.scrub, reduced]);

  useFrame(() => {
    const scrub = subject.scrub ? actions[subject.scrub] : null;
    if (scrub && mixer) scrub.time = motion.progress * scrub.getClip().duration * 0.999;
  });

  return (
    <group ref={root}>
      <group scale={fit.s} position={[fit.x, fit.y, fit.z]}>
        <primitive object={object} />
      </group>
    </group>
  );
}

export const preloadSubject = (url: string | null) => { if (url) useGLTF.preload(url); };
