'use client';
import { useEffect, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';
import { AdditiveBlending, BufferAttribute, BufferGeometry, Group, Mesh, NormalBlending, Object3D, ShaderMaterial, Vector3, Box3 } from 'three';
import { MeshSurfaceSampler } from 'three/examples/jsm/math/MeshSurfaceSampler.js';
import { FINISH, NOISE } from '@/lib/glsl';
import { motion } from '@/lib/motion';
import type { Subject } from '@/lib/subject';
import type { ThemeColors } from '@/lib/useThemeColors';

const VERT = /* glsl */ `
  attribute vec3 aTarget; attribute float aSeed;
  uniform float uTime; uniform float uForm; uniform float uScatter; uniform float uScale; uniform float uSize;
  varying float vA; varying float vH;
  ${NOISE}
  void main(){
    float k = smoothstep(0.0, 1.0, clamp(uForm * 1.4 - aSeed * 0.4, 0.0, 1.0));          // staggered assemble
    vec3 cloud = position;                                                                // random start cloud
    vec3 p = mix(cloud, aTarget, k);
    float n = vnoise(vec2(aSeed * 40.0, uTime * 0.25));
    p += (vec3(vnoise(aTarget.xy * 3.0 + uTime * 0.2), n, vnoise(aTarget.zy * 3.0 - uTime * 0.2)) - 0.5) * (0.035 + uScatter * 0.5);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    float d = max(-mv.z, 0.1);
    gl_PointSize = clamp(uSize * (0.5 + aSeed * 0.8) * uScale / d, 1.0, 9.0);
    vA = 0.55 + 0.45 * aSeed; vH = clamp(aTarget.y / 2.4, 0.0, 1.0);
  }
`;
const FRAG = /* glsl */ `
  uniform vec3 uC2; uniform vec3 uC3; uniform float uOpacity;
  varying float vA; varying float vH;
  void main(){
    float r = length(gl_PointCoord - 0.5) * 2.0;
    float a = 1.0 - smoothstep(0.0, 1.0, r);
    a *= a;
    vec3 col = mix(uC2, uC3, vH);                      // theme gradient bottom -> top
    gl_FragColor = vec4(col, a * vA * uOpacity);
    ${FINISH}
  }
`;

/**
 * Turn ANY real model into a particle sculpture by sampling its surface. The silhouette is the real thing
 * (a person, a bottle, a car), rendered as theme-coloured points. A far better "person" than any primitive stack,
 * and cheap. Skinned characters are sampled in bind pose: pick a model whose rest pose is acceptable (A-pose/T-pose).
 */
export default function ParticleFigure({ subject, colors, count, additive, reduced }: { subject: Subject; colors: ThemeColors; count: number; additive: boolean; reduced: boolean }) {
  const gltf = useGLTF(subject.url as string) as unknown as { scene: Group };

  const geometry = useMemo(() => {
    const meshes: Mesh[] = [];
    gltf.scene.updateWorldMatrix(true, true);
    gltf.scene.traverse((o: Object3D) => { const m = o as Mesh; if (m.isMesh && m.geometry?.attributes?.position) meshes.push(m); });
    const tri = (m: Mesh) => (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3;
    const total = meshes.reduce((s, m) => s + tri(m), 0) || 1;

    const target = new Float32Array(count * 3);
    const start = new Float32Array(count * 3);
    const seed = new Float32Array(count);
    const v = new Vector3();
    let i = 0;
    for (const m of meshes) {
      const n = Math.max(1, Math.round((tri(m) / total) * count));
      const sampler = new MeshSurfaceSampler(m).build();
      for (let k = 0; k < n && i < count; k++, i++) {
        sampler.sample(v);
        v.applyMatrix4(m.matrixWorld);
        target.set([v.x, v.y, v.z], i * 3);
      }
    }
    for (; i < count; i++) target.set([target[0], target[1], target[2]], i * 3);   // rounding remainder

    // normalise to subject.height, feet on y=0, centred
    const box = new Box3(); for (let j = 0; j < count; j++) box.expandByPoint(v.set(target[j * 3], target[j * 3 + 1], target[j * 3 + 2]));
    const size = box.getSize(new Vector3()); const c = box.getCenter(new Vector3()); const s = subject.height / Math.max(size.y, 1e-3);
    for (let j = 0; j < count; j++) {
      target[j * 3] = (target[j * 3] - c.x) * s; target[j * 3 + 1] = (target[j * 3 + 1] - box.min.y) * s; target[j * 3 + 2] = (target[j * 3 + 2] - c.z) * s;
      start[j * 3] = (Math.random() - 0.5) * 9; start[j * 3 + 1] = Math.random() * 5; start[j * 3 + 2] = (Math.random() - 0.5) * 7;
      seed[j] = Math.random();
    }
    const g = new BufferGeometry();
    g.setAttribute('position', new BufferAttribute(start, 3));
    g.setAttribute('aTarget', new BufferAttribute(target, 3));
    g.setAttribute('aSeed', new BufferAttribute(seed, 1));
    return g;
  }, [gltf.scene, count, subject.height]);

  const material = useMemo(
    () => new ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, toneMapped: false,
      uniforms: { uTime: { value: 0 }, uForm: { value: reduced ? 1 : 0 }, uScatter: { value: 0 }, uScale: { value: 900 }, uSize: { value: 0.05 }, uC2: { value: colors.c2 }, uC3: { value: colors.c3 }, uOpacity: { value: 0.95 } },
    }),
    [colors], // eslint-disable-line react-hooks/exhaustive-deps
  );
  useEffect(() => { material.blending = additive ? AdditiveBlending : NormalBlending; material.needsUpdate = true; }, [additive, material]);

  useFrame(({ clock, size, gl, camera }, dt) => {
    const u = material.uniforms;
    const fov = ((camera as { fov?: number }).fov ?? 50) * (Math.PI / 180);
    u.uScale.value = (size.height * gl.getPixelRatio() * 0.5) / Math.tan(fov / 2);
    u.uTime.value = reduced ? 0 : clock.elapsedTime;
    u.uForm.value = Math.min(1, u.uForm.value + dt * 0.45);                            // assemble over ~2.5 s
    u.uScatter.value += (Math.min(motion.velocity, 2) * 0.35 - u.uScatter.value) * 0.1;   // scrolling disturbs the figure
  });
  useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);
  return <points geometry={geometry} material={material} frustumCulled={false} renderOrder={6} />;
}
