import { create } from 'zustand';
import { DEFAULT_THEME } from '@/lib/themes';

export type Quality = 'high' | 'medium' | 'low';
export type ViewerView = 'three-quarter' | 'front' | 'side';

type State = {
  themeId: string;
  quality: Quality;
  reducedMotion: boolean;
  viewerView: ViewerView;
  viewerHotspot: string | null;
  webglAvailable: boolean | null;
  // domain state (low-frequency): 0..1 share of requests the gateway blocked,
  // mirrored in the DOM as the "blocked" KPI — the scene only eases toward it
  threatLevel: number;
  setTheme: (id: string) => void;
  setQuality: (q: Quality) => void;
  setReducedMotion: (v: boolean) => void;
  setViewerView: (view: ViewerView) => void;
  setViewerHotspot: (id: string | null) => void;
  setWebglAvailable: (available: boolean) => void;
  setThreatLevel: (v: number) => void;
};

export const useStore = create<State>((set) => ({
  themeId: DEFAULT_THEME,
  quality: 'high',
  reducedMotion: false,
  viewerView: 'three-quarter',
  viewerHotspot: null,
  webglAvailable: null,
  threatLevel: 0,
  setTheme: (themeId) => {
    set({ themeId });
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = themeId;
      try { localStorage.setItem('theme', themeId); } catch {}
    }
  },
  setQuality: (quality) => set({ quality }),
  setReducedMotion: (reducedMotion) => set({ reducedMotion }),
  setViewerView: (viewerView) => set({ viewerView }),
  setViewerHotspot: (viewerHotspot) => set({ viewerHotspot }),
  setWebglAvailable: (webglAvailable) => set({ webglAvailable }),
  setThreatLevel: (threatLevel) => set({ threatLevel: Math.min(1, Math.max(0, threatLevel)) }),
}));
