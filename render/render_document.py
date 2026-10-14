"""Renders a governed Markdown document to Word (.docx) and PDF with the print template.

Template: A4, 2 cm margins, Arial 12 for every run, black text, bold headings, thin black table borders,
and a footer with the source path, its last-reviewed date and the page number. The .docx is the master;
LibreOffice converts it to PDF, so both formats always match.

Usage (from the workspace root):
  python orderflow-engine-tools/render/render_document.py <source.md> <output-dir> [--pdf]
"""
import argparse
import hashlib
import io
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FONT = 'Arial'
SIZE = Pt(12)
BLACK = RGBColor(0, 0, 0)
SOFFICE_CANDIDATES = [
    'soffice',
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    '/Applications/LibreOffice.app/Contents/MacOS/soffice',
]


def front_matter(text):
    match = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    data = {}
    if match:
        for line in match.group(1).split('\n'):
            key, _, value = line.partition(':')
            data[key.strip()] = value.strip()
        text = text[match.end():]
    return data, text


def style_run(run, bold=False, mono=False):
    run.font.name = FONT
    run.font.size = SIZE
    run.font.bold = bold
    run.font.color.rgb = BLACK
    run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    if mono:
        run.font.highlight_color = None


def add_inline(paragraph, text):
    """Supports **bold** and `code` (rendered in Arial, as the template allows one font only)."""
    for token in re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', text):
        if not token:
            continue
        if token.startswith('**'):
            style_run(paragraph.add_run(token[2:-2]), bold=True)
        elif token.startswith('`'):
            style_run(paragraph.add_run(token[1:-1]), mono=True)
        else:
            style_run(paragraph.add_run(token))


def set_cell_borders(table):
    tbl = table._tbl
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        element = OxmlElement(f'w:{edge}')
        element.set(qn('w:val'), 'single')
        element.set(qn('w:sz'), '4')
        element.set(qn('w:color'), '000000')
        borders.append(element)
    tbl.tblPr.append(borders)


FOOTER_LABELS = {'en': ('Source', 'p.'), 'es': ('Fuente', 'pág.')}
CHAR_EMU = 85000      # average Arial 12 character width
PADDING_EMU = 180000  # left and right cell padding


def column_widths(rows, usable):
    """No column is narrower than its longest word, so words never break; the rest follows content length."""
    cols = len(rows[0])
    plain = [[re.sub(r'[*`]', '', row[c]) for c in range(cols)] for row in rows]
    minimum = [max(len(w) for row in plain for w in (row[c].split() or [''])) * CHAR_EMU + PADDING_EMU
               for c in range(cols)]
    content = [max(len(row[c]) for row in plain) for c in range(cols)]
    spare = max(0, usable - sum(minimum))
    extra = [max(0, content[c] - max(len(w) for row in plain for w in (row[c].split() or ['']))) for c in range(cols)]
    total = sum(extra) or 1
    return [int(minimum[c] + spare * extra[c] / total) for c in range(cols)]


def add_page_number(paragraph):
    for instruction in ('PAGE',):
        run = paragraph.add_run()
        style_run(run)
        begin = OxmlElement('w:fldChar'); begin.set(qn('w:fldCharType'), 'begin')
        code = OxmlElement('w:instrText'); code.set(qn('xml:space'), 'preserve'); code.text = instruction
        end = OxmlElement('w:fldChar'); end.set(qn('w:fldCharType'), 'end')
        run._r.append(begin); run._r.append(code); run._r.append(end)


def render_docx(source, out_path, source_label):
    raw = io.open(source, encoding='utf-8').read().replace('\r\n', '\n')
    meta, body = front_matter(raw)
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    for side in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
        setattr(section, side, Cm(2.0))
    normal = doc.styles['Normal']
    normal.font.name = FONT
    normal.font.size = SIZE
    normal.font.color.rgb = BLACK
    normal.paragraph_format.space_after = Pt(4)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.LEFT
    labels = FOOTER_LABELS.get(meta.get('lang', 'en'), FOOTER_LABELS['en'])
    add_inline(footer, f'{labels[0]}: {source_label} · {labels[1]} ')
    add_page_number(footer)

    lines = body.split('\n')
    i = 0
    after_table = False
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                if not re.match(r'^\|[-| :]+\|$', lines[i]):
                    rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            table = doc.add_table(rows=len(rows), cols=len(rows[0]))
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.autofit = False
            set_cell_borders(table)
            # Column widths follow content length, so short columns do not force long ones to wrap.
            usable = section.page_width - section.left_margin - section.right_margin
            widths = column_widths(rows, usable)
            for c, width in enumerate(widths):
                table.columns[c].width = width
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    cell = table.cell(r, c)
                    cell.width = widths[c]
                    paragraph = cell.paragraphs[0]
                    paragraph.paragraph_format.space_after = Pt(0)
                    if r == 0:
                        style_run(paragraph.add_run(value.replace('**', '')), bold=True)
                    else:
                        add_inline(paragraph, value)
            after_table = True
            continue
        heading = re.match(r'^(#{1,3}) (.*)$', line)
        if heading:
            paragraph = doc.add_paragraph()
            paragraph.paragraph_format.space_before = Pt(8 if heading.group(1) != '#' else 0)
            paragraph.paragraph_format.space_after = Pt(4)
            paragraph.paragraph_format.keep_with_next = True
            style_run(paragraph.add_run(heading.group(2)), bold=True)
            after_table = False
            i += 1
            continue
        bullet = re.match(r'^\s*[-*] (.*)$', line)
        if bullet:
            paragraph = doc.add_paragraph(style='List Bullet')
            paragraph.paragraph_format.space_after = Pt(2)
            add_inline(paragraph, bullet.group(1))
            after_table = False
            i += 1
            continue
        paragraph = doc.add_paragraph()
        if after_table:
            paragraph.paragraph_format.space_before = Pt(6)
        after_table = False
        text = line
        while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r'^(#|\||\s*[-*] )', lines[i + 1]):
            i += 1
            text += ' ' + lines[i].strip()
        add_inline(paragraph, text)
        i += 1

    for style_name in ('List Bullet',):
        style = doc.styles[style_name]
        style.font.name = FONT
        style.font.size = SIZE
        style.font.color.rgb = BLACK
    clean_metadata(doc, meta)
    doc.save(out_path)
    strip_application(out_path)
    return meta


def to_pdf(docx_path, out_dir):
    for candidate in SOFFICE_CANDIDATES:
        exe = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if exe:
            subprocess.run([exe, '--headless', '--convert-to', 'pdf', '--outdir', str(out_dir), str(docx_path)],
                           check=True, capture_output=True)
            return Path(out_dir) / (Path(docx_path).stem + '.pdf')
    raise SystemExit('LibreOffice (soffice) is required to produce the PDF')


def license_holder():
    """The document author is the copyright holder named in this repository's LICENSE."""
    text = (Path(__file__).resolve().parents[1] / 'LICENSE').read_text(encoding='utf-8')
    match = re.search(r'Copyright \(c\) \d{4} (.+)', text)
    return match.group(1).strip() if match else ''


def clean_metadata(doc, meta):
    props = doc.core_properties
    props.author = license_holder()
    props.last_modified_by = license_holder()
    props.title = meta.get('title', '')
    props.subject = ''
    props.keywords = ''
    props.comments = ''
    props.category = ''


def strip_application(docx_path):
    """Removes the application name that the default template carries in docProps/app.xml."""
    path = Path(docx_path)
    with zipfile.ZipFile(path) as source:
        items = [(info, source.read(info.filename)) for info in source.infolist()]
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as target:
        for info, data in items:
            if info.filename == 'docProps/app.xml':
                data = re.sub(rb'<Application>[^<]*</Application>|<AppVersion>[^<]*</AppVersion>', b'', data)
            target.writestr(info, data)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('out_dir')
    parser.add_argument('--pdf', action='store_true')
    parser.add_argument('--label', help='source path as shown in the footer (defaults to the given path)')
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source = Path(args.source)
    docx_path = out_dir / (source.stem + '.docx')
    render_docx(source, docx_path, args.label or source.as_posix())
    print(f'written {docx_path}')
    if args.pdf:
        print(f'written {to_pdf(docx_path, out_dir)}')


if __name__ == '__main__':
    sys.exit(main())
