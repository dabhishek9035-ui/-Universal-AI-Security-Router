#!/usr/bin/env node
/**
 * Validate every GLSL template string in a TS/JS project WITHOUT opening a browser.
 *   node scripts/check_shaders.mjs src            (files or directories)
 *
 * It finds `const NAME = \`...\`` strings, resolves ${OTHER_CONST} interpolation (across files),
 * pairs *_VERT / *_FRAG strings, wraps them the way three.js wraps a ShaderMaterial (GLSL ES 3.00),
 * and compiles them with `glslangValidator` (apt install glslang-tools / brew install glslang).
 * Also runs heuristics for the bugs that are *undefined behaviour* in GLSL and bite in production:
 *   - smoothstep(a, b, x) with a >= b            (undefined; works on some GPUs, breaks on others)
 *   - missing <colorspace_fragment>               (colours look washed out / too dark)
 * Exit code 1 if anything fails.
 */
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const roots = process.argv.slice(2);
if (!roots.length) { console.error('usage: check_shaders.mjs <file|dir> [...]'); process.exit(2); }

const exts = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.md']);
const skip = new Set(['node_modules', '.next', '.git', 'dist']);
const files = [];
function walk(p) {
  if (!fs.existsSync(p)) return;
  if (fs.statSync(p).isDirectory()) { for (const f of fs.readdirSync(p)) if (!skip.has(f)) walk(path.join(p, f)); }
  else if (exts.has(path.extname(p))) files.push(p);
}
roots.forEach(walk);

// pass 1: collect all template-literal consts, scoped per file (many files reuse names like VERT/FRAG)
const RAW = new Map();           // `${file}::${name}` -> text
const BY_NAME = new Map();       // name -> [file, ...]  (used to resolve imported chunks like NOISE)
const re = /(?:export\s+)?const\s+([A-Za-z_]\w*)\s*(?::\s*string)?\s*=\s*(?:\/\*\s*glsl\s*\*\/\s*)?`([\s\S]*?)`/g;
for (const f of files) {
  const src = fs.readFileSync(f, 'utf8');
  let m; while ((m = re.exec(src))) {
    RAW.set(`${f}::${m[1]}`, m[2]);
    BY_NAME.set(m[1], [...(BY_NAME.get(m[1]) ?? []), f]);
  }
}
const memo = new Map();
function resolve(file, name, stack = []) {
  const key = `${file}::${name}`;
  if (memo.has(key)) return memo.get(key);
  if (stack.includes(key) || !RAW.has(key)) return null;
  let ok = true;
  const out = RAW.get(key).replace(/\$\{\s*([A-Za-z_]\w*)\s*\}/g, (_, id) => {
    const home = RAW.has(`${file}::${id}`) ? file : BY_NAME.get(id)?.[0];
    const r = home ? resolve(home, id, [...stack, key]) : null;
    if (r == null) { ok = false; return ''; }
    return r;
  });
  const v = ok ? out : null; memo.set(key, v); return v;
}

const isShader = (name, text) => /(VERT|FRAG|VERTEX|FRAGMENT)$/i.test(name) && /void\s+main\s*\(/.test(text ?? '');
const kind = (name, text) => (/gl_Position/.test(text) || /VERT/i.test(name) ? 'vert' : 'frag');

const vPre = `#version 300 es
precision highp float; precision highp int;
uniform mat4 modelMatrix; uniform mat4 modelViewMatrix; uniform mat4 projectionMatrix; uniform mat4 viewMatrix; uniform mat3 normalMatrix; uniform vec3 cameraPosition;
in vec3 position; in vec3 normal; in vec2 uv; in mat4 instanceMatrix; in vec3 color;
#define attribute in
#define varying out
#define texture2D texture
`;
const fPre = `#version 300 es
precision highp float; precision highp int;
uniform mat4 viewMatrix; uniform vec3 cameraPosition;
out vec4 pc_fragColor;
#define gl_FragColor pc_fragColor
#define varying in
#define texture2D texture
`;
const strip = (s) => s.replace(/#include\s*<[^>]+>/g, '');

const have = spawnSync('glslangValidator', ['--version']).status === 0;
if (!have) console.warn('! glslangValidator not found - skipping compile, heuristics only (apt install glslang-tools)');

let bad = 0, count = 0;
for (const key of RAW.keys()) {
  const [file, name] = key.split('::');
  const text = resolve(file, name);
  if (!isShader(name, text)) continue;
  count++;
  const k = kind(name, text);
  const problems = [];

  for (const m of text.matchAll(/smoothstep\(\s*(-?\d*\.?\d+)\s*,\s*(-?\d*\.?\d+)\s*,/g)) {
    if (parseFloat(m[1]) >= parseFloat(m[2])) problems.push(`smoothstep(${m[1]}, ${m[2]}, ...) has edge0 >= edge1 (undefined) - use 1.0 - smoothstep(lo, hi, x)`);
  }
  if (k === 'frag' && /gl_FragColor\s*=/.test(text) && !/colorspace_fragment/.test(text)) problems.push('no #include <colorspace_fragment> (output will not be sRGB-encoded) - ignore for post-process passes / premultiplied overlays on purpose');

  if (have) {
    const tmp = path.join(process.env.TMPDIR || '/tmp', `shader_${count}_${name}.${k}`);
    fs.writeFileSync(tmp, (k === 'vert' ? vPre : fPre) + strip(text));
    const r = spawnSync('glslangValidator', [tmp], { encoding: 'utf8' });
    if (r.status !== 0) problems.unshift('COMPILE ERROR:\n' + (r.stdout || r.stderr).split('\n').slice(0, 8).join('\n'));
    fs.rmSync(tmp, { force: true });
  }
  const hard = problems.some((p) => p.startsWith('COMPILE') || p.startsWith('smoothstep'));
  if (hard) bad++;
  console.log(`${hard ? 'FAIL' : problems.length ? 'warn' : 'ok  '}  ${name}  (${path.relative('.', file)})`);
  for (const p of problems) console.log('      ' + p.replace(/\n/g, '\n      '));
}
console.log(`\n${count} shader string(s), ${bad} failing`);
process.exit(bad ? 1 : 0);
