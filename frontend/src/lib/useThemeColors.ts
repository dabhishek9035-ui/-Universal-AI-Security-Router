'use client';
import { useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Color } from 'three';
import type { Theme } from './themes';

export type ThemeColors = Record<'bg' | 'c1' | 'c2' | 'c3' | 'particle', Color>;
const KEYS = ['bg', 'c1', 'c2', 'c3', 'particle'] as const;
const make = (t: Theme): ThemeColors => ({ bg: new Color(t.scene.bg), c1: new Color(t.scene.c1), c2: new Color(t.scene.c2), c3: new Color(t.scene.c3), particle: new Color(t.scene.particle) });

/**
 * Returns Color objects that ease toward the active theme every frame.
 * Pass these objects straight into shader uniforms (`{ value: colors.c1 }`): mutating them updates the shader,
 * so switching themes cross-fades the whole scene with zero React re-renders.
 */
export function useThemeColors(theme: Theme): ThemeColors {
  const current = useMemo(() => make(theme), []); // eslint-disable-line react-hooks/exhaustive-deps
  const target = useMemo(() => make(theme), [theme]);
  useFrame((_, dt) => {
    const k = 1 - Math.exp(-Math.min(dt, 0.05) * 4);
    for (const key of KEYS) current[key].lerp(target[key], k);
  });
  return current;
}
