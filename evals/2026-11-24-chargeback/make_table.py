#!/usr/bin/env python3
"""Joins scoring_blind.json with blind_map.json (arm labels restored only here), writes scores.csv and table.md:
the totals for all 20 questions and for the 18 without the two extension questions, and the per-question table."""
import csv, json
from pathlib import Path
H = Path(__file__).resolve().parent
panel = {q["id"]: q for q in json.load(open(H / "panel.json", encoding="utf-8"))["questions"]}
S = json.load(open(H / "scoring_blind.json", encoding="utf-8"))
M = json.load(open(H / "blind_map.json", encoding="utf-8"))
rows = []
for rid, m in M.items():
    s, q = S[rid], panel[m["id"]]
    rows.append({"arm": m["arm"], "id": m["id"], "group": q["group"], "scope": q["scope"], "blind_id": rid,
                 "points_met": sum(s["points"]), "points_possible": len(s["points"]),
                 "point_flags": "".join(map(str, s["points"])), "wrong": s["wrong"], "invented": s["invented"],
                 "unsupported": s["unsupported"], "verdict": s["verdict"], "note": s.get("note", "")})
order = list(panel)
rows.sort(key=lambda r: (order.index(r["id"]), r["arm"]))
with open(H / "scores.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def tot(arm, scopes):
    rs = [r for r in rows if r["arm"] == arm and r["scope"] in scopes]
    return (sum(r["points_met"] for r in rs), sum(r["points_possible"] for r in rs), sum(r["wrong"] for r in rs),
            sum(r["invented"] for r in rs), sum(r["unsupported"] for r in rs), sum(r["verdict"] for r in rs), len(rs))

out = ["| Set | Arm | Key points met | Wrong | Invented (not in key) | Not on the site either | Verdict |", "| --- | --- | --- | --- | --- | --- | --- |"]
for label, sc in (("All 20 questions", ("core", "extension")), ("18 core questions", ("core",))):
    for arm, name in (("A", "A, no skill"), ("B", "B, with skill")):
        m, p, w, i, u, v, n = tot(arm, sc)
        out.append(f"| {label} | {name} | {m} of {p} ({round(100*m/p)}%) | {w} of {n} | {i} of {n} | {u} of {n} | {v} of {n} |")
out += ["", "| Q | Group | Arm A, no skill | Arm B, with skill |", "| --- | --- | --- | --- |"]
by = {(r["arm"], r["id"]): r for r in rows}
def cell(r):
    fl = [n for n, k in (("wrong", "wrong"), ("invented", "invented"), ("verdict", "verdict")) if r[k] == 1]
    return f"{r['points_met']}/{r['points_possible']}" + (" (" + ", ".join(fl) + ")" if fl else "")
for q in order:
    tag = " (extension)" if panel[q]["scope"] == "extension" else ""
    out.append(f"| {q}{tag} | {panel[q]['group']} | {cell(by[('A', q)])} | {cell(by[('B', q)])} |")
(H / "table.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
