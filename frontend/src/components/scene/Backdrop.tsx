'use client';
import { useEffect, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { PlaneGeometry, ShaderMaterial } from 'three';
import { FINISH, NOISE } from '@/lib/glsl';
import { motion } from '@/lib/motion';
import type { ThemeColors } from '@/lib/useThemeColors';

const VERT = /* glsl */ `
  varying vec2 vUv;
  void main(){
    vUv = uv;
    gl_Position = vec4(position.xy, 0.9999, 1.0);   // full-screen, at the far plane
  }
`;
const FRAG = /* glsl */ `
  varying vec2 vUv;
  uniform float uTime; uniform float uProgress; uniform float uWarp; uniform float uAspect;
  uniform vec2 uMouse; uniform vec3 uBg; uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3;
  ${NOISE}
  void main(){
    vec2 p = (vUv - 0.5) * vec2(uAspect, 1.0) * 2.2 + uMouse * 0.15;
    float t = uTime * 0.05;
    vec2 q = vec2(fbm(p + vec2(0.0, t)), fbm(p + vec2(5.2, 1.3) - t));
    vec2 r = vec2(fbm(p + 3.0 * q + vec2(1.7, 9.2) + t * 0.7), fbm(p + 3.0 * q + vec2(8.3, 2.8) - t * 0.6));
    float f = fbm(p + uWarp * 4.0 * r);
    vec3 col = mix(uBg, uC1, smoothstep(0.1, 0.6, f));
    col = mix(col, uC2, smoothstep(0.45, 0.95, f) * (0.35 + 0.65 * uWarp));
    col += uC3 * pow(smoothstep(0.55, 1.0, length(r)), 3.0) * 0.35;
    float v = smoothstep(-0.1, 1.1, 1.0 - vUv.y + uProgress * 0.3);
    col = mix(uBg, col, 0.35 + 0.65 * v);
    col *= 1.0 - 0.45 * smoothstep(0.35, 1.1, length(vUv - 0.5) * 1.4);
    col += (hash21(gl_FragCoord.xy + uTime) - 0.5) / 255.0;   // dither: kills banding in dark gradients
    gl_FragColor = vec4(col, 1.0);
    ${FINISH}
  }
`;

export default function Backdrop({ colors, warp, reduced }: { colors: ThemeColors; warp: number; reduced: boolean }) {
  const geometry = useMemo(() => new PlaneGeometry(2, 2), []);
  const material = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: VERT, fragmentShader: FRAG, depthTest: false, depthWrite: false,
        uniforms: {
          uTime: { value: 0 }, uProgress: { value: 0 }, uWarp: { value: warp }, uAspect: { value: 1.6 }, uMouse: { value: [0, 0] },
          uBg: { value: colors.bg }, uC1: { value: colors.c1 }, uC2: { value: colors.c2 }, uC3: { value: colors.c3 },
        },
      }),
    [colors], // eslint-disable-line react-hooks/exhaustive-deps
  );
  useFrame(({ clock, size }) => {
    const u = material.uniforms;
    u.uTime.value = reduced ? 0 : clock.elapsedTime;
    u.uProgress.value = motion.progress;
    u.uWarp.value += (warp - u.uWarp.value) * 0.05;
    u.uAspect.value = size.width / Math.max(1, size.height);
    u.uMouse.value = [motion.mx, -motion.my];
  });
  useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);
  return <mesh geometry={geometry} material={material} renderOrder={-100} frustumCulled={false} />;
}
