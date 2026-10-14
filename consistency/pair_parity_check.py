"""Content parity of en/es pairs: inline code spans, table rows and list items must match."""
import io
import os
import re
import sys
from pathlib import Path

R = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2])
pdf = open(os.path.join(R, 'orderflow-engine-docs/assignment/Prueba_Tecnica_Tech_Lead_1.pdf'), 'rb').read()
print('PDF XMP metadata present:', b'xmpmeta' in pdf)

pairs = []
for top in sorted(d for d in os.listdir(R) if d.startswith('orderflow-engine')):
    for root, _, files in os.walk(os.path.join(R, top)):
        for f in files:
            if f.endswith('.es.md'):
                es = os.path.join(root, f)
                en = es[:-6] + '.md'
                if os.path.exists(en):
                    pairs.append((en, es))


def strip_front(t):
    return re.sub(r'^---\n.*?\n---\n', '', t, flags=re.S)


def profile(path):
    t = strip_front(io.open(path, encoding='utf-8').read())
    t_no_fence = re.sub(r'```.*?```', '', t, flags=re.S)
    # Each language links to its own counterpart: README.md <-> README.es.md is expected.
    codes = [c.replace('.es.md', '.md') for c in re.findall(r'`([^`\n]+)`', t_no_fence)]
    # Tree blocks carry translated comments after two or more spaces: compare structure only.
    fences = [re.sub(r'(?m)\s{2,}\S.*$', '', f).replace('.es.md', '.md')
              for f in re.findall(r'```.*?```', t, flags=re.S)]
    rows = len([l for l in t.split('\n') if l.startswith('|') and not re.match(r'^\|[-| ]+\|$', l)])
    items = len([l for l in t.split('\n') if re.match(r'^\s*(- |\d+\. )', l)])
    return codes, fences, rows, items


total = 0
for en, es in pairs:
    ce, fe, re_, ie = profile(en)
    cs, fs, rs, is_ = profile(es)
    rel = os.path.relpath(en, R).replace(os.sep, '/')
    issues = []
    only_en = sorted(set(ce) - set(cs))
    only_es = sorted(set(cs) - set(ce))
    if only_en: issues.append(f'code only in en: {only_en}')
    if only_es: issues.append(f'code only in es: {only_es}')
    if fe != fs: issues.append('code blocks differ')
    if re_ != rs: issues.append(f'table rows en={re_} es={rs}')
    if ie != is_: issues.append(f'list items en={ie} es={is_}')
    total += len(issues)
    print(f'{"OK " if not issues else "BAD"} {rel}')
    for i in issues:
        print('     -', i)
print('pairs:', len(pairs), 'issues:', total)
