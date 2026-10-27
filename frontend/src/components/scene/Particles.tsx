'use client';
import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { AdditiveBlending, BufferAttribute, BufferGeometry, NormalBlending, Points, ShaderMaterial } from 'three';
import { FINISH } from '@/lib/glsl';
import { motion } from '@/lib/motion';
import type { ThemeColors } from '@/lib/useThemeColors';

const H = 5; // half height of the particle volume
const VERT = /* glsl */ `
  attribute float aSeed;
  uniform float uTime; uniform float uScale; uniform float uPush; uniform float uSize; uniform float uH;
  varying float vA;
  void main(){
    float y = mod(position.y + uH + (uTime * 0.04 + uPush) * (0.4 + aSeed), 2.0 * uH) - uH;
    vec3 p = vec3(position.x + sin(uTime * 0.2 + aSeed * 40.0) * 0.25, y, position.z + cos(uTime * 0.17 + aSeed * 31.0) * 0.25);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    float d = max(-mv.z, 0.1);
    gl_PointSize = clamp(uSize * (0.4 + aSeed) * uScale / d, 1.0, 18.0);
    float q = d * 0.06;
    vA = (0.35 + 0.65 * aSeed) * exp(-q * q) * (1.0 - smoothstep(uH * 0.8, uH, abs(y)));
  }
`;
const FRAG = /* glsl */ `
  uniform vec3 uColor; uniform float uOpacity;
  varying float vA;
  void main(){
    float r = length(gl_PointCoord - 0.5) * 2.0;
    float a = 1.0 - smoothstep(0.0, 1.0, r);
    a *= a;
    gl_FragColor = vec4(uColor, a * vA * uOpacity);
    ${FINISH}
  }
`;

export default function Particles({ colors, count, additive, reduced }: { colors: ThemeColors; count: number; additive: boolean; reduced: boolean }) {
  const ref = useRef<Points>(null);
  const push = useRef(0);
  const geometry = useMemo(() => {
    const pos = new Float32Array(count * 3), seed = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 16;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 2 * H;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 14 - 1;
      seed[i] = Math.random();
    }
    const g = new BufferGeometry();
    g.setAttribute('position', new BufferAttribute(pos, 3));
    g.setAttribute('aSeed', new BufferAttribute(seed, 1));
    return g;
  }, [count]);
  const material = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false,
        uniforms: { uTime: { value: 0 }, uScale: { value: 900 }, uPush: { value: 0 }, uSize: { value: 0.09 }, uH: { value: H }, uColor: { value: colors.particle }, uOpacity: { value: 0.9 } },
      }),
    [colors], // eslint-disable-line react-hooks/exhaustive-deps
  );
  useEffect(() => { material.blending = additive ? AdditiveBlending : NormalBlending; material.needsUpdate = true; }, [additive, material]);
  useFrame(({ clock, size, gl, camera }, dt) => {
    const fov = ((camera as { fov?: number }).fov ?? 50) * (Math.PI / 180);
    material.uniforms.uScale.value = (size.height * gl.getPixelRatio() * 0.5) / Math.tan(fov / 2);
    material.uniforms.uTime.value = reduced ? 0 : clock.elapsedTime;
    push.current += reduced ? 0 : motion.velocity * Math.min(dt, 0.05) * 0.8;   // particles flow only while scrolling
    material.uniforms.uPush.value = push.current;
  });
  useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);
  return <points ref={ref} geometry={geometry} material={material} frustumCulled={false} renderOrder={5} />;
}
