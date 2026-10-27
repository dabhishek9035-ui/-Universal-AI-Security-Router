/**
 * THE SUBJECT: the recognisable thing this site is about (a product, a character, a person, a vehicle...).
 * Recognisable subjects are REAL ASSETS (glTF), never stacks of boxes and spheres.
 * Set `url: null` to fall back to the abstract hero orb (abstract/brand sites only).
 */
export type Subject = {
  url: string | null;          // /public path to a .glb (meshopt/draco compressed is fine)
  height: number;              // world units tall after auto-fit
  clip?: string;               // animation to loop (falls back to "Idle", then the first clip)
  scrub?: string;              // optional clip scrubbed by scroll progress instead of playing in time
  rotationY: number;           // radians; turn the model to face the camera
  mode: 'model' | 'particles'; // 'particles' = the surface sampled into theme-coloured points
};

export const SUBJECT: Subject = {
  url: null,
  height: 2.3,
  clip: 'Idle',
  rotationY: 0,
  mode: 'model',
};
