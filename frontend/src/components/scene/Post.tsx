'use client';
import { Bloom, EffectComposer, ToneMapping, Vignette } from '@react-three/postprocessing';
import { ToneMappingMode } from 'postprocessing';
import { getTheme } from '@/lib/themes';
import { useStore } from '@/state/store';

/**
 * Bloom + vignette on the high tier only, and only for themes that want glow (not light themes).
 * When a composer is active the renderer's tone mapping is bypassed, so tone-map as the LAST effect
 * (Neutral keeps brand colours and PBR base colours faithful; ACES_FILMIC is punchier/darker).
 */
export default function Post() {
  const quality = useStore((s) => s.quality);
  const bloom = getTheme(useStore((s) => s.themeId)).scene.bloom;
  if (quality !== 'high' || bloom <= 0) return null;
  return (
    <EffectComposer multisampling={0}>
      <Bloom intensity={bloom} luminanceThreshold={0.6} luminanceSmoothing={0.3} mipmapBlur />
      <Vignette offset={0.2} darkness={0.6} />
      <ToneMapping mode={ToneMappingMode.NEUTRAL} />
    </EffectComposer>
  );
}
