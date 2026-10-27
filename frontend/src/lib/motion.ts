/**
 * Non-reactive motion state. Written by useScrollMotion, READ inside useFrame.
 * Never put per-frame values in React state or a zustand `set` - that re-renders the tree.
 */
export const motion = {
  progress: 0,   // 0..1 page scroll progress
  velocity: 0,   // smoothed |scroll speed| ~0..3, decays to 0 when scrolling stops
  mx: 0,         // mouse -1..1
  my: 0,
};
