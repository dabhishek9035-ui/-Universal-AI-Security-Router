#!/usr/bin/env node
/** Check that each shipped GLB/glTF has a concrete source and licence record. */
import fs from 'node:fs';
import path from 'node:path';

const directory = path.resolve(process.argv[2] ?? 'public/models');
if (!fs.existsSync(directory) || !fs.statSync(directory).isDirectory()) {
  console.error(`Asset directory not found: ${directory}`);
  process.exit(2);
}

const models = fs.readdirSync(directory).filter((name) => /\.(glb|gltf)$/i.test(name));
if (!models.length) {
  console.log(`No GLB/glTF assets found in ${directory}.`);
  process.exit(0);
}

const creditsPath = path.join(directory, 'CREDITS.md');
const credits = fs.existsSync(creditsPath) ? fs.readFileSync(creditsPath, 'utf8') : '';
const lines = credits.split(/\r?\n/);
let failed = false;

for (const model of models) {
  const idx = lines.findIndex((line) => line.toLowerCase().includes(model.toLowerCase()));
  if (idx < 0) {
    console.error(`MISSING  ${model}: add an entry to ${creditsPath}`);
    failed = true;
    continue;
  }
  const record = lines.slice(idx, idx + 3).join(' ');
  const placeholder = /\b(todo|tbd|unknown|unspecified)\b/i.test(record);
  const hasLicense = /\b(CC0|CC[- ]?BY|public domain|proprietary|permission|license|licence)\b/i.test(record);
  const hasSource = /https?:\/\/|\bsource\s*:/i.test(record);
  if (placeholder || !hasLicense || !hasSource) {
    console.error(`INCOMPLETE  ${model}: entry needs a non-placeholder source URL and licence`);
    failed = true;
  } else {
    console.log(`RECORDED  ${model}: source and licence fields are present; verify the terms manually.`);
  }
}

if (failed) process.exitCode = 1;
