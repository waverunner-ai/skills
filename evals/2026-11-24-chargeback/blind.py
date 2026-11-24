#!/usr/bin/env python3
"""Shuffles the 40 answers under random ids (blind_map.json holds the mapping; the scorer never sees it) and writes
blind/<id>.json with the question, the key and the answer, no arm label. Usage: python blind.py"""
import json, random
from pathlib import Path
H = Path(__file__).resolve().parent
panel = {q["id"]: q for q in json.loads((H / "panel.json").read_text(encoding="utf-8"))["questions"]}
mp = H / "blind_map.json"
if not mp.exists():
    items = [(a, i) for a in "AB" for i in panel]
    random.Random(20261124).shuffle(items)
    mp.write_text(json.dumps({f"R{n+1:02d}": {"arm": a, "id": i} for n, (a, i) in enumerate(items)}, indent=1), encoding="utf-8")
m = json.loads(mp.read_text(encoding="utf-8"))
(H / "blind").mkdir(exist_ok=True)
for rid, v in m.items():
    q = panel[v["id"]]
    ans = (H / "answers" / v["arm"] / f"{q['id']}.md").read_text(encoding="utf-8")
    (H / "blind" / f"{rid}.json").write_text(json.dumps({
        "rid": rid, "question": q["question"], "key_points": [p["text"] for p in q["key_points"]],
        "wrong_if": q["wrong_if"], "answer": ans}, indent=1, ensure_ascii=False), encoding="utf-8")
print(len(m), "blind files")
