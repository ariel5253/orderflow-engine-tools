"""Cross-reference check across the Orderflow Engine documents.

Compares test names, acceptance criteria, error codes, tables and endpoints between SPEC, TASKS, the API
contract, the data model, the READMEs and the ADR, and lists acceptance criteria that no assignment
requirement points to. Usage: python orderflow-engine-tools/consistency/cross_reference_check.py [workspace]
"""
import io
import re
import sys
from pathlib import Path

root = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2])
F = {
    'SPEC': 'orderflow-engine-docs/spec/SPEC.md',
    'TASKS': 'orderflow-engine-docs/spec/TASKS.md',
    'CONTRACT': 'orderflow-engine-docs/spec/api-contract.md',
    'MODEL': 'orderflow-engine-docs/spec/data-model.md',
    'PLAN': 'orderflow-engine-docs/spec/plan.md',
    'CONST': 'orderflow-engine-docs/spec/constitution.md',
    'ARCH': 'orderflow-engine-docs/spec/architecture.md',
    'HANDOFF': 'orderflow-engine-docs/handoff/HANDOFF.md',
    'README_API': 'orderflow-engine-api/README.md',
    'README_API_ES': 'orderflow-engine-api/README.es.md',
    'ADR': 'orderflow-engine-api/docs/adr/0001-order-pricing-and-confirmation.md',
    'ADR_ES': 'orderflow-engine-api/docs/adr/0001-order-pricing-and-confirmation.es.md',
}
T = {k: io.open(f'{root}/{v}', encoding='utf-8').read() for k, v in F.items()}


def find(rx, keys=None):
    out = {}
    for k in (keys or T):
        for m in re.findall(rx, T[k]):
            out.setdefault(m, set()).add(k)
    return out


print('== Test classes not listed in TASKS (where each test is created)')
tests = find(r'\b([A-Z][a-z][A-Za-z0-9]*(?:Test|IT))\b')
for name, where in sorted(tests.items()):
    if 'TASKS' not in where:
        print(f'  {name:40s} mentioned in {sorted(where)}')

print('== AC ids: defined in SPEC §14.2 vs covered by TASKS')
spec_acs = set(re.findall(r'^\| (AC-\d\d) \|', T['SPEC'], re.M))
task_acs = set()
for line in re.findall(r'\*\*Covers:\*\*([^\n]*)', T['TASKS']):
    for a, b in re.findall(r'AC-(\d\d)(?:\s*…\s*AC-(\d\d))?', line):
        lo = int(a); hi = int(b) if b else lo
        task_acs |= {f'AC-{i:02d}' for i in range(lo, hi + 1)}
print('  in SPEC, not covered by any task:', sorted(spec_acs - task_acs))
print('  covered by a task, not in SPEC  :', sorted(task_acs - spec_acs))

print('== AC rows: task column vs the task that covers them')
for ac, task_col in re.findall(r'^\| (AC-\d\d) \|[^|]*\|[^|]*\| ([^|]*) \|', T['SPEC'], re.M):
    tasks_in_spec = set(re.findall(r'T-\d\d', task_col))
    covering = set()
    for block in re.split(r'\n### ', T['TASKS']):
        m = re.match(r'(T-\d\d):', block)
        if not m:
            continue
        cov = re.search(r'\*\*Covers:\*\*([^\n]*)', block)
        if not cov:
            continue
        ids = set()
        for a, b in re.findall(r'AC-(\d\d)(?:\s*…\s*AC-(\d\d))?', cov.group(1)):
            lo = int(a); hi = int(b) if b else lo
            ids |= {f'AC-{i:02d}' for i in range(lo, hi + 1)}
        if ac in ids:
            covering.add(m.group(1))
    if tasks_in_spec and covering and not (tasks_in_spec & covering):
        print(f'  {ac}: SPEC says {sorted(tasks_in_spec)}, TASKS covers in {sorted(covering)}')
    if tasks_in_spec and not covering:
        print(f'  {ac}: SPEC says {sorted(tasks_in_spec)}, no task lists it')

print('== Error codes: SPEC §8 vs api-contract')
codes_spec = set(re.findall(r'`([A-Z][A-Z_]{3,})`', T['SPEC'].split('## 8. API contract')[1].split('## 9.')[0]))
codes_contract = set(re.findall(r'`([A-Z][A-Z_]{3,})`', T['CONTRACT']))
ignore = {'CASH', 'CREDIT', 'OPEN', 'CONFIRMED', 'EXPIRED', 'PUSH', 'ERP', 'TIER', 'COMBO', 'PENDING', 'SENT', 'DEAD'}
print('  only in SPEC §8   :', sorted(codes_spec - codes_contract - ignore))
print('  only in contract  :', sorted(codes_contract - codes_spec - ignore))
all_codes = set()
for k in T:
    all_codes |= set(re.findall(r'\b([A-Z]+(?:_[A-Z]+)+)\b', T[k]))
print('  codes anywhere not in SPEC §8:', sorted(c for c in all_codes - codes_spec - ignore
                                                  if any(w in c for w in ['QUOTE', 'ORDER', 'CREDIT', 'IDEMPOTENCY', 'CART', 'SKU', 'TENANT', 'CUSTOMER', 'VALIDATION', 'INVALID', 'INTERNAL'])))

print('== Tables: data-model vs mentions elsewhere')
model_tables = set(re.findall(r'^\| `([a-z_]+)` \|', T['MODEL'].split('## 6.')[0], re.M))
print('  data-model tables:', len(model_tables), sorted(model_tables))
mentioned = find(r'`([a-z]+_[a-z_]+)`')
suspects = {n: w for n, w in mentioned.items() if n.endswith('s') and n not in model_tables and 'MODEL' not in w}
for n, w in sorted(suspects.items()):
    print(f'  snake_case plural not in model: {n:28s} {sorted(w)}')

print('== Endpoints')
eps = find(r'((?:GET|POST) /api/v1/[a-z{}/?=&A-Za-z]+)')
for e, w in sorted(eps.items()):
    print(f'  {e:45s} {sorted(w)}')

print('== Reverse traceability: ACs that no assignment requirement (SPEC 14.1) points to')
sec = T['SPEC'].split('### 14.1')[1].split('### 14.2')[0]
traced = set()
for a, b in re.findall(r'AC-(\d\d)(?:\s*…\s*AC-(\d\d))?', sec):
    lo = int(a); hi = int(b) if b else lo
    traced |= {f'AC-{i:02d}' for i in range(lo, hi + 1)}
rows = dict(re.findall(r'^\| (AC-\d\d) \| ([^|]*)\|', T['SPEC'], re.M))
untraced = sorted(set(rows) - traced)
print(f'  ACs total: {len(rows)}  traced to a REQ: {len(set(rows) & traced)}  untraced: {len(untraced)}')
for ac in untraced:
    print(f'  {ac}: {rows[ac].strip()}')

beyond = T['SPEC'].split('### 14.3')[1] if '### 14.3' in T['SPEC'] else ''
justified = set(re.findall(r'AC-\d\d', beyond))
missing = [ac for ac in untraced if ac not in justified]
print(f'  untraced but not justified in SPEC 14.3: {missing if missing else "none"}')
