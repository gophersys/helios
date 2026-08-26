#!/usr/bin/env python3
"""Determinism measurement: N independent (pir.yaml, scorecard.yaml) pairs
-> per-field agreement matrix + overall rates. Pure comparison, no judgment."""
import sys, yaml, json
from pathlib import Path
from collections import Counter

def norm_set(v):
    if v is None: return frozenset()
    if isinstance(v, (list, tuple)): return frozenset(str(x).strip().lower() for x in v)
    return frozenset([str(v).strip().lower()])

def norm_scalar(v):
    return str(v).strip().lower() if v is not None else "(none)"

def load(d):
    pir = yaml.safe_load(open(Path(d)/"pir.yaml"))
    sc  = yaml.safe_load(open(Path(d)/"scorecard.yaml"))
    return pir, sc

def pir_features(p):
    env = p.get("environment") or {}
    phy = p.get("physical") or {}
    comp = p.get("compliance") or {}
    tgt = p.get("targets") or {}
    feats = {
      "power_class": norm_scalar(p.get("power_class")),
      "env.where": norm_scalar(env.get("where")),
      "env.conditions": norm_set(env.get("conditions")),
      "env.on_body": norm_scalar(env.get("on_body")),
      "phys.size_class": norm_scalar(phy.get("size_class")),
      "phys.carry": norm_scalar(phy.get("carry")),
      "phys.controls": norm_scalar(phy.get("controls")),
      "comp.regions": norm_set(comp.get("regions")),
      "comp.safety": norm_scalar(comp.get("safety")),
      "comp.personal_data": norm_set(comp.get("personal_data")),
      "comp.certifications": norm_set(comp.get("certifications")),
      "constraints": frozenset(f'{norm_scalar((c or {}).get("tech"))}:{norm_scalar((c or {}).get("strength"))}'
                               for c in (p.get("constraints") or [])),
      "unknown_fields": norm_set([ (u or {}).get("field") for u in (p.get("unknowns") or []) ]),
      "volume.y1": norm_scalar((tgt.get("volume") or {}).get("y1") if isinstance(tgt.get("volume"), dict) else tgt.get("volume")),
      "assets": norm_set(p.get("assets")),
      "fn.capabilities": frozenset(Counter(norm_scalar((f or {}).get("capability"))
                               for f in (p.get("functions") or [])).keys()),
    }
    return feats

def sc_features(s):
    feats = {}
    for row in (s.get("scores") or []):
        feats[f'score.{row.get("id")}'] = norm_scalar(row.get("score"))
    d = s.get("derived") or {}
    feats["derived.needs_hardware"] = norm_scalar(d.get("needs_hardware"))
    feats["derived.needs_firmware"] = norm_scalar(d.get("needs_firmware"))
    feats["human_gates"] = norm_set(s.get("human_gates"))
    feats["verdict"] = norm_scalar((s.get("recommendation") or {}).get("verdict"))
    return feats

def main(dirs):
    names = [Path(d).name for d in dirs]
    rows = {}
    for d, n in zip(dirs, names):
        pir, sc = load(d)
        f = {**pir_features(pir), **sc_features(sc)}
        for k, v in f.items():
            rows.setdefault(k, {})[n] = v
    keys = sorted(rows)
    unanimous = 0; total = 0
    print(f"{'field':38s} " + " ".join(f"{n:>10s}" for n in names) + "  agree")
    print("─" * (38 + 11*len(names) + 8))
    disagreements = []
    for k in keys:
        vals = [rows[k].get(n, "(missing)") for n in names]
        rend = []
        for v in vals:
            s = ",".join(sorted(v)) if isinstance(v, frozenset) else str(v)
            rend.append((s[:10]))
        def canon(v):
            return ",".join(sorted(v)) if isinstance(v, frozenset) else str(v)
        c = Counter(canon(v) for v in vals)
        agree = len(c) == 1
        total += 1; unanimous += agree
        mark = "✔" if agree else "✗"
        print(f"{k:38s} " + " ".join(f"{r:>10s}" for r in rend) + f"   {mark}")
        if not agree:
            disagreements.append((k, {n: (",".join(sorted(v)) if isinstance(v, frozenset) else str(v)) for n, v in zip(names, vals)}))
    print("─" * (38 + 11*len(names) + 8))
    score_keys = [k for k in keys if k.startswith("score.")]
    def canon2(v):
        return ",".join(sorted(v)) if isinstance(v, frozenset) else str(v)
    score_agree = sum(1 for k in score_keys if len(Counter(canon2(rows[k].get(n)) for n in names)) == 1)
    pir_keys = [k for k in keys if not k.startswith(("score.", "derived.", "verdict", "human_gates"))]
    pir_agree = sum(1 for k in pir_keys if len(Counter(canon2(rows[k].get(n)) for n in names)) == 1)
    print(f"OVERALL   unanimous {unanimous}/{total} = {100*unanimous/total:.1f}%")
    print(f"PIR       unanimous {pir_agree}/{len(pir_keys)} = {100*pir_agree/len(pir_keys):.1f}%")
    print(f"SCORES    unanimous {score_agree}/{len(score_keys)} = {100*score_agree/len(score_keys):.1f}%")
    vkey = Counter(str(rows.get('verdict', {}).get(n)) for n in names)
    print(f"VERDICT   {'UNANIMOUS' if len(vkey)==1 else 'SPLIT'}: {dict(vkey)}")
    json.dump({"disagreements": [{ "field": k, "values": v} for k, v in disagreements],
               "unanimous": unanimous, "total": total},
              open(Path(dirs[0]).parent/"analysis.json", "w"), indent=1)
    print(f"disagreement detail -> {Path(dirs[0]).parent/'analysis.json'}")

if __name__ == "__main__":
    main(sys.argv[1:])
