#!/usr/bin/env python3
"""Shuffles the 40 answers under random ids (blind_map.json holds the mapping; do not open it while scoring)
and prints a batch with the key points, no arm label. Usage: python blind.py <batch 0-3>"""
import json, random, sys
from pathlib import Path
H = Path(__file__).resolve().parent
panel = {q["id"]: q for q in json.loads((H / "panel.json").read_text(encoding="utf-8"))["questions"]}
mp = H / "blind_map.json"
if not mp.exists():
    items = [(a, i) for a in "AB" for i in panel]
    random.Random(20261124).shuffle(items)
    mp.write_text(json.dumps({f"R{n+1:02d}": {"arm": a, "id": i} for n, (a, i) in enumerate(items)}, indent=1), encoding="utf-8")
m = json.loads(mp.read_text(encoding="utf-8"))
b = int(sys.argv[1])
for rid in sorted(m)[b * 10:(b + 1) * 10]:
    q = panel[m[rid]["id"]]
    ans = (H / "answers" / m[rid]["arm"] / f"{q['id']}.md").read_text(encoding="utf-8")
    q_short = q["question"] if len(q["question"]) < 400 else q["question"][:200] + " ...[file pasted]... " + q["question"][-200:]
    print(f"=========== {rid}  (question {q['id']})\nQ: {q_short}\nKEY:")
    for p in q["keyPoints"]:
        print(f"  {p['n']}. {p['text']}")
    print("WRONG:", " | ".join(q["wrong"]))
    print("--- ANSWER\n" + ans + "\n")
