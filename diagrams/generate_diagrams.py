"""Generates the Orderflow Engine SVG figures on a fixed grid and checks them for collisions.

Every figure is checked for text overflowing its box, labels over boxes, edges crossing each other and
edges passing through boxes. The run fails if any check fails.

Usage (from the workspace root):
  python orderflow-engine-tools/diagrams/generate_diagrams.py [output_dir]
The default output is orderflow-engine-docs/diagrams.
"""
from pathlib import Path
import html
import os
import sys

FONT = "ui-sans-serif, system-ui, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
PAL = {
    'node': ('#ffffff', '#94a3b8'), 'key': ('#e0f2fe', '#0284c7'), 'group': ('#f8fafc', '#cbd5e1'),
    'tx': ('#f0fdf4', '#16a34a'), 'warn': ('#fffbeb', '#d97706'), 'muted': ('#f8fafc', '#94a3b8'),
    'note': ('#f8fafc', '#cbd5e1'), 'bad': ('#fef2f2', '#dc2626'),
}
TXT = {'t': '#0f172a', 's': '#475569', 'txt': '#15803d', 'warnt': '#b45309', 'badt': '#b91c1c', 'keyt': '#0369a1'}
EDGE = {'edge': ('#475569', 'a'), 'bad': ('#dc2626', 'abad'), 'txe': ('#16a34a', 'atx'), 'keye': ('#0284c7', 'akey')}
DARK = """@media (prefers-color-scheme: dark) {
      .card { fill: #0b1220; stroke: #1e293b; } .group { fill: #0f172a; stroke: #334155; }
      .node { fill: #111a2e; stroke: #475569; } .key { fill: #0c3a52; stroke: #38bdf8; }
      .tx { fill: #052e1a; stroke: #22c55e; } .warn { fill: #3a2a06; stroke: #f59e0b; }
      .muted { fill: #0f172a; stroke: #475569; } .note { fill: #131c2e; stroke: #475569; }
      .bad { fill: #3b0d0d; stroke: #f87171; }
      .t { fill: #e2e8f0; } .s { fill: #94a3b8; } .txt { fill: #4ade80; } .warnt { fill: #fbbf24; }
      .badt { fill: #f87171; } .keyt { fill: #38bdf8; }
      .edge { stroke: #94a3b8; } .ea { fill: #94a3b8; } .edgebad { stroke: #f87171; } .eabad { fill: #f87171; }
      .edgetx { stroke: #4ade80; } .eatx { fill: #4ade80; } .edgekey { stroke: #38bdf8; } .eakey { fill: #38bdf8; }
      .life { stroke: #475569; } .halo { stroke: #0b1220; }
    }"""


def esc(s):
    return html.escape(str(s), quote=True)


def text_width(s, size, weight=None):
    factor = 0.60 if weight else 0.56
    return len(str(s)) * size * factor


class Diagram:
    def __init__(self, name, w, h, title, subtitle, aria, source):
        self.name, self.w, self.h = name, w, h
        self.title, self.subtitle, self.aria, self.source = title, subtitle, aria, source
        self.els = []
        self.rects = []      # (x, y, w, h, id) obstacles for labels
        self.labels = []     # (x0, y0, x1, y1, text) free labels
        self.problems = []
        self.edges = []      # list of point lists

    def add(self, s):
        self.els.append(s)

    def text(self, x, y, s, size=11, weight=None, anchor='middle', cls='s', halo=False):
        halo_attr = ' stroke="#ffffff" stroke-width="4" stroke-linejoin="round" paint-order="stroke"' if halo else ''
        w_attr = f' font-weight="{weight}"' if weight else ''
        c = cls + (' halo' if halo else '')
        self.add(f'<text class="{c}" x="{x:g}" y="{y:g}" text-anchor="{anchor}" font-size="{size}"{w_attr} '
                 f'fill="{TXT[cls]}"{halo_attr}>{esc(s)}</text>')
        tw = text_width(s, size, weight)
        x0 = x - tw / 2 if anchor == 'middle' else (x if anchor == 'start' else x - tw)
        return (x0, y - size * 0.78, x0 + tw, y + size * 0.22)

    def rect(self, x, y, w, h, kind='node', rx=8, dashed=False, obstacle=True, rid=None):
        fill, stroke = PAL[kind]
        dash = ' stroke-dasharray="5 4"' if dashed or kind == 'muted' else ''
        self.add(f'<rect class="{kind}" x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"{dash}/>')
        if obstacle:
            self.rects.append((x, y, w, h, rid or f'rect@{x},{y}'))

    def box(self, x, y, w, h, title, *subs, kind='node', title_cls='t', size=12):
        self.rect(x, y, w, h, kind, rid=title)
        n = len(subs)
        ty = y + h / 2 + 4 - 7.5 * n
        bb = self.text(x + w / 2, ty, title, size, 600, cls=title_cls)
        self._fits(bb, x, w, title)
        for i, s in enumerate(subs):
            bb = self.text(x + w / 2, ty + 16 * (i + 1), s, 10.5)
            self._fits(bb, x, w, s)

    def group(self, x, y, w, h, label, kind='group', dashed=False, label_cls='s'):
        self.rect(x, y, w, h, kind, rx=12, dashed=dashed, obstacle=False)
        self.text(x + 14, y + 20, label, 11, 600, anchor='start', cls=label_cls)

    def note(self, x, y, w, h, title, lines):
        self.rect(x, y, w, h, 'note', rx=8, rid='note:' + title)
        bb = self.text(x + 14, y + 22, title, 11.5, 600, anchor='start', cls='t')
        self._fits(bb, x, w, title)
        for i, line in enumerate(lines):
            bb = self.text(x + 14, y + 41 + 16 * i, line, 10.5, anchor='start')
            self._fits(bb, x, w, line)

    def _fits(self, bb, x, w, s):
        if bb[0] < x + 6 or bb[2] > x + w - 6:
            self.problems.append(f'text overflows its box: "{s}"')

    def edge(self, pts, kind='edge', dashed=False, arrow=True, width=1.4):
        color, marker = EDGE[kind]
        cls = {'edge': 'edge', 'bad': 'edgebad', 'txe': 'edgetx', 'keye': 'edgekey'}[kind]
        self.edges.append(list(pts))
        d = 'M' + ' L'.join(f'{px:g},{py:g}' for px, py in pts)
        dash = ' stroke-dasharray="6 4"' if dashed else ''
        m = f' marker-end="url(#{marker})"' if arrow else ''
        self.add(f'<path class="{cls}" d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{dash}{m}/>')

    def label(self, x, y, s, anchor='middle', cls='s', size=10.5, weight=None):
        bb = self.text(x, y, s, size, weight, anchor=anchor, cls=cls, halo=True)
        self.labels.append((*bb, s))

    # sequence helpers
    def lifeline(self, x, top, bottom, title, sub, kind='node', w=170):
        self.box(x - w / 2, top, w, 44, title, sub, kind=kind)
        self.add(f'<line class="life" x1="{x:g}" y1="{top + 44:g}" x2="{x:g}" y2="{bottom:g}" '
                 f'stroke="#94a3b8" stroke-width="1" stroke-dasharray="4 4"/>')

    def msg(self, x1, x2, y, s, ret=False, kind='edge', weight=None, cls='s'):
        end = x2 - 3 if x2 > x1 else x2 + 3
        self.edge([(x1, y), (end, y)], kind=kind, dashed=ret, width=2 if weight else 1.4)
        self.label((x1 + x2) / 2, y - 7, s, cls=cls, weight=weight)

    def self_msg(self, x, y, s, side='right'):
        dx = 44 if side == 'right' else -44
        self.edge([(x, y), (x + dx, y), (x + dx, y + 18), (x + (4 if side == 'right' else -4), y + 18)])
        if side == 'right':
            self.label(x + dx + 8, y + 13, s, anchor='start')
        else:
            self.label(x + dx - 8, y + 13, s, anchor='end')

    @staticmethod
    def _segments(pts):
        return list(zip(pts, pts[1:]))

    @staticmethod
    def _cross(a, b, c, d):
        # proper intersection of axis-aligned or oblique segments, ignoring touching endpoints
        def orient(p, q, r):
            v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
            return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
        if a in (c, d) or b in (c, d):
            return False
        o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
        if o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4):
            return True
        return False

    @staticmethod
    def _through(a, b, rect):
        # does the segment pass through the interior of the rectangle (shrunk by 4 px)?
        x, y, w, h = rect
        x0, y0, x1, y1 = x + 4, y + 4, x + w - 4, y + h - 4
        steps = 200
        for i in range(1, steps):
            t = i / steps
            px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            if x0 < px < x1 and y0 < py < y1:
                return True
        return False

    def check(self):
        for i, e1 in enumerate(self.edges):
            for e2 in self.edges[i + 1:]:
                if e1[0] == e2[0] or e1[-1] == e2[-1] or set(e1) & set(e2):
                    shared = True
                else:
                    shared = False
                for a, b in self._segments(e1):
                    for c, d in self._segments(e2):
                        if not shared and self._cross(a, b, c, d):
                            self.problems.append(f'edges cross: {e1[0]}→{e1[-1]} and {e2[0]}→{e2[-1]}')
            for a, b in self._segments(e1):
                for (rx, ry, rw, rh, rid) in self.rects:
                    if self._through(a, b, (rx, ry, rw, rh)):
                        self.problems.append(f'edge {e1[0]}→{e1[-1]} passes through box "{rid}"')
        for (x0, y0, x1, y1, s) in self.labels:
            for (rx, ry, rw, rh, rid) in self.rects:
                if x0 < rx + rw and x1 > rx and y0 < ry + rh and y1 > ry:
                    self.problems.append(f'label "{s}" overlaps box "{rid}"')
            if x0 < 8 or x1 > self.w - 8:
                self.problems.append(f'label "{s}" leaves the figure')
        for i, a in enumerate(self.labels):
            for b in self.labels[i + 1:]:
                if a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]:
                    self.problems.append(f'labels overlap: "{a[4]}" / "{b[4]}"')
        return self.problems

    def render(self):
        markers = ''.join(
            f'<marker id="{mid}" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="10" markerHeight="8" '
            f'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path class="{cls}" d="M0,0 L10,4 L0,8 z" fill="{col}"/></marker>'
            for mid, cls, col in [('a', 'ea', '#475569'), ('abad', 'eabad', '#dc2626'),
                                  ('atx', 'eatx', '#16a34a'), ('akey', 'eakey', '#0284c7')])
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
                f'height="{self.h}" role="img" aria-label="{esc(self.aria)}" font-family="{esc(FONT)}">\n'
                f'  <title>{esc(self.title)}</title>\n  <desc>{esc(self.subtitle)}</desc>\n'
                f'  <defs>\n    {markers}\n    <style>\n    {DARK}\n    </style>\n  </defs>\n'
                f'  <rect class="card" x="0.5" y="0.5" width="{self.w - 1}" height="{self.h - 1}" rx="12" '
                f'fill="#ffffff" stroke="#cbd5e1"/>\n')
        title = (f'  <text class="t" x="{self.w / 2:g}" y="34" text-anchor="middle" font-size="15" font-weight="600" '
                 f'fill="#0f172a">{esc(self.title)}</text>\n'
                 f'  <text class="s" x="{self.w / 2:g}" y="54" text-anchor="middle" font-size="11.5" '
                 f'fill="#475569">{esc(self.subtitle)}</text>\n')
        foot = (f'  <text class="s" x="{self.w - 24}" y="{self.h - 16}" text-anchor="end" font-size="10" '
                f'fill="#475569">{esc(self.source)} · generated by orderflow-engine-tools</text>\n')
        return head + title + ''.join('  ' + e + '\n' for e in self.els) + foot + '</svg>\n'


# ---------------------------------------------------------------- figures

def fig01():
    d = Diagram('01-runtime-topology', 960, 580,
                'Runtime topology: one service, one database, effects only through the outbox',
                'Every arrow is a call that exists at runtime; nothing in the request path reaches push or the ERP',
                'Runtime topology: the browser loads the web client from the nginx of orderflow-engine-web, which forwards '
                '/api/ to orderflow-engine-api over HTTP, so the browser sees one origin; inside the service, the web adapter '
                'invokes the use cases, which call the pure pricing engine and the persistence adapter; PostgreSQL is the '
                'single source of truth; the outbox relay is the only component that calls the push gateway and the ERP.',
                'Source: SPEC §7, §10, §12 · architecture.md §1.1 · push and ERP are fakes in this delivery')
    d.group(280, 88, 640, 310, 'orderflow-engine-api · Spring Boot · one deployable', kind='group')
    d.box(40, 124, 180, 64, 'orderflow-engine-web', 'Angular · full order flow', 'nginx forwards /api/')
    d.box(300, 130, 170, 52, 'Web adapter', 'REST · problem+json')
    d.box(520, 130, 180, 52, 'Use cases', 'quote · confirm · history', kind='key')
    d.box(750, 130, 150, 52, 'Pricing engine', 'pure · no I/O')
    d.box(300, 300, 170, 52, 'Outbox relay', 'lease · backoff · DEAD')
    d.box(520, 300, 180, 52, 'Persistence adapter', 'JdbcClient · explicit locks')
    d.box(520, 450, 180, 56, 'PostgreSQL', 'single source of truth', kind='key')
    d.box(40, 262, 180, 48, 'Push gateway', 'dedupes by event_id')
    d.box(40, 342, 180, 48, 'ERP', 'upserts by order number')
    d.edge([(220, 156), (297, 156)]); d.label(258, 148, 'HTTP · /api/')
    d.edge([(470, 156), (517, 156)]); d.label(495, 148, 'invokes')
    d.edge([(700, 156), (747, 156)]); d.label(725, 148, 'price()')
    d.edge([(610, 182), (610, 297)]); d.label(618, 244, 'load · save · lock', anchor='start')
    d.edge([(610, 352), (610, 447)]); d.label(618, 424, 'one transaction per request', anchor='start')
    d.edge([(470, 326), (517, 326)]); d.label(495, 318, 'claims')
    d.edge([(300, 326), (250, 326), (250, 286), (223, 286)])
    d.edge([(250, 326), (250, 366), (223, 366)])
    d.label(258, 302, 'notify', anchor='start')
    d.label(258, 356, 'publish', anchor='start')
    d.note(720, 430, 220, 96, 'Effects leave via the outbox',
           ['Push and ERP are called only', 'by the relay, after the order', 'is committed (P-04, P-05).'])
    return d


def fig02():
    d = Diagram('02-workspace-repositories', 960, 470,
                'Workspace: six folders, each a future repository',
                'Arrows show what each repository takes from another; the specification governs all of them',
                'Workspace: orderflow-engine-docs specifies the API, the web client and the infrastructure; '
                'orderflow-engine-tools generates the figures, the progress chart and the ADR in Word and PDF into '
                'orderflow-engine-docs; the web client reads the API contract of orderflow-engine-api; orderflow-engine-infra provides '
                'the full stack with Docker Compose and runs the tests; orderflow-engine-app is reserved; orderflow-engine-api is the deliverable.',
                'Source: SPEC §15 · ADR-0001')
    d.box(370, 84, 220, 60, 'orderflow-engine-docs', 'spec · contract · results', kind='key')
    d.box(690, 84, 220, 60, 'orderflow-engine-tools', 'generators · checks')
    d.box(50, 224, 220, 60, 'orderflow-engine-web', 'Angular · full order flow · nginx')
    d.box(370, 224, 220, 60, 'orderflow-engine-api', 'the deliverable · code · ADR', kind='key')
    d.box(690, 224, 220, 60, 'orderflow-engine-infra', 'full-stack compose · test-all')
    d.box(50, 360, 220, 56, 'orderflow-engine-app', 'reserved · not built', kind='muted')
    d.edge([(690, 114), (593, 114)]); d.label(640, 106, 'generates')
    d.edge([(480, 144), (480, 221)])
    d.edge([(430, 144), (430, 184), (160, 184), (160, 221)])
    d.edge([(530, 144), (530, 184), (800, 184), (800, 221)])
    d.label(300, 176, 'specifies')
    d.label(665, 176, 'specifies')
    d.label(488, 206, 'specifies', anchor='start')
    d.edge([(270, 254), (367, 254)]); d.label(320, 246, 'API contract')
    d.edge([(690, 254), (593, 254)]); d.label(640, 246, 'runs tests')
    d.edge([(800, 284), (800, 322), (160, 322), (160, 287)]); d.label(480, 314, 'runs tests')
    d.note(330, 352, 600, 72, 'Why separate repositories',
           ['orderflow-engine-api stands alone as the deliverable: code, tests, single command, README and ADR.',
            'Generators live in tools; their results and the specification live once, in docs.'])
    return d


def fig03():
    d = Diagram('03-ports-and-adapters', 1120, 520,
                'Ports and adapters: the service is cut at its boundaries',
                'Driving side on the left, driven side on the right; use cases see only ports, never adapters',
                'Ports and adapters: REST controllers and scheduled jobs drive inbound ports implemented by the quoting, '
                'ordering and outbox use cases, which use the pure pricing domain and outbound ports; the JDBC adapter, '
                'the fake push gateway and the fake ERP publisher implement those outbound ports.',
                'Source: SPEC §12 · architecture.md §2')
    for x, label in [(40, 'Driving adapters'), (270, 'Inbound ports'), (510, 'Application core'),
                     (790, 'Outbound ports'), (980, 'Driven adapters')]:
        d.text(x, 92, label, 11, 600, anchor='start', cls='keyt')
    d.box(40, 130, 170, 56, 'REST controllers', 'quotes · orders · products')
    d.box(40, 300, 170, 56, 'Scheduled jobs', 'relay · housekeeping')
    d.rect(270, 110, 180, 270, 'node', rid='inbound')
    for i, s in enumerate(['CreateQuote', 'GetQuote · ListProducts', 'ConfirmOrder', 'GetOrder · ListOrders',
                           'RelayOutbox', 'Housekeep']):
        d.text(360, 140 + i * 42, s, 11.5, 600, cls='t')
    d.group(500, 110, 240, 270, 'use cases implement the ports', kind='group')
    d.box(520, 140, 200, 40, 'quoting', kind='node', size=11.5)
    d.box(520, 192, 200, 40, 'ordering', kind='node', size=11.5)
    d.box(520, 244, 200, 40, 'outbox', kind='node', size=11.5)
    d.box(520, 310, 200, 52, 'pricing.domain', 'pure · used by quoting', kind='key')
    d.rect(790, 110, 160, 160, 'node', rid='persistence ports')
    for i, s in enumerate(['QuoteRepository', 'OrderRepository', 'CreditLedger', 'IdempotencyStore',
                           'OutboxRepository']):
        d.text(870, 138 + i * 28, s, 11.5, 600, cls='t')
    d.box(790, 290, 160, 40, 'PushNotificationPort', size=11)
    d.box(790, 342, 160, 40, 'ErpPublisherPort', size=11)
    d.box(980, 162, 120, 56, 'JDBC adapter', '→ PostgreSQL')
    d.box(980, 290, 120, 40, 'Fake push', size=11.5)
    d.box(980, 342, 120, 40, 'Fake ERP', size=11.5)
    d.edge([(210, 158), (267, 158)]); d.label(238, 150, 'HTTP')
    d.edge([(210, 328), (267, 328)]); d.label(238, 320, 'timer')
    d.edge([(450, 245), (497, 245)])
    d.edge([(740, 190), (787, 190)]); d.label(763, 182, 'uses')
    d.edge([(740, 310), (787, 310)])
    d.edge([(740, 362), (787, 362)])
    d.edge([(950, 190), (977, 190)])
    d.edge([(950, 310), (977, 310)])
    d.edge([(950, 362), (977, 362)])
    d.note(270, 410, 830, 70, 'One place knows both sides',
           ['config wires every port to its adapter. Swapping the fake push gateway for a real one changes one '
            'binding,', 'and no use case or domain class.'])
    return d


def fig04():
    d = Diagram('04-dependency-rule', 960, 360,
                'Dependency rule: source dependencies point inward',
                'The domain imports only the JDK; a dependency in the other direction fails the build',
                'Dependency rule: adapters depend on the application layer, which depends on the domain; the domain '
                'never depends on adapters, and ArchUnit tests fail the build if it does.',
                'Source: constitution P-05, P-06 · DomainPurityArchTest, TransactionBoundaryArchTest')
    d.box(40, 120, 240, 96, 'Adapters', 'web · persistence · push · erp', 'Spring, JDBC, HTTP allowed')
    d.box(360, 120, 240, 96, 'Application', 'use cases + ports', '@Transactional lives here only')
    d.box(680, 120, 240, 96, 'Domain', 'pricing.domain', 'JDK only · no float, no double', kind='key')
    d.edge([(280, 168), (357, 168)]); d.label(318, 160, 'depends on')
    d.edge([(600, 168), (677, 168)]); d.label(638, 160, 'depends on')
    d.edge([(800, 216), (800, 262), (160, 262), (160, 219)], kind='bad', dashed=True)
    d.label(480, 278, 'forbidden: domain → application or adapters — the ArchUnit rule fails the build', cls='badt')
    d.group(40, 76, 880, 30, '', kind='muted')
    d.text(480, 96, 'config · composition root — the only module that knows every layer and wires ports to adapters',
           10.5)
    return d


def fig05():
    d = Diagram('05-pricing-pipeline', 1010, 430,
                'Pricing pipeline: the order in which levers apply',
                'A pure function price(cart, snapshot) → breakdown; amber steps are the only rounding points',
                'Pricing pipeline: normalize the cart, check gift eligibility, apply combos, apply tier discounts to the '
                'remaining units, compute line net, taxable base and tax per line, then the total; credit is evaluated '
                'afterwards in the application layer. Rounding happens only at line discounts and line tax.',
                'Source: SPEC BR-01 … BR-05, §4')
    xs = [40, 290, 540, 790]
    top = [('0 · Normalize', 'merge duplicate SKUs', 'sort by SKU code', 'node'),
           ('1 · Gift eligibility', 'paid quantities and', 'gross before discounts', 'node'),
           ('2 · Combos', 'consume units first', 'one COMBO entry each', 'node'),
           ('3 · Tiers', 'marginal brackets on', 'units no combo consumed', 'node')]
    bottom = [('7 · Total', 'Σ net + taxes charged', 'never re-rounded (RP-5)', 'node'),
              ('6 · Tax per line', 'base × SKU rate', 'rounded per line (RP-4)', 'warn'),
              ('5 · Taxable base', 'net + gift reference', 'value, per gift policy', 'node'),
              ('4 · Line net', 'discounts rounded per', 'line (RP-2); net exact', 'warn')]
    for x, (t, a, b, k) in zip(xs, top):
        d.box(x, 90, 180, 74, t, a, b, kind=k)
    for x, (t, a, b, k) in zip(xs, bottom):
        d.box(x, 230, 180, 74, t, a, b, kind=k)
    for x, s in zip([220, 470, 720], ['cart', 'gift lines', 'units left']):
        d.edge([(x, 127), (x + 67, 127)]); d.label(x + 35, 119, s)
    d.edge([(880, 164), (880, 227)]); d.label(888, 200, 'line discounts', anchor='start')
    for x, s in zip([790, 540, 290], ['net', 'base', 'tax']):
        d.edge([(x, 267), (x - 67, 267)]); d.label(x - 35, 259, s)
    d.rect(40, 334, 930, 36, 'muted', rx=8, rid='credit bar')
    d.text(505, 357, '8 · Credit evaluation runs outside the engine, in the application layer: advisory at quote, '
           'enforced at confirmation', 10.5)
    d.rect(40, 386, 14, 14, 'warn', rx=3, obstacle=False)
    d.text(62, 397, 'rounding point: currency scale and rounding mode come from the country', 10.5, anchor='start')
    return d


def fig06():
    d = Diagram('06-quote-sequence', 1160, 660,
                'Quote: the price is computed once and sealed',
                'Prices and levers are read at time T; the engine is pure; the stored lines are never updated',
                'Quote sequence: the client posts a cart; the use case normalizes it, loads the snapshot, calls the pure '
                'engine and inserts the quote with its lines and discount components, then the controller returns 201.',
                'Source: SPEC §6 · api-contract E-01')
    xs = [100, 290, 490, 690, 880, 1060]
    heads = [('Client', 'shopkeeper app'), ('QuoteController', 'web adapter'), ('CreateQuoteUseCase', 'application'),
             ('SnapshotProvider', 'outbound port'), ('PricingEngine', 'pure domain'), ('QuoteRepository', 'outbound port')]
    for x, (t, s) in zip(xs, heads):
        d.lifeline(x, 74, 520, t, s, kind='key' if t == 'PricingEngine' else 'node')
    d.msg(xs[0], xs[1], 150, 'POST /api/v1/quotes')
    d.msg(xs[1], xs[2], 186, 'create(tenant, customer, cart)')
    d.self_msg(xs[2], 210, 'normalize cart (BR-00)')
    d.msg(xs[2], xs[3], 270, 'load prices, levers, rates, policy')
    d.msg(xs[3], xs[2], 306, 'snapshot at time T', ret=True)
    d.msg(xs[2], xs[4], 342, 'price(cart, snapshot)')
    d.msg(xs[4], xs[2], 378, 'breakdown', ret=True)
    d.msg(xs[2], xs[5], 414, 'insert quote · lines · adjustments')
    d.msg(xs[2], xs[1], 450, 'quote', ret=True)
    d.msg(xs[1], xs[0], 486, '201 · breakdown · credit', ret=True)
    d.note(40, 540, 340, 86, 'Pure and deterministic',
           ['The engine does no I/O, so the same snapshot always', 'gives the same breakdown; the golden tests pin', 'its output.'])
    d.note(410, 540, 340, 86, 'Insert-only',
           ['Quote rows are never updated. The order will', 'point at these lines and store no amount, so', 'every figure exists exactly once.'])
    d.note(780, 540, 340, 86, 'Credit is advisory here',
           ['The quote reports fits, available and shortfall,', 'but reserves nothing; the limit is enforced', 'when the order is confirmed.'])
    return d


def fig07():
    d = Diagram('07-confirm-transaction', 1160, 820,
                'Confirmation: one transaction, and the reply only after commit',
                'Locks are always taken in the same order: idempotency key → quote → credit account',
                'Confirmation sequence: within one transaction the use case inserts the idempotency key, locks and '
                'validates the quote, consumes credit, inserts the order and the outbox events and stores the response; '
                'the controller returns 201 only after COMMIT; later the relay claims events and calls push and the ERP '
                'outside any transaction.',
                'Source: SPEC §7 · data-model §8 · api-contract E-03')
    xs = [100, 290, 500, 820, 1050]
    heads = [('Client', 'shopkeeper app'), ('OrderController', 'web adapter'), ('ConfirmOrderUseCase', 'application'),
             ('PostgreSQL', 'single source of truth'), ('OutboxRelay', 'scheduled job')]
    for x, (t, s) in zip(xs, heads):
        d.lifeline(x, 74, 690, t, s, kind='key' if t == 'ConfirmOrderUseCase' else 'node')
    d.msg(xs[0], xs[1], 150, 'POST /orders · Idempotency-Key')
    d.msg(xs[1], xs[2], 186, 'confirm(quoteId, key)')
    d.rect(420, 204, 490, 268, 'tx', rx=10, obstacle=False)
    d.text(436, 224, 'BEGIN — one ACID transaction', 11, 600, anchor='start', cls='txt')
    steps = ['1 · insert idempotency key, on conflict do nothing', '2 · select quote for update · no order, not expired',
             '3 · conditional credit update (CREDIT only)', '4 · insert order row, then the ledger row',
             '5 · insert outbox events: PUSH, ERP', '6 · store order id and response on the key']
    for i, s in enumerate(steps):
        d.msg(xs[2], xs[3], 254 + 34 * i, s)
    d.msg(xs[2], xs[3], 458, '7 · COMMIT', kind='txe', weight=600, cls='txt')
    d.msg(xs[2], xs[1], 504, 'order (committed)', ret=True)
    d.msg(xs[1], xs[0], 540, '201 Created · Location', ret=True, weight=600, cls='t')
    d.add('<line class="life" x1="40" y1="566" x2="1120" y2="566" stroke="#94a3b8" stroke-width="1" stroke-dasharray="2 4"/>')
    d.label(580, 584, 'Later, asynchronously', cls='keyt', weight=600, size=11)
    d.msg(xs[4], xs[3], 616, 'claim due events with a lease', ret=False)
    d.self_msg(xs[4], 636, 'call push / ERP', side='left')
    d.msg(xs[4], xs[3], 682, 'mark SENT · or retry · or DEAD')
    d.note(40, 706, 340, 70, 'I-201',
           ['The 201 is serialized only after COMMIT returns,', 'so every order number points to a committed row.'])
    d.note(410, 706, 340, 70, 'Failures are not cached',
           ['Any error rolls back everything, including the key;', 'the client can fix the cause and retry.'])
    d.note(780, 706, 340, 70, 'At-least-once effects',
           ['A crash after the call re-sends after the lease;', 'consumers dedupe by event_id.'])
    return d


def fig08():
    d = Diagram('08-data-model', 1160, 680,
                'Data model: 19 tables in third normal form, no JSON',
                'Arrows point from the referencing table to the referenced one; amber labels are UNIQUE constraints',
                'Data model: reference tables (currencies, countries, tenants), tenant catalog and levers, credit, '
                'insert-only quotes with lines and discount components, thin orders that reference their quote and store '
                'no amount, idempotency keys and outbox events.',
                'Source: data-model.md · Liquibase changelogs in orderflow-engine-api')
    cols = [(40, 'Reference, tenancy, credit'), (310, 'Catalog and levers'), (600, 'Quotes and orders'),
            (900, 'Idempotency and effects')]
    for x, label in cols:
        d.group(x - 14, 70, 248, 500, label)
    W = 220
    d.box(40, 104, W, 56, 'currencies', 'code · scale')
    d.box(40, 190, W, 56, 'countries', 'currency · rounding · gift · TTL')
    d.box(40, 276, W, 56, 'tenants', 'UNIQUE (country, brand)')
    d.box(40, 362, W, 56, 'customers', 'PK (tenant_id, id)')
    d.box(40, 448, W, 56, 'credit_accounts', 'CHECK consumed ≤ limit', kind='key')
    d.box(310, 104, W, 56, 'families', 'PK (tenant_id, code)')
    d.box(310, 190, W, 56, 'products', 'sku · name · tax_rate · list_price')
    d.box(310, 276, W, 56, 'tier_rules · tier_brackets', 'SKU or family target')
    d.box(310, 362, W, 56, 'combo_rules · combo_items', 'combo price · min quantities')
    d.box(310, 448, W, 56, 'gift_rules', 'trigger · gift product · qty')
    d.box(600, 104, W, 56, 'quotes', 'customer · currency · expires_at', kind='key')
    d.box(600, 190, W, 56, 'quote_lines', 'unit_price · tax_rate · base · tax', kind='key')
    d.box(600, 276, W, 56, 'quote_line_adjustments', 'kind TIER | COMBO · rule_id', kind='key')
    d.box(600, 390, W, 64, 'orders', 'number · confirmed_at', 'no breakdown amounts', kind='key')
    d.box(600, 490, W, 56, 'credit_ledger', 'amount · append-only', kind='key')
    d.box(900, 104, W, 64, 'idempotency_keys', 'PK (tenant, customer, key)', 'request_hash · response')
    d.box(900, 236, W, 84, 'outbox_events', 'UNIQUE (order, destination)', 'PENDING · SENT · DEAD', 'attempts · lease')
    # reference chain
    d.edge([(150, 190), (150, 163)]); d.label(158, 181, 'currency_code', anchor='start')
    d.edge([(150, 276), (150, 249)]); d.label(158, 267, 'country_code', anchor='start')
    d.edge([(150, 448), (150, 421)]); d.label(158, 439, 'customer_id', anchor='start')
    # catalog
    d.edge([(420, 190), (420, 163)]); d.label(428, 181, 'family_code', anchor='start')
    d.edge([(530, 304), (550, 304), (550, 232), (533, 232)])
    d.edge([(530, 390), (550, 390), (550, 304)], arrow=False)
    d.edge([(530, 476), (550, 476), (550, 390)], arrow=False)
    d.label(546, 440, 'product_id', anchor='end')
    # quotes and orders
    d.edge([(600, 206), (533, 206)]); d.label(566, 198, 'product_id')
    d.edge([(710, 190), (710, 163)]); d.label(718, 181, 'quote_id', anchor='start')
    d.edge([(710, 276), (710, 249)]); d.label(718, 267, 'quote_id · line_no', anchor='start')
    d.edge([(820, 402), (840, 402), (840, 132), (823, 132)])
    d.label(834, 368, 'quote_id · UNIQUE', anchor='end', cls='warnt', weight=600)
    d.edge([(710, 490), (710, 457)]); d.label(718, 481, 'order_id · UNIQUE', anchor='start', cls='warnt', weight=600)
    # idempotency and outbox
    d.edge([(900, 150), (870, 150), (870, 424), (823, 424)]); d.label(875, 210, 'order_id', anchor='start')
    d.edge([(900, 300), (885, 300), (885, 446), (823, 446)]); d.label(890, 345, 'order_id', anchor='start')
    d.text(40, 600, 'Every tenant-scoped table is keyed by (tenant_id, id) and references tenants (not drawn). quotes and orders '
           'reference customers; the order FK pins customer_id to its quote.', 10.5, anchor='start')
    d.text(40, 620, 'The order stores no breakdown amount: its lines are the quote lines, so quote and order cannot diverge.',
           10.5, anchor='start')
    return d


def fig09():
    d = Diagram('09-outbox-lifecycle', 1000, 470,
                'Outbox lifecycle: at-least-once delivery, consumers deduplicate',
                'Status is PENDING, SENT or DEAD; a lease (locked_until) marks the event being sent',
                'Outbox lifecycle: an event is written as PENDING in the order transaction; the relay leases it with '
                'FOR UPDATE SKIP LOCKED; success sets SENT; a retryable failure or an expired lease leaves it PENDING with '
                'backoff; a non-retryable failure or the last attempt sets DEAD; operations can requeue a DEAD event.',
                'Source: SPEC §7.4 · data-model §5')
    d.add('<circle class="ea" cx="62" cy="190" r="8" fill="#475569"/>')
    d.box(140, 162, 180, 56, 'PENDING', 'waits for next_attempt_at')
    d.box(450, 162, 180, 56, 'PENDING · leased', 'locked_until > now', kind='key')
    d.box(770, 162, 180, 56, 'SENT', 'delivered', kind='tx')
    d.box(450, 330, 180, 56, 'DEAD', 'counted in outbox_dead', kind='bad')
    d.edge([(70, 190), (137, 190)]); d.label(40, 136, 'written in the', anchor='start'); d.label(40, 150, 'order transaction', anchor='start')
    d.edge([(320, 182), (447, 182)]); d.label(384, 174, 'claim · SKIP LOCKED')
    d.edge([(630, 190), (767, 190)]); d.label(698, 182, 'gateway OK → SENT')
    d.edge([(540, 162), (540, 118), (230, 118), (230, 159)], dashed=True)
    d.label(385, 110, 'retryable failure or expired lease · attempts + 1 · backoff with jitter')
    d.edge([(540, 218), (540, 327)]); d.label(548, 276, 'non-retryable error', anchor='start'); d.label(548, 290, 'or last attempt', anchor='start')
    d.edge([(450, 358), (230, 358), (230, 221)], dashed=True); d.label(340, 350, 'manual requeue (operations)')
    d.note(680, 300, 280, 104, 'Why nothing is lost or duplicated',
           ['The call happens under the lease, outside', 'any database transaction. A crash re-sends', 'after the lease; consumers dedupe by', 'event_id (push collapse id, ERP upsert).'])
    return d


FIGURES = [fig01, fig02, fig03, fig04, fig05, fig06, fig07, fig08, fig09]

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2] / 'orderflow-engine-docs' / 'diagrams')
    total = 0
    for f in FIGURES:
        d = f()
        problems = d.check()
        total += len(problems)
        with open(os.path.join(out, d.name + '.svg'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(d.render())
        print(f'{d.name}: {"OK" if not problems else str(len(problems)) + " problem(s)"}')
        for p in problems:
            print('   -', p)
    sys.exit(1 if total else 0)
