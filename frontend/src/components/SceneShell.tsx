'use client';
import dynamic from 'next/dynamic';
import { useEffect } from 'react';
import { DEFAULT_THEME, THEME_IDS } from '@/lib/themes';
import { useStore } from '@/state/store';

// three.js touches `window`/WebGL: load it on the client only, after the page has painted.
const SceneCanvas = dynamic(() => import('./SceneCanvas'), { ssr: false });

export default function SceneShell() {
  useEffect(() => {
    // the inline boot script already set data-theme before paint; mirror it into the store
    const id = document.documentElement.dataset.theme ?? DEFAULT_THEME;
    useStore.setState({ themeId: THEME_IDS.includes(id) ? id : DEFAULT_THEME });
  }, []);
  return <SceneCanvas />;
}
