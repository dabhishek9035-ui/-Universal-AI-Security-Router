'use client';
import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { ContactShadows, Environment, Lightformer } from '@react-three/drei';
import type { DirectionalLight } from 'three';
import type { ThemeColors } from '@/lib/useThemeColors';

/**
 * Studio lighting for real models. A glTF without light and reflections looks like grey plastic.
 *  - procedural environment (Lightformers): NO remote HDRI download, works offline and under strict CSP
 *  - key light (warm-white), rim light that follows the THEME highlight colour
 *  - soft contact shadow so the subject sits in the scene instead of floating
 */
export default function Stage({ colors, shadows }: { colors: ThemeColors; shadows: boolean }) {
  const rim = useRef<DirectionalLight>(null);
  const fill = useRef<DirectionalLight>(null);
  useFrame(() => { rim.current?.color.copy(colors.c3); fill.current?.color.copy(colors.c2).lerp(colors.c3, 0.25); });
  return (
    <>
      <ambientLight intensity={0.25} />
      <directionalLight position={[3, 5, 4]} intensity={2.4} castShadow={shadows} shadow-mapSize={[1024, 1024]} shadow-bias={-0.0004} />
      <directionalLight ref={rim} position={[-4, 2.5, -3]} intensity={3.2} />
      <directionalLight ref={fill} position={[-3, 1, 4]} intensity={0.9} />
      <Environment resolution={256} frames={1}>
        <Lightformer form="rect" intensity={5} position={[0, 5, -6]} scale={[12, 3, 1]} />
        <Lightformer form="rect" intensity={2.5} position={[-6, 1.5, 2]} rotation-y={Math.PI / 2} scale={[8, 3, 1]} />
        <Lightformer form="ring" intensity={3} color="#ffffff" position={[5, 2, 3]} scale={3} />
      </Environment>
      {shadows && <ContactShadows position={[0, 0.001, 0]} opacity={0.55} scale={9} blur={2.6} far={4.5} resolution={512} frames={1} />}
    </>
  );
}
