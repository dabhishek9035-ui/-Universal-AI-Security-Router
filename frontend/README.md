# Immersive site starter

```bash
npm install && npm run dev        # http://localhost:3000
npm run typecheck && npm run check:shaders && npm run audit:assets
npm run audit:assets              # verify every model has a source + licence record
```

**The subject** (the recognisable thing the site is about) lives in `src/lib/subject.ts` and `public/models/`.
The shipped `hero.glb` is a CC0 demo robot: **replace it** with the real model (`node scripts/model_report.mjs public/models/hero.glb`
to inspect clips/size; optimise with `npx @gltf-transform/cli optimize in.glb public/models/hero.glb --compress meshopt --texture-compress webp --texture-size 1024`).
`mode: 'particles'` renders the same model as a theme-coloured particle sculpture. `url: null` shows the abstract orb.

**Interactive object study:** open `/viewer` to see a complete model-inspection page. It uses the same persistent canvas, a neutral studio, bounded orbit controls, camera presets, and a world-space HTML hotspot mirrored by an accessible details panel. The included robot is a mechanics demo; replace it for the actual subject and adjust the hotspot in `src/components/scene/InspectionScene.tsx`. For client work, match the studio reflections, background, and contact shadow to the real asset and intended setting.

**Visual review captures:** while the dev server is running, install Playwright once (`npm install --save-dev playwright && npx playwright install chromium`) and run `npm run capture:review`. Desktop and mobile screenshots of the landing page and the object viewer are written to `artifacts/visual-review/`. Inspect those images manually; capture output is evidence for review, not an automatic visual quality verdict.

**Themes:** `src/lib/themes.ts` (one object per theme: CSS variables + shader colours). **Scene layers:** `src/components/scene/`.
Lighting/environment for models: `Stage.tsx` (procedural, no HDRI download). Tone mapping: Neutral (see `SceneCanvas.tsx`, `Post.tsx`).
