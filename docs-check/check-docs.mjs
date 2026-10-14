#!/usr/bin/env node
// Documentation governance check for the orderflow-engine-* workspace. Rules: orderflow-engine-docs/governance/documentation-rules.md.
// Run from the workspace root, with the sibling repositories present: node orderflow-engine-tools/docs-check/check-docs.mjs
// Configuration: governance/docs-governance.json. No dependencies; Node 18+.
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { dirname, join, posix, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { parseHandoff, renderProgress } from '../progress/progress.mjs';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const workspace = resolve(scriptDir, '..', '..');
const docsRoot = join(workspace, 'orderflow-engine-docs');
const config = JSON.parse(readFileSync(join(docsRoot, 'governance', 'docs-governance.json'), 'utf8'));

const errors = [];
const fail = (file, message) => errors.push(`${file}: ${message}`);
const read = (rel) => readFileSync(join(workspace, rel), 'utf8').replace(/\r\n/g, '\n');
const exists = (rel) => existsSync(join(workspace, rel));
const toWorkspace = (abs) => abs.slice(workspace.length + 1).replace(/\\/g, '/');

function globToRegExp(glob) {
  let re = '';
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === '*' && glob[i + 1] === '*') {
      if (glob[i + 2] === '/') { re += '(?:.*/)?'; i += 2; } else { re += '.*'; i += 1; }
    } else if (c === '*') {
      re += '[^/]*';
    } else if (c === '?') {
      re += '[^/]';
    } else if (c === '[') {
      const end = glob.indexOf(']', i);
      re += glob.slice(i, end + 1);
      i = end;
    } else {
      re += c.replace(/[.+^${}()|\\]/g, '\\$&');
    }
  }
  return new RegExp(`^${re}$`);
}
const matcher = (globs = []) => {
  const res = globs.map(globToRegExp);
  return (path) => res.some((re) => re.test(path));
};

function walk(relDir, out) {
  for (const entry of readdirSync(join(workspace, relDir), { withFileTypes: true })) {
    const rel = posix.join(relDir, entry.name);
    if (entry.isDirectory()) {
      if (!config.excludeDirs.includes(entry.name)) walk(rel, out);
    } else {
      out.push(rel);
    }
  }
  return out;
}

const files = config.scanRoots.filter(exists).flatMap((root) => walk(root, []));
const markdown = files.filter((f) => f.endsWith('.md'));

// Strips fenced code blocks and inline code so examples are not parsed as content.
const prose = (text) => text.replace(/```[\s\S]*?```/g, '').replace(/`[^`\n]*`/g, '');
const headings = (text) => prose(text).split('\n').filter((l) => /^#{1,6}\s/.test(l)).map((l) => l.replace(/^#+\s+/, '').trim());

function frontMatter(text) {
  if (!text.startsWith('---\n')) return null;
  const end = text.indexOf('\n---', 4);
  if (end < 0) return null;
  const data = {};
  for (const line of text.slice(4, end).split('\n')) {
    const m = line.match(/^([\w-]+):\s*(.*)$/);
    if (m) data[m[1]] = m[2].trim();
  }
  return data;
}

function links(text) {
  const found = [];
  for (const m of prose(text).matchAll(/\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)) found.push(m[1]);
  return found;
}

const resolveLink = (fromFile, target) => {
  const clean = decodeURI(target.split('#')[0].split('?')[0]);
  return clean ? posix.normalize(posix.join(posix.dirname(fromFile), clean)) : null;
};
const isExternal = (t) => /^(https?:|mailto:|#)/.test(t);

const pairOf = (file) => (file.endsWith('.es.md') ? `${file.slice(0, -6)}.md` : `${file.slice(0, -3)}.es.md`);

// 1. Location
const isAllowed = matcher(config.allowed);
for (const file of markdown) if (!isAllowed(file)) fail(file, 'Markdown file outside the allowed locations');

// 2. Index membership
const indexed = new Set(config.indexes);
for (const index of config.indexes) {
  if (!exists(index)) { fail(index, 'document map is missing'); continue; }
  const text = read(index);
  for (const target of links(text)) {
    if (!isExternal(target)) indexed.add(resolveLink(index, target));
  }
  // Documents of other repositories are cited by workspace path, without a link (see rule 5).
  for (const m of text.matchAll(/`((?:orderflow-engine-[a-z]+)\/[^`\s]+\.md)`/g)) {
    if (!exists(m[1])) fail(index, `cited document ${m[1]} does not exist`);
    indexed.add(m[1]);
  }
}
for (const file of markdown) if (!indexed.has(file)) fail(file, 'not listed in the document map');

// 3. Language pairs
const isBilingual = matcher(config.bilingual);
const checkedPairs = new Set();
for (const file of markdown.filter(isBilingual)) {
  const pair = pairOf(file);
  const key = [file, pair].sort().join('|');
  if (checkedPairs.has(key)) continue;
  checkedPairs.add(key);
  if (!exists(pair)) { fail(file, `missing language pair ${pair}`); continue; }
  const a = headings(read(file)).length;
  const b = headings(read(pair)).length;
  if (a !== b) fail(file, `heading count ${a} differs from ${pair} (${b})`);
}

// 4. Front matter
const needsFrontMatter = matcher(config.frontMatter.required);
const isExempt = matcher(config.frontMatter.exempt);
for (const file of markdown.filter((f) => needsFrontMatter(f) && !isExempt(f))) {
  const fm = frontMatter(read(file));
  if (!fm) { fail(file, 'missing front matter'); continue; }
  for (const key of config.frontMatter.keys) if (!fm[key]) fail(file, `front matter key "${key}" is missing`);
  if (fm.status && !config.frontMatter.status.includes(fm.status)) fail(file, `invalid status "${fm.status}"`);
  const expectedLang = file.endsWith('.es.md') ? 'es' : 'en';
  if (fm.lang && fm.lang !== expectedLang) fail(file, `lang "${fm.lang}" does not match the file name (${expectedLang})`);
  if (fm.status === 'template') continue;
  if (fm['last-reviewed'] && !/^\d{4}-\d{2}-\d{2}$/.test(fm['last-reviewed'])) fail(file, 'last-reviewed must be YYYY-MM-DD');
  if (fm.pair && fm.pair !== 'none') {
    const target = resolveLink(file, fm.pair);
    if (!exists(target)) fail(file, `pair ${fm.pair} does not exist`);
    else if (isBilingual(file) && target !== pairOf(file)) fail(file, `pair must be ${posix.basename(pairOf(file))}`);
  } else if (isBilingual(file)) {
    fail(file, 'bilingual document must declare its pair');
  }
}

// 5. Relative links
for (const file of markdown) {
  for (const target of links(read(file))) {
    if (isExternal(target)) continue;
    const resolved = resolveLink(file, target);
    if (resolved && !exists(resolved)) fail(file, `broken link ${target}`);
    // Each folder is a repository that must stand alone when cloned.
    if (resolved && resolved.split('/')[0] !== file.split('/')[0]) fail(file, `relative link leaves its repository: ${target}`);
  }
}

// 6. ADR length
const isAdr = matcher([config.adr.files]);
for (const file of markdown.filter(isAdr)) {
  const words = read(file).split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length;
  if (words > config.adr.maxWords) fail(file, `ADR has ${words} words; limit is ${config.adr.maxWords}`);
}

// 7. Required headings
for (const [file, required] of Object.entries(config.requiredHeadings ?? {})) {
  if (!exists(file)) { fail(file, 'document with required headings is missing'); continue; }
  const present = headings(read(file)).map((h) => h.toLowerCase());
  for (const h of required) if (!present.includes(h.toLowerCase())) fail(file, `required heading "${h}" is missing`);
}

// 8. i18n key parity
function propertiesKeys(text) {
  const entries = new Map();
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i].trim();
    if (!line || line.startsWith('#') || line.startsWith('!')) continue;
    while (line.endsWith('\\') && i + 1 < lines.length) line = line.slice(0, -1) + lines[++i].trim();
    const m = line.match(/^((?:\\.|[^=:\s])+)\s*[=:\s]\s*(.*)$/);
    if (m) entries.set(m[1], m[2]);
  }
  return entries;
}
function jsonKeys(value, prefix = '', entries = new Map()) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    for (const [k, v] of Object.entries(value)) jsonKeys(v, prefix ? `${prefix}.${k}` : k, entries);
  } else {
    entries.set(prefix, typeof value === 'string' ? value : JSON.stringify(value));
  }
  return entries;
}
const bundleGroups = new Map();
for (const file of files.filter((f) => f.split('/').includes('i18n'))) {
  let group;
  if (file.endsWith('.properties')) group = `${posix.dirname(file)}/${posix.basename(file).replace(/(_[A-Za-z-]+)?\.properties$/, '')}`;
  else if (file.endsWith('.json')) group = `${posix.dirname(file)}/*.json`;
  else continue;
  if (!bundleGroups.has(group)) bundleGroups.set(group, []);
  bundleGroups.get(group).push(file);
}
for (const [group, bundle] of bundleGroups) {
  const parsed = bundle.map((file) => {
    try {
      return [file, file.endsWith('.json') ? jsonKeys(JSON.parse(read(file))) : propertiesKeys(read(file))];
    } catch (e) {
      fail(file, `cannot parse i18n file: ${e.message}`);
      return [file, new Map()];
    }
  });
  const allKeys = new Set(parsed.flatMap(([, entries]) => [...entries.keys()]));
  for (const [file, entries] of parsed) {
    for (const key of allKeys) {
      if (!entries.has(key)) fail(file, `i18n key "${key}" is missing (group ${group})`);
      else if (!entries.get(key).trim()) fail(file, `i18n key "${key}" is empty`);
    }
  }
}

// 9. Task progress chart matches the HANDOFF task table
const handoffPath = join(docsRoot, 'handoff', 'HANDOFF.md');
const chartPath = join(docsRoot, 'handoff', 'progress.svg');
if (existsSync(handoffPath)) {
  const handoffRel = toWorkspace(handoffPath);
  try {
    const expected = renderProgress(readFileSync(handoffPath, 'utf8').replace(/\r\n/g, '\n'));
    const actualChart = existsSync(chartPath) ? readFileSync(chartPath, 'utf8').replace(/\r\n/g, '\n') : '';
    if (actualChart !== expected) fail(handoffRel, 'progress.svg is stale: run node orderflow-engine-tools/progress/progress.mjs');
    // The progress table must list exactly the tasks of TASKS.md.
    const tasksPath = join(docsRoot, 'spec', 'TASKS.md');
    if (existsSync(tasksPath)) {
      const planned = [...readFileSync(tasksPath, 'utf8').matchAll(/^### (T-\d\d):/gm)].map((m) => m[1]).join(',');
      const tracked = parseHandoff(readFileSync(handoffPath, 'utf8').replace(/\r\n/g, '\n')).tasks.map((t) => t.id).join(',');
      if (planned !== tracked) fail(handoffRel, `task progress table lists [${tracked}] but TASKS.md defines [${planned}]`);
    }
  } catch (e) {
    fail(handoffRel, `task progress table: ${e.message}`);
  }
}

// 10. Commit lines in TASKS: one Conventional Commit line, at most 60 characters, ending with its own task tag
const tasksFile = join(docsRoot, 'spec', 'TASKS.md');
if (existsSync(tasksFile)) {
  const tasksRel = toWorkspace(tasksFile);
  const commitRule = /^(feat|fix|hotfix|docs|test|refactor|chore|build|perf|release)(\([a-z-]+\))?!?: [^\s].* \((T-\d\d)\)$/;
  for (const block of readFileSync(tasksFile, 'utf8').replace(/\r\n/g, '\n').split('\n### ').slice(1)) {
    const task = (block.match(/^(T-\d\d):/) || [])[1];
    if (!task) continue;
    const line = (block.match(/\*\*Commit:\*\* `([^`]+)`/) || [])[1];
    if (!line) { fail(tasksRel, `${task} has no commit line`); continue; }
    const m = line.match(commitRule);
    if (!m) fail(tasksRel, `${task} commit is not "<type>(<scope>): <summary> (T-NN)": ${line}`);
    else if (m[3] !== task) fail(tasksRel, `${task} commit carries the tag of ${m[3]}`);
    if (line.length > 60) fail(tasksRel, `${task} commit has ${line.length} characters; limit is 60`);
  }
}

// 11. Generated deliverables match their sources
const manifestPath = join(docsRoot, 'deliverables', 'manifest.json');
if (existsSync(manifestPath)) {
  const manifestRel = toWorkspace(manifestPath);
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  for (const doc of manifest.documents ?? []) {
    if (!exists(doc.source)) { fail(manifestRel, `source ${doc.source} does not exist`); continue; }
    const digest = createHash('sha256').update(readFileSync(join(workspace, doc.source))).digest('hex');
    if (digest !== doc.sha256) fail(manifestRel, `${doc.source} changed: run python orderflow-engine-tools/render/build_deliverables.py`);
    for (const output of doc.outputs ?? []) {
      if (!existsSync(join(docsRoot, 'deliverables', output))) fail(manifestRel, `deliverable ${output} is missing`);
    }
  }
}

if (errors.length) {
  console.error(`check-docs: FAIL (${errors.length} problem${errors.length === 1 ? '' : 's'})`);
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}
console.log(`check-docs: OK (${markdown.length} Markdown files, ${bundleGroups.size} i18n bundle groups)`);
