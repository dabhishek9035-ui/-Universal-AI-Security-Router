'use client';
import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { IcosahedronGeometry, Mesh, ShaderMaterial } from 'three';
import { FINISH, NOISE } from '@/lib/glsl';
import { motion } from '@/lib/motion';
import { useStore } from '@/state/store';
import type { ThemeColors } from '@/lib/useThemeColors';

const VERT = /* glsl */ `
  uniform float uTime; uniform float uAmp;
  varying vec3 vPos; varying vec3 vWorld;
  ${NOISE}
  void main(){
    vec3 p = position;
    float n = vnoise3(p * 1.6 + vec3(0.0, uTime * 0.35, 0.0));
    p += normal * (n - 0.5) * uAmp;
    vPos = p;
    vec4 w = modelMatrix * vec4(p, 1.0);
    vWorld = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;
const FRAG = /* glsl */ `
  uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3; uniform float uThreat;
  varying vec3 vPos; varying vec3 vWorld;
  void main(){
    vec3 N = normalize(cross(dFdx(vWorld), dFdy(vWorld)));   // faceted-free at high subdivision
    vec3 V = normalize(cameraPosition - vWorld);
    float fres = pow(1.0 - clamp(dot(N, V), 0.0, 1.0), 2.5);
    vec3 base = mix(uC1, uC2, clamp(vPos.y * 0.5 + 0.5, 0.0, 1.0));
    // threat pressure: surface heats toward the highlight colour as the
    // blocked share of live traffic rises (same value as the DOM "Blocked" KPI)
    vec3 hot = mix(base, uC3, clamp(uThreat * 0.55, 0.0, 0.55));
    vec3 L = normalize(vec3(0.5, 0.8, 0.6));
    float diff = clamp(dot(N, L), 0.0, 1.0);
    float spec = pow(clamp(dot(reflect(-L, N), V), 0.0, 1.0), 40.0);
    vec3 col = hot * (0.35 + 0.65 * diff) + uC3 * fres * (0.9 + uThreat * 0.5) + uC3 * spec * 0.6;
    gl_FragColor = vec4(col, 1.0);
    ${FINISH}
  }
`;

export default function Orb({ colors, reduced, detail = 48 }: { colors: ThemeColors; reduced: boolean; detail?: number }) {
  const mesh = useRef<Mesh>(null);
  const threatTarget = useRef(0);
  const threatLevel = useStore((s) => s.threatLevel);
  threatTarget.current = threatLevel; // low-frequency store write -> plain ref for useFrame
  const geometry = useMemo(() => new IcosahedronGeometry(1.35, detail), [detail]);
  const material = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: VERT, fragmentShader: FRAG,
        uniforms: {
          uTime: { value: 0 }, uAmp: { value: 0.28 }, uThreat: { value: 0 },
          uC1: { value: colors.c1 }, uC2: { value: colors.c2 }, uC3: { value: colors.c3 },
        },
      }),
    [colors], // eslint-disable-line react-hooks/exhaustive-deps
  );
  useFrame(({ clock }, dt) => {
    const u = material.uniforms;
    u.uTime.value = reduced ? 0 : clock.elapsedTime;
    // ease toward the store's target: the orb is a *view* of live gateway state
    u.uThreat.value += (threatTarget.current - u.uThreat.value) * (1 - Math.exp(-dt * 1.8));
    u.uAmp.value = 0.28 + u.uThreat.value * 0.42 + Math.min(motion.velocity, 2) * 0.12;
    if (mesh.current) {
      mesh.current.rotation.y += dt * (reduced ? 0 : 0.12 + motion.velocity * 0.4 + u.uThreat.value * 0.35);
      mesh.current.position.y = -motion.progress * 1.2;
      mesh.current.position.x = 1.1 - motion.progress * 2.2;   // drift across the layout as you scroll
    }
  });
  useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);
  return <mesh ref={mesh} geometry={geometry} material={material} />;
}
