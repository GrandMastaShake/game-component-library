#!/usr/bin/env python3
"""Validate compound recipes against component descriptors and event contracts.

Two of these checks exist because the wiring loop below reads
`compound["connections"]` through `.get(..., [])`, and a compound that spells
that key differently therefore has NO wires rather than bad ones. Two compounds
were written with a `wiring` key instead. Both validated clean, both were
reported in the wire total as contributing zero, and one of them reached `main`
that way -- missing a field `compound.schema.json` marks required, with fifteen
connections between them that nothing had ever looked at.

So the shape is checked before the contents: a compound must carry every key the
schema requires, and must not carry keys the schema does not define. The second
half is the one that catches a rename, and a default of `[]` for a required
field is exactly the kind of guard that hides the finding worth having.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def load_json(path):
    with path.open(encoding="utf-8") as f: return json.load(f)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--report",type=Path); args=parser.parse_args()
    components={}; errors=[]
    for path in sorted((ROOT/"components").rglob("*.component.json")):
        try: component=load_json(path)
        except (OSError,json.JSONDecodeError) as exc: errors.append(f"{path.relative_to(ROOT)}: invalid JSON ({exc})"); continue
        cid=component.get("id")
        if not isinstance(cid,str) or not cid: errors.append(f"{path.relative_to(ROOT)}: missing string id")
        elif cid in components: errors.append(f"duplicate component id: {cid}")
        else: components[cid]=component
    for cid,c in components.items():
        emits=set(c.get("events",{}).get("emits",[])); intents=c.get("eventIntents",{}); sink=c.get("sinkFor",[])
        if not isinstance(intents,dict): errors.append(f"{cid}: eventIntents must be an object"); continue
        if not isinstance(sink,list) or not all(isinstance(x,str) and x for x in sink): errors.append(f"{cid}: sinkFor must be an array of non-empty strings")
        for event,values in intents.items():
            if event not in emits: errors.append(f"{cid}: eventIntents declares non-emitted event {event}")
            if not isinstance(values,list) or not values or not all(isinstance(x,str) and x for x in values): errors.append(f"{cid}: eventIntents[{event}] must be a non-empty string array")
    compounds=[]
    for path in sorted((ROOT/"compounds").glob("*.compound.json")):
        try: compounds.append((path,load_json(path)))
        except (OSError,json.JSONDecodeError) as exc: errors.append(f"{path.relative_to(ROOT)}: invalid JSON ({exc})")
    # Shape before contents. The schema is the authority on which keys exist;
    # reading it here means a key added there is enforced without touching this.
    try:
        schema=load_json(ROOT/"compound.schema.json")
        allowed=set(schema.get("properties",{})); required=list(schema.get("required",[]))
    except (OSError,json.JSONDecodeError) as exc:
        errors.append(f"compound.schema.json: unreadable ({exc})"); allowed=set(); required=[]
    for path,compound in compounds:
        label=compound.get("id",path.stem)
        for key in required:
            if key not in compound: errors.append(f"{label}: missing required key '{key}' (compound.schema.json)")
        if allowed:
            for key in sorted(set(compound)-allowed):
                errors.append(f"{label}: unknown key '{key}' — compound.schema.json defines {sorted(allowed)}")

    wires=[]
    for path,compound in compounds:
        label=compound.get("id",path.stem); members={x.get("id") for x in compound.get("components",[]) if isinstance(x,dict)}
        for member in sorted(members):
            if member not in components: errors.append(f"{label}: missing component {member}")
        for wire in compound.get("connections",[]):
            if not isinstance(wire,dict): errors.append(f"{label}: connection must be an object"); continue
            source_id,target_id,event=wire.get("from"),wire.get("to"),wire.get("event"); prefix=f"{label}: {source_id} --{event}--> {target_id}"
            if source_id not in members or target_id not in members: errors.append(f"{prefix}: endpoint not declared in compound"); continue
            source,target=components.get(source_id),components.get(target_id)
            if source is None or target is None: continue
            if event not in source.get("events",{}).get("emits",[]): errors.append(f"{prefix}: source does not emit event"); continue
            if event in target.get("events",{}).get("listensTo",[]): mode="exact"
            else:
                shared=sorted(set(source.get("eventIntents",{}).get(event,[])) & set(target.get("sinkFor",[])))
                if not shared: errors.append(f"{prefix}: target neither listens exactly nor declares a matching sink intent"); continue
                mode="intent:"+",".join(shared)
            wires.append({"compound":label,"from":source_id,"to":target_id,"event":event,"acceptedBy":mode})
    report={"status":"PASS" if not errors else "FAIL","compoundCount":len(compounds),"componentCount":len(components),"validatedWires":wires,"errors":errors}
    if args.report: args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"validate_compounds: {report['status']} ({len(compounds)} compounds, {len(wires)} wires, {len(errors)} errors)")
    for error in errors: print(f"ERROR: {error}")
    return 0 if not errors else 1
if __name__=="__main__": sys.exit(main())
