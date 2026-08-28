#!/usr/bin/env python3
"""Validate compound recipes against component descriptors and event contracts."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); p.add_argument('--report',type=Path); a=p.parse_args(); root=a.root.resolve(); reg={}
 for f in (root/'components').rglob('*.component.json'):
  x=json.loads(f.read_text()); reg[x['id']]=x
 errors=[]; validated=[]
 for f in sorted((root/'compounds').glob('*.compound.json')):
  x=json.loads(f.read_text()); validated.append(x.get('id',str(f))); members=[m.get('id') for m in x.get('components',[]) if isinstance(m,dict)]
  for cid in members:
   c=reg.get(cid)
   if not c: errors.append(f'{f}: unknown component {cid}')
   elif x.get('targetPlatform') not in c['platform'] and 'agnostic' not in c['platform']: errors.append(f'{f}: unsupported platform {cid}')
  for w in x.get('connections',[]):
   s,t,e=w.get('from'),w.get('to'),w.get('event')
   if s not in members: errors.append(f'{f}: source {s} not member'); continue
   if t not in members: errors.append(f'{f}: target {t} not member'); continue
   if e not in reg.get(s,{}).get('events',{}).get('emits',[]): errors.append(f'{f}: {s} does not emit {e}')
   if e not in reg.get(t,{}).get('events',{}).get('listensTo',[]): errors.append(f'{f}: {t} does not listen to {e}')
  for cid in x.get('criticalComponents',[]):
   if cid not in members: errors.append(f'{f}: critical {cid} not member')
 report={'status':'PASS' if not errors else 'FAIL','compoundCount':len(validated),'validatedCompounds':validated,'errors':errors}
 if a.report: a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2)); return 0 if not errors else 1
if __name__=='__main__':
 try: raise SystemExit(main())
 except (OSError,ValueError,json.JSONDecodeError) as e: print(f'Compound validation failed: {e}',file=sys.stderr); raise SystemExit(1)
