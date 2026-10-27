#!/usr/bin/env node
/**
 * Inspect a .glb/.gltf and print what matters for a web build, plus concrete recommendations.
 *   npm i -D @gltf-transform/core @gltf-transform/functions @gltf-transform/extensions
 *   node scripts/model_report.mjs public/models/hero.glb
 * Reports: size, triangles, meshes/materials/textures (with resolution), skins/joints, animations (name, seconds),
 * morph targets (facial expressions), bounding box + suggested scale, compression extensions, and warnings.
 */
import fs from 'node:fs';
import { NodeIO } from '@gltf-transform/core';
import { getBounds } from '@gltf-transform/functions';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';

const file = process.argv[2];
if (!file) { console.error('usage: model_report.mjs <file.glb|gltf>'); process.exit(2); }

const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
let doc;
try { doc = await io.read(file); } catch (e) {
  // Draco/Meshopt-compressed files need decoders; report that instead of failing silently
  console.error('Could not read file:', e.message); console.error('If it is Draco/Meshopt compressed: npm i draco3dgltf meshoptimizer and register the decoders.'); process.exit(1);
}
const root = doc.getRoot();
const kb = (n) => (n / 1024).toFixed(0) + ' KB';
const size = fs.statSync(file).size;

let tris = 0, verts = 0;
for (const mesh of root.listMeshes()) for (const prim of mesh.listPrimitives()) {
  const pos = prim.getAttribute('POSITION'); const idx = prim.getIndices();
  verts += pos ? pos.getCount() : 0;
  tris += idx ? idx.getCount() / 3 : pos ? pos.getCount() / 3 : 0;
}
const scene = root.getDefaultScene() ?? root.listScenes()[0];
const b = getBounds(scene);
const dim = b.max.map((v, i) => v - b.min[i]);
const tallest = Math.max(...dim);

const textures = root.listTextures().map((t) => {
  const [w, h] = t.getSize() ?? [0, 0];
  return { name: t.getName() || t.getURI() || '(unnamed)', mime: t.getMimeType(), w, h, bytes: t.getImage()?.byteLength ?? 0 };
});
const skins = root.listSkins();
const anims = root.listAnimations().map((a) => {
  let end = 0; for (const s of a.listSamplers()) { const t = s.getInput(); if (t) end = Math.max(end, t.getMax([])[0]); }
  return { name: a.getName() || '(unnamed)', sec: end };
});
let morphs = new Set();
for (const mesh of root.listMeshes()) for (const p of mesh.listPrimitives()) for (const t of p.listTargets()) morphs.add(t.getName());
const morphNames = root.listMeshes().flatMap((m) => m.getExtras()?.targetNames ?? []);
const textureName = (texture) => texture ? (texture.getName() || texture.getURI() || 'embedded texture') : 'none';
const materialLines = root.listMaterials().map((m) => {
  const color = m.getBaseColorFactor().map((v) => v.toFixed(2)).join(',');
  return `   - ${m.getName() || '(unnamed)'}  base=[${color}] metal=${m.getMetallicFactor().toFixed(2)} rough=${m.getRoughnessFactor().toFixed(2)} baseMap=${textureName(m.getBaseColorTexture())} normal=${textureName(m.getNormalTexture())} MR=${textureName(m.getMetallicRoughnessTexture())}`;
});
const rootNodes = scene.listChildren().map((n) => `${n.getName() || '(unnamed)'} @ [${n.getTranslation().map((v) => v.toFixed(2)).join(', ')}]`);

console.log(`FILE        ${file}  (${kb(size)})`);
console.log(`GEOMETRY    ${root.listMeshes().length} meshes, ${tris.toLocaleString()} triangles, ${verts.toLocaleString()} vertices`);
console.log(`MATERIALS   ${root.listMaterials().length}: ${root.listMaterials().map((m) => m.getName() || '(unnamed)').slice(0, 8).join(', ')}`);
if (materialLines.length) console.log(`PBR MAPS\n${materialLines.join('\n')}`);
console.log(`TEXTURES    ${textures.length}${textures.length ? '\n' + textures.map((t) => `   - ${t.name} ${t.w}x${t.h} ${t.mime} ${kb(t.bytes)}`).join('\n') : ''}`);
console.log(`SKINS       ${skins.length}${skins[0] ? ` (joints: ${skins.map((s) => s.listJoints().length).join(', ')})` : ''}`);
console.log(`ANIMATIONS  ${anims.length}${anims.length ? '\n' + anims.map((a) => `   - ${a.name}  ${a.sec.toFixed(2)} s`).join('\n') : ''}`);
console.log(`MORPHS      ${morphs.size}${morphNames.length ? ' (' + morphNames.slice(0, 12).join(', ') + ')' : ''}`);
console.log(`EXTENSIONS  ${root.listExtensionsUsed().map((e) => e.extensionName).join(', ') || 'none'}`);
console.log(`BOUNDS      min [${b.min.map((v) => v.toFixed(2))}]  max [${b.max.map((v) => v.toFixed(2))}]  size [${dim.map((v) => v.toFixed(2))}]`);
console.log(`FIT         scale to a 2-unit-tall stage with scale=${(2 / tallest).toFixed(4)}; centre = [${b.min.map((v, i) => ((v + b.max[i]) / 2).toFixed(2))}]`);
console.log(`ROOT NODES  ${rootNodes.join(' | ') || '(none)'}  (check pivot and front direction in the preview sheet)`);

const warn = [];
if (size > 2.5 * 1024 * 1024) warn.push('File > 2.5 MB: run `gltf-transform optimize in.glb out.glb --compress meshopt --texture-compress webp` (or draco) and downscale textures.');
if (tris > 150_000) warn.push(`${tris.toLocaleString()} triangles is heavy for a background hero (aim < 100k); decimate (gltf-transform simplify).`);
for (const t of textures) if (Math.max(t.w, t.h) > 2048) warn.push(`Texture ${t.name} is ${t.w}x${t.h}: resize to <= 2048 (1024 for secondary maps).`);
if (textures.some((t) => t.mime === 'image/png' && t.bytes > 400 * 1024)) warn.push('Large PNG textures: convert to WebP/KTX2 (--texture-compress webp).');
if (root.listMaterials().length > 8) warn.push('Many materials = many draw calls: merge/atlas where possible.');
if (skins.length && !anims.length) warn.push('Rigged model with no animation clips: it will sit in bind pose (T-pose). Add clips (Mixamo/Blender) or pose bones in code.');
if (!skins.length && /human|person|character|avatar/i.test(file)) warn.push('Named like a character but has no skeleton.');
if (Math.max(...dim) > 50 || Math.max(...dim) < 0.05) warn.push('Unusual scale: auto-fit with <Bounds>/the Model component or apply the suggested scale.');
console.log('\n' + (warn.length ? 'WARNINGS\n - ' + warn.join('\n - ') : 'No warnings.'));
