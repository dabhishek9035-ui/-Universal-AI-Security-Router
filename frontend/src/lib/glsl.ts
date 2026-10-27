/** Reusable GLSL chunks. Concatenate with template literals: `${NOISE}`. */

/** Colour-space + tone-mapping epilogue. Required in every ShaderMaterial that outputs colour:
 *  THREE.Color uniforms are LINEAR, so the shader must convert on output. */
export const FINISH = /* glsl */ `
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
`;

export const NOISE = /* glsl */ `
  float hash21(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
  float hash31(vec3 p){ p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419)); p *= 50.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
  float vnoise(vec2 p){
    vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash21(i), hash21(i + vec2(1.0, 0.0)), f.x), mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), f.x), f.y);
  }
  float vnoise3(vec3 p){
    vec3 i = floor(p); vec3 f = fract(p); f = f * f * (3.0 - 2.0 * f);
    float a = hash31(i), b = hash31(i + vec3(1.0, 0.0, 0.0)), c = hash31(i + vec3(0.0, 1.0, 0.0)), d = hash31(i + vec3(1.0, 1.0, 0.0));
    float e = hash31(i + vec3(0.0, 0.0, 1.0)), g = hash31(i + vec3(1.0, 0.0, 1.0)), h = hash31(i + vec3(0.0, 1.0, 1.0)), k = hash31(i + vec3(1.0, 1.0, 1.0));
    return mix(mix(mix(a, b, f.x), mix(c, d, f.x), f.y), mix(mix(e, g, f.x), mix(h, k, f.x), f.y), f.z);
  }
  float fbm(vec2 p){ float s = 0.0; float a = 0.5; for (int i = 0; i < 5; i++) { s += a * vnoise(p); p = p * 2.02 + vec2(17.3, 9.1); a *= 0.5; } return s; }
`;
