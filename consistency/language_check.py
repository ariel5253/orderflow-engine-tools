"""Language leak scan: Spanish text in English-only files, and English sentences in Spanish files."""
import os
import re
import sys
from pathlib import Path

root_dir = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2])
spanish_chars = re.compile(r'[áéíóúñ¿¡ÁÉÍÓÚÑ]')
english_words = re.compile(r'\b(the|and|is|are|with|which|when|this|that|from|only|never|must|every)\b', re.I)
scanned = 0
for top in sorted(d for d in os.listdir(root_dir) if d.startswith('orderflow-engine')):
    for root, dirs, files in os.walk(os.path.join(root_dir, top)):
        for f in files:
            if not f.endswith(('.md', '.json', '.mjs', '.svg')):
                continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, root_dir).replace(os.sep, '/')
            scanned += 1
            in_code = False
            for i, line in enumerate(open(path, encoding='utf-8'), 1):
                if line.strip().startswith('```'):
                    in_code = not in_code
                    continue
                if in_code:
                    continue
                if not f.endswith('.es.md'):
                    m = spanish_chars.search(line)
                    if m and 'Español' not in line:
                        print(f'ES-IN-EN  {rel}:{i}: {line.strip()[:110]}')
                else:
                    text = re.sub(r'`[^`]*`', '', line)
                    hits = english_words.findall(text)
                    if len(hits) >= 3:
                        print(f'EN-IN-ES  {rel}:{i}: {line.strip()[:110]}')
print('files scanned:', scanned)
