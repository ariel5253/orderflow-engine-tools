"""Checks that every count and code range stated in the docs matches what actually exists."""
import io
import os
import re
import sys
from pathlib import Path

R = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2])
def rd(p):
    return io.open(os.path.join(R, p), encoding='utf-8').read()

spec = rd('orderflow-engine-docs/spec/SPEC.md')
tasks = rd('orderflow-engine-docs/spec/TASKS.md')
plan = rd('orderflow-engine-docs/spec/plan.md')
contract = rd('orderflow-engine-docs/spec/api-contract.md')
model = rd('orderflow-engine-docs/spec/data-model.md')
const = rd('orderflow-engine-docs/spec/constitution.md')
rules = rd('orderflow-engine-docs/governance/documentation-rules.md')
handoff = rd('orderflow-engine-docs/handoff/HANDOFF.md')
readme = rd('orderflow-engine-docs/README.md')
diagrams = sorted(os.listdir(os.path.join(R, 'orderflow-engine-docs/diagrams')))

def ids(rx, text):
    return sorted(set(re.findall(rx, text, re.M)))

actual = {
    'tables (data-model §1-5)': len(set(re.findall(r'^\| `([a-z_]+)` \|', model.split('## 6.')[0], re.M))),
    'diagrams': len(diagrams),
    'tasks T-xx': len(ids(r'^### (T-\d\d):', tasks)),
    'ACs': len(ids(r'^\| (AC-\d\d) \|', spec)),
    'BR rules': len(ids(r'^### (BR-\d\d)', spec)),
    'assumptions A-xx': len(ids(r'^\| (A-\d\d) \|', spec)),
    'golden GT-xx': len(ids(r'^\| (GT-\d\d) \|', spec)),
    'principles P-xx': len(ids(r'^\| (P-\d\d) \|', const)),
    'decisions DEC-xx': len(ids(r'^\| (DEC-\d\d) \|', plan)),
    'risks RISK-xx': len(ids(r'^\| (RISK-\d\d) \|', plan)),
    'global constraints GC-x': len(ids(r'^\| (GC-\d) \|', tasks)),
    'review focus RF-x': len(ids(r'^\| (RF-\d) \|', tasks)),
    'operation cards E-xx': len(ids(r'^### (E-\d\d)', contract)),
    'doc rules DR-x': len(ids(r'^\| (DR-\d) \|', rules)),
}
for k, v in actual.items():
    print(f'  {k:28s} {v}')

print('== stated ranges vs actual')
claims = [
    ('README codes', r'`T-00`…`T-(\d\d)`', readme, int(ids(r'^### T-(\d\d):', tasks)[-1])),
    ('README codes', r'`AC-01`…`AC-(\d\d)`', readme, int(ids(r'^\| AC-(\d\d) \|', spec)[-1])),
    ('README codes', r'`P-01`…`P-(\d\d)`', readme, int(ids(r'^\| P-(\d\d) \|', const)[-1])),
    ('README codes', r'`A-01`…`A-(\d\d)`', readme, int(ids(r'^\| A-(\d\d) \|', spec)[-1])),
    ('README codes', r'`BR-00`…`BR-(\d\d)`', readme, int(ids(r'^### BR-(\d\d)', spec)[-1])),
    ('README codes', r'`GT-01`…`GT-(\d\d)`', readme, int(ids(r'^\| GT-(\d\d) \|', spec)[-1])),
    ('README codes', r'`E-01`…`E-(\d\d)`', readme, int(ids(r'^### E-(\d\d)', contract)[-1])),
    ('README codes', r'`DR-1`…`DR-(\d)`', readme, int(ids(r'^\| DR-(\d) \|', rules)[-1])),
    ('architecture risks', r'RISK-01…RISK-(\d\d)', rd('orderflow-engine-docs/spec/architecture.md'), int(ids(r'^\| RISK-(\d\d) \|', plan)[-1])),
    ('SPEC §8 cards', r'E-01…E-(\d\d)', spec, int(ids(r'^### E-(\d\d)', contract)[-1])),
]
for where, rx, text, real in claims:
    for m in re.findall(rx, text):
        status = 'OK ' if int(m) == real else 'BAD'
        print(f'  {status} {where}: states {m}, actual {real}')

print('== stated counts in prose')
for name, text in [('SPEC', spec), ('TASKS', tasks), ('HANDOFF', handoff), ('README', readme), ('data-model', model),
                   ('fig08', rd('orderflow-engine-docs/diagrams/08-data-model.svg'))]:
    for m in re.finditer(r'(\d+|nine|eight|five|four|two|six|seven) (tables|diagrams|figures|tasks|ACs|folders|repositories|golden tests)', text):
        print(f'  {name}: "{m.group(0)}"')
