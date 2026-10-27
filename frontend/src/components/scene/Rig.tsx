'use client';
import { useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Vector3 } from 'three';
import { motion } from '@/lib/motion';

/** Camera follows scroll + mouse with exponential damping (frame-rate independent). */
export default function Rig({ reduced }: { reduced: boolean }) {
  const look = useMemo(() => new Vector3(), []);
  useFrame(({ camera }, dt) => {
    const k = 1 - Math.exp(-Math.min(dt, 0.05) * 3);
    const m = reduced ? 0 : 1;
    camera.position.x += (motion.mx * 0.5 * m - camera.position.x) * k;
    camera.position.y += (-motion.my * 0.3 * m - motion.progress * 1.6 - camera.position.y) * k;
    camera.position.z += (6 - motion.progress * 1.2 - camera.position.z) * k;
    look.set(0, -motion.progress * 1.2, 0);
    camera.lookAt(look);
  });
  return null;
}
