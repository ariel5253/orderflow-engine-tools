# orderflow-engine-tools

[Español](README.es.md)

Generators and checks for the Orderflow Engine documentation. The tools live here, so they never mix with the documents they produce. Their results are kept in the `orderflow-engine-docs` repository.

## How to run

Run every tool from the workspace root, with the sibling repositories (`orderflow-engine-api`, `orderflow-engine-docs`, …) checked out side by side.

| Need | Version |
|------|---------|
| Node | 18 or later (no packages) |
| Python | 3.11 or later, with `pip install -r orderflow-engine-tools/requirements.txt` |
| LibreOffice | Any recent version, for the PDF conversion |

### With Docker

The image holds Node, Python and the Python packages. The tools run from the mounted workspace, so editing a tool needs no rebuild. From the workspace root:

```bash
docker build -t orderflow-engine-tools orderflow-engine-tools
```

```bash
docker run --rm -v "$PWD":/workspace orderflow-engine-tools
```

The default command runs the documentation check and the integrity check. Any other tool runs by appending its command, for example `python orderflow-engine-tools/diagrams/generate_diagrams.py`. The PDF conversion stays on the host, because it needs LibreOffice and the Arial font of the print template.

## Tools

| Folder | What it does | Command | Writes to |
|--------|--------------|---------|-----------|
| `docs-check/` | Documentation gate: locations, index, language pairs, links, front matter, required headings, ADR length, i18n keys, progress chart, commit lines, deliverable sources | `node orderflow-engine-tools/docs-check/check-docs.mjs` | — |
| `integrity/` | Repository integrity: required `.gitignore`, `.dockerignore` and `.gitattributes` entries, `.env.example` where a repository runs with Docker, Docker files that stay inside their repository, and no secrets | `node orderflow-engine-tools/integrity/check-integrity.mjs` | — |
| `progress/` | Task progress chart, built from the task table in the HANDOFF | `node orderflow-engine-tools/progress/progress.mjs` | `orderflow-engine-docs/handoff/progress.svg` |
| `diagrams/` | The architecture figures, checked for overflowing text, overlapping labels, crossing edges and edges through boxes | `python orderflow-engine-tools/diagrams/generate_diagrams.py` | `orderflow-engine-docs/diagrams/` |
| `render/` | Word and PDF with the print template (A4, Arial 12, black): the ADR, one page at most, and the user manual, technical manual, architecture report and solution walkthrough, in English and Spanish | `python orderflow-engine-tools/render/build_deliverables.py` | `orderflow-engine-docs/deliverables/` |
| `render/` | The presentation decks (PowerPoint, 16:9, Arial), one per language, with speaker notes | `python orderflow-engine-tools/render/build_presentation.py` | `orderflow-engine-docs/deliverables/delivery/` |
| `screenshots/` | Screenshots of the web client in Spanish and English, and a PNG image of each architecture figure, for the delivery documents | `node /e2e/screenshots/capture.mjs`, inside the end-to-end runner image (see below) | `orderflow-engine-docs/delivery/screenshots/`, `orderflow-engine-docs/delivery/figures/` |
| `consistency/` | Cross-references, stated counts, language leaks and English/Spanish parity | `python orderflow-engine-tools/consistency/<check>.py` | — |

The Word renderer reads front matter, headings, paragraphs with bold and inline code, `- ` bullets, `1. ` numbered steps, pipe tables, fenced code blocks, notices (a quote that starts with a bold label, such as `> **Note:**`) and images on their own line, `![caption](path.png)`. An image path is relative to its Markdown file, and the image must be PNG or JPEG. It is scaled to the usable width, at most 18 cm high, and numbered by the renderer ("Figure N." in English, "Figura N." in Spanish), so captions carry no number. A document in `orderflow-engine-docs/delivery/` also gets a title block with its title, the author named in `LICENSE` and its `last-reviewed` date. A missing image, an image in another format or an unclosed code fence stops the build with the file and line.

The deck builder reads one slide per `##` heading: bullets, numbered steps, at most one image, and the speaker notes in a last `> **Notes:**` block (`> **Notas:**` in Spanish). It writes the same bytes for the same source, and it stops before writing any deck when an image is missing or the source breaks the format.

The screenshots need the full stack running (web client on port 8081 of the host) and the end-to-end runner image of `orderflow-engine-infra`, which holds Node, Playwright and Chromium. From the workspace root:

```bash
docker build --tag ofe-e2e-runner orderflow-engine-infra/e2e
```

```bash
docker run --rm --init --ipc=host --add-host=host.docker.internal:host-gateway \
  -v "$PWD/orderflow-engine-tools/screenshots:/e2e/screenshots:ro" \
  -v "$PWD/orderflow-engine-docs:/docs" \
  ofe-e2e-runner node /e2e/screenshots/capture.mjs
```

The confirmation screenshot places one order per language on credit of the first store. `CONFIRM=0` (passed with `-e CONFIRM=0`) places no order and skips that screenshot, and `ONLY=screens` or `ONLY=figures` takes only one of the two sets. The header of `screenshots/capture.mjs` lists every option.

## Source of each result

| Result | Generated from |
|--------|----------------|
| Figures | The figure definitions in `diagrams/generate_diagrams.py`. Each figure cites its specification section in its footer |
| Progress chart | The task table in `orderflow-engine-docs/handoff/HANDOFF.md` |
| Word and PDF | The ADR in `orderflow-engine-api/docs/adr/` and the delivery documents in `orderflow-engine-docs/delivery/`. `deliverables/manifest.json` records each source and its SHA-256, and the SHA-256 of every image a source embeds |
| Presentation decks | `orderflow-engine-docs/delivery/presentation.md` and `presentation.es.md` |
| Screenshots and figure images | The running web client, and the SVG figures in `orderflow-engine-docs/diagrams/` |
