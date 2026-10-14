"""Builds the Word and PDF deliverables into orderflow-engine-docs/deliverables and records their sources.

Each deliverable is rendered with the print template (render_document.py). The manifest stores the SHA-256 of
every source, so the documentation check fails when a source changes and its deliverable was not rebuilt.

Usage (from the workspace root, with LibreOffice installed):
  python orderflow-engine-tools/render/build_deliverables.py
"""
import hashlib
import json
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_document import render_docx, to_pdf  # noqa: E402

WORKSPACE = Path(__file__).resolve().parents[2]
OUT = WORKSPACE / 'orderflow-engine-docs' / 'deliverables'

# source (workspace-relative) -> output folder, and the page limit the assignment sets
DELIVERABLES = [
    ('orderflow-engine-api/docs/adr/0001-order-pricing-and-confirmation.md', 'adr', 1),
    ('orderflow-engine-api/docs/adr/0001-order-pricing-and-confirmation.es.md', 'adr', 1),
]


def main():
    documents = []
    failures = []
    for source_rel, folder, max_pages in DELIVERABLES:
        source = WORKSPACE / source_rel
        target = OUT / folder
        target.mkdir(parents=True, exist_ok=True)
        docx_path = target / (source.stem + '.docx')
        render_docx(source, docx_path, source_rel)
        pdf_path = to_pdf(docx_path, target)
        pages = len(PdfReader(str(pdf_path)).pages)
        if pages > max_pages:
            failures.append(f'{source_rel}: {pages} pages, limit {max_pages}')
        documents.append({
            'source': source_rel,
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'outputs': [p.relative_to(OUT).as_posix() for p in (docx_path, pdf_path)],
            'pages': pages,
        })
        print(f'built {docx_path.name} and {pdf_path.name} ({pages} page{"s" if pages != 1 else ""})')
    manifest = {'generator': 'orderflow-engine-tools/render/build_deliverables.py', 'documents': documents}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    if failures:
        print('page limit exceeded:\n  ' + '\n  '.join(failures))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
