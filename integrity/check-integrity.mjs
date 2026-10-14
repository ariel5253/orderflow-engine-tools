#!/usr/bin/env node
// Repository integrity check for the orderflow-engine-* workspace.
// Policy: orderflow-engine-docs/governance/repository-integrity.md. Rules: the "integrity" section of
// orderflow-engine-docs/governance/docs-governance.json. No dependencies; Node 18+.
// Run from the workspace root: node orderflow-engine-tools/integrity/check-integrity.mjs
import { execFileSync } from 'node:child_process';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { dirname, join, posix, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const workspace = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const config = JSON.parse(readFileSync(join(workspace, 'orderflow-engine-docs', 'governance', 'docs-governance.json'), 'utf8'));
const rules = config.integrity;
const errors = [];
const fail = (file, message) => errors.push(`${file}: ${message}`);
const read = (rel) => readFileSync(join(workspace, rel), 'utf8').replace(/\r\n/g, '\n');
const exists = (rel) => existsSync(join(workspace, rel));
const lines = (rel) => read(rel).split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#'));

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

const SECRET_PATTERNS = [
  [/-----BEGIN [A-Z ]*PRIVATE KEY-----/, 'private key'],
  [/\bAKIA[0-9A-Z]{16}\b/, 'cloud access key'],
  [/\bghp_[A-Za-z0-9]{36}\b/, 'GitHub token'],
  [/\bxox[abprs]-[A-Za-z0-9-]{10,}/, 'chat token'],
];
const CONFIG_FILE = /(^|\/)(\.env[^/]*|[^/]+\.ya?ml|[^/]+\.properties)$/;
const SECRET_KEY = /^\s*([A-Za-z0-9_.-]*(password|passwd|secret|token|api[_.-]?key|private[_.-]?key)[A-Za-z0-9_.-]*)\s*[=:]\s*(.*)$/i;
const ALLOWED_VALUE = /^(|change-me|"change-me"|'change-me'|\$\{[^}]+\}|""|'')$/;

for (const repo of config.scanRoots.filter(exists)) {
  const repoRules = rules.repositories[repo] ?? {};
  const files = walk(repo, []);
  const has = (name) => exists(`${repo}/${name}`);

  // .gitignore
  const gitignore = `${repo}/.gitignore`;
  if (!has('.gitignore')) fail(repo, 'missing .gitignore');
  else {
    const present = lines(gitignore);
    for (const entry of [...rules.gitignore.common, ...(repoRules.gitignore ?? [])]) {
      if (!present.includes(entry)) fail(gitignore, `missing required entry "${entry}"`);
    }
  }

  // .gitattributes
  const attributes = `${repo}/.gitattributes`;
  if (!has('.gitattributes')) fail(repo, 'missing .gitattributes');
  else {
    const present = lines(attributes).map((l) => l.replace(/\s+/g, ' '));
    for (const entry of rules.gitattributes) if (!present.includes(entry)) fail(attributes, `missing line "${entry}"`);
  }

  // Docker: .dockerignore and standalone paths
  const dockerFiles = ['Dockerfile', 'compose.yaml', 'compose.yml', 'docker-compose.yml', 'docker-compose.yaml'].filter(has);
  if (has('Dockerfile')) {
    const dockerignore = `${repo}/.dockerignore`;
    if (!has('.dockerignore')) fail(repo, 'has a Dockerfile but no .dockerignore');
    else {
      const present = lines(dockerignore);
      for (const entry of [...rules.dockerignore.common, ...(repoRules.dockerignore ?? [])]) {
        if (!present.includes(entry)) fail(dockerignore, `missing required entry "${entry}"`);
      }
    }
  }
  if (!repoRules.mayReferenceSiblings) {
    for (const name of dockerFiles) {
      const text = read(`${repo}/${name}`);
      if (/(^|[\s"'=:])\.\.(\/|\\|\s|$|")/m.test(text)) fail(`${repo}/${name}`, 'references a path outside its repository');
    }
  }

  // .env.example where the repository runs with configuration
  if (repoRules.envExample && dockerFiles.length > 0) {
    const example = `${repo}/.env.example`;
    if (!has('.env.example')) fail(repo, 'runs with Docker but has no .env.example');
    else {
      const raw = read(example).split('\n');
      raw.forEach((line, i) => {
        const m = line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)$/);
        if (!m) return;
        const previous = raw.slice(0, i).reverse().find((l) => l.trim());
        if (!previous || !previous.trim().startsWith('#')) fail(example, `key ${m[1]} has no comment line above it`);
      });
    }
  }

  // A local .env holds the real values, so its content is never scanned; instead it must never be tracked
  if (has('.git')) {
    try {
      const tracked = execFileSync('git', ['-C', join(workspace, repo), 'ls-files', '--', '.env', '**/.env'],
        { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
      if (tracked) fail(repo, `git tracks ${tracked.split('\n').join(', ')}`);
    } catch (e) {
      fail(repo, `cannot verify tracked files with git: ${String(e.stderr || e.message).trim().split('\n')[0]}`);
    }
  }

  // Secrets
  for (const rel of files) {
    if (posix.basename(rel) === '.env') continue;
    if (rules.binaryExtensions.some((ext) => rel.toLowerCase().endsWith(ext))) continue;
    let text;
    try { text = read(rel); } catch { continue; }
    for (const [pattern, what] of SECRET_PATTERNS) if (pattern.test(text)) fail(rel, `looks like a ${what}`);
    if (CONFIG_FILE.test(rel)) {
      text.split('\n').forEach((line, i) => {
        const m = line.match(SECRET_KEY);
        if (m && !line.trim().startsWith('#') && !ALLOWED_VALUE.test(m[3].trim())) fail(rel, `line ${i + 1}: ${m[1]} has a value`);
      });
    }
  }
}

if (errors.length) {
  console.error(`check-integrity: FAIL (${errors.length} problem${errors.length === 1 ? '' : 's'})`);
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}
console.log(`check-integrity: OK (${config.scanRoots.filter(exists).length} repositories)`);
