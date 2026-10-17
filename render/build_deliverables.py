"""Builds the Word and PDF deliverables into orderflow-engine-docs/deliverables and records their sources.

Each deliverable is rendered with the print template (render_document.py). The manifest stores the SHA-256 of
every source, so the documentation check fails when a source changes and its deliverable was not rebuilt. It
also stores the SHA-256 of every image a source embeds (key "images", only for sources that embed one).

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

# source (workspace-relative) -> output folder, and the page limit the assignment sets (None: no limit)
DELIVERABLES = [
    ('orderflow-engine-api/docs/adr/0001-order-pricing-and-confirmation.md', 'adr', 1),
    ('orderflow-engine-api/docs/adr/0001-order-pricing-and-confirmation.es.md', 'adr', 1),
] + [
    (f'orderflow-engine-docs/delivery/{name}{suffix}', 'delivery', None)
    for name in ('user-manual', 'technical-manual', 'architecture-report', 'solution-walkthrough')
    for suffix in ('.md', '.es.md')
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    missing = [source_rel for source_rel, _, _ in DELIVERABLES if not (WORKSPACE / source_rel).is_file()]
    if missing:
        print('missing sources:\n  ' + '\n  '.join(missing))
        return 1
    documents = []
    failures = []
    for source_rel, folder, max_pages in DELIVERABLES:
        source = WORKSPACE / source_rel
        target = OUT / folder
        target.mkdir(parents=True, exist_ok=True)
        docx_path = target / (source.stem + '.docx')
        _, images = render_docx(source, docx_path, source_rel)
        pdf_path = to_pdf(docx_path, target)
        pages = len(PdfReader(str(pdf_path)).pages)
        if max_pages is not None and pages > max_pages:
            failures.append(f'{source_rel}: {pages} pages, limit {max_pages}')
        document = {
            'source': source_rel,
            'sha256': digest(source),
            'outputs': [p.relative_to(OUT).as_posix() for p in (docx_path, pdf_path)],
            'pages': pages,
        }
        if images:
            document['images'] = [{'path': image.relative_to(WORKSPACE).as_posix(), 'sha256': digest(image)}
                                  for image in images]
        documents.append(document)
        print(f'built {docx_path.name} and {pdf_path.name} ({pages} page{"s" if pages != 1 else ""})')
    manifest = {'generator': 'orderflow-engine-tools/render/build_deliverables.py', 'documents': documents}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    if failures:
        print('page limit exceeded:\n  ' + '\n  '.join(failures))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
