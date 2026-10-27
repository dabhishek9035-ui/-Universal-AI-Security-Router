/**
 * ONE source of truth for look & feel.
 *  - `ui`    -> CSS variables (emitted as [data-theme="id"] rules, so SSR has no flash)
 *  - `scene` -> shader uniforms / blending / post-processing (read by the 3D scene)
 * Add a theme = add one object here. Nothing else changes.
 */
export type Theme = {
  id: string;
  label: string;
  mode: 'dark' | 'light';
  ui: {
    bg: string; panel: string; line: string;
    text: string; muted: string;
    accent: string; accent2: string; onAccent: string;
  };
  scene: {
    bg: string;          // clear / fog colour - match the page background
    c1: string;          // deep colour
    c2: string;          // mid colour
    c3: string;          // highlight / rim
    particle: string;
    additive: boolean;   // false on LIGHT themes (additive blending vanishes on white)
    bloom: number;       // 0 = off
    warp: number;        // 0..1 how turbulent the backdrop is
  };
};

export const THEMES: Record<string, Theme> = {
  abyss: {
    id: 'abyss', label: 'Abyss', mode: 'dark',
    ui: { bg: '#000000', panel: 'rgba(5,15,22,.62)', line: 'rgba(133,205,220,.16)', text: '#eaf6f7', muted: '#8aa1a8', accent: '#5de1ee', accent2: '#85e4ec', onAccent: '#021419' },
    scene: { bg: '#000000', c1: '#02121a', c2: '#0b5a6b', c3: '#7ff3ff', particle: '#7fe9ef', additive: true, bloom: 0.55, warp: 0.55 },
  },
  nebula: {
    id: 'nebula', label: 'Nebula', mode: 'dark',
    ui: { bg: '#05010d', panel: 'rgba(16,8,32,.62)', line: 'rgba(190,150,255,.18)', text: '#f3ecff', muted: '#a597c4', accent: '#b794ff', accent2: '#ff7ad9', onAccent: '#12062a' },
    scene: { bg: '#05010d', c1: '#12052e', c2: '#5b2bb0', c3: '#ff7ad9', particle: '#d9c4ff', additive: true, bloom: 0.8, warp: 0.8 },
  },
  aurora: {
    id: 'aurora', label: 'Aurora', mode: 'dark',
    ui: { bg: '#020a0f', panel: 'rgba(4,20,26,.62)', line: 'rgba(120,255,210,.16)', text: '#e9fff7', muted: '#86a9a0', accent: '#6cffc4', accent2: '#6aa8ff', onAccent: '#02140e' },
    scene: { bg: '#020a0f', c1: '#031a1f', c2: '#0f7a6a', c3: '#8affd8', particle: '#b8fff0', additive: true, bloom: 0.7, warp: 0.65 },
  },
  ember: {
    id: 'ember', label: 'Ember', mode: 'dark',
    ui: { bg: '#0a0503', panel: 'rgba(28,12,6,.62)', line: 'rgba(255,170,110,.18)', text: '#fff1e8', muted: '#b39484', accent: '#ff9a52', accent2: '#ff4d6d', onAccent: '#1f0a02' },
    scene: { bg: '#0a0503', c1: '#220a05', c2: '#b0361a', c3: '#ffc27a', particle: '#ffb98a', additive: true, bloom: 0.75, warp: 0.7 },
  },
  neon: {
    id: 'neon', label: 'Neon', mode: 'dark',
    ui: { bg: '#07000f', panel: 'rgba(14,4,30,.66)', line: 'rgba(0,240,255,.22)', text: '#f2fbff', muted: '#9a8fc0', accent: '#00f0ff', accent2: '#ff2bd6', onAccent: '#00131a' },
    scene: { bg: '#07000f', c1: '#12002e', c2: '#6a1bd1', c3: '#00f0ff', particle: '#ff6fe8', additive: true, bloom: 1.0, warp: 0.5 },
  },
  verdant: {
    id: 'verdant', label: 'Verdant', mode: 'dark',
    ui: { bg: '#030905', panel: 'rgba(6,22,12,.62)', line: 'rgba(170,240,150,.16)', text: '#effaea', muted: '#8fa88f', accent: '#9be564', accent2: '#3fc79a', onAccent: '#071a04' },
    scene: { bg: '#030905', c1: '#04150a', c2: '#1c6b3a', c3: '#c8ff8a', particle: '#d6ffb0', additive: true, bloom: 0.5, warp: 0.6 },
  },
  daylight: {
    id: 'daylight', label: 'Daylight', mode: 'light',
    ui: { bg: '#f4f8fb', panel: 'rgba(255,255,255,.72)', line: 'rgba(12,26,36,.12)', text: '#0c1a24', muted: '#51666f', accent: '#1b6cff', accent2: '#00a3a3', onAccent: '#ffffff' },
    scene: { bg: '#f4f8fb', c1: '#dbe9f6', c2: '#8fbaf0', c3: '#ffffff', particle: '#4a86e8', additive: false, bloom: 0, warp: 0.45 },
  },
};

export const DEFAULT_THEME = 'abyss';
export const THEME_IDS = Object.keys(THEMES);
export const getTheme = (id: string): Theme => THEMES[id] ?? THEMES[DEFAULT_THEME];

/** CSS for every theme: `[data-theme="abyss"]{--bg:#000;...}` - render once in <head>. */
export function themesCss(): string {
  return Object.values(THEMES)
    .map((t) => {
      const v = Object.entries(t.ui).map(([k, val]) => `--${k.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase())}:${val}`).join(';');
      return `[data-theme="${t.id}"]{${v};color-scheme:${t.mode}}`;
    })
    .join('\n');
}

/** Inline script (runs before first paint) that restores the saved theme. */
export const themeBootScript =
  `try{var t=localStorage.getItem('theme');var ok=${JSON.stringify(THEME_IDS)};document.documentElement.dataset.theme=t&&ok.indexOf(t)>-1?t:${JSON.stringify(DEFAULT_THEME)}}catch(e){document.documentElement.dataset.theme=${JSON.stringify(DEFAULT_THEME)}}`;
