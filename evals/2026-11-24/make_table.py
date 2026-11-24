#!/usr/bin/env python3
"""Prints the per-question table (arm labels restored from scores.csv) for README.md."""
import csv
import json
from pathlib import Path

H = Path(__file__).resolve().parent
rows = list(csv.DictReader(open(H / "scores.csv", encoding="utf-8")))
panel = {q["id"]: q for q in json.load(open(H / "panel.json", encoding="utf-8"))["questions"]}
by = {(r["arm"], r["id"]): r for r in rows}
short = {
    "S1": "AM04: meaning, fault, retry", "S2": "MD01", "S3": "MD06 refund claim", "S4": "MS03",
    "S5": "AC04, retry next week", "S6": "MD07", "S7": "SL01", "S8": "ED05 (the rarer code)",
    "F1": "pain.002 example file, today 2026-11-03", "F2": "CSV example file (has AB05), 2026-11-03",
    "F3": "camt.054 file I made, 2026-11-04", "F4": "German CSV with names, 2026-11-12",
    "F5": "CSV example plus the merchant's own fees", "F6": "camt.054, \"I use Mollie\"",
    "T1": "AB05, a code outside the 25", "T2": "\"just retry MS03 next week?\"",
    "T3": "\"charge MD06 again right away?\"", "T4": "weekend retry date (Saturday 2026-11-07)",
    "T5": "\"what is the SEPA retry maximum?\"", "T6": "statement with no returns in it",
}


def cell(r):
    s = f"{r['points_met']}/{r['points_possible']}"
    fl = []
    if r["wrong_flag"] == "1":
        fl.append("wrong")
    if r["invented_flag"] == "1":
        fl.append("invented")
    return s + (" (" + ", ".join(fl) + ")" if fl else "")


out = ["| Q | Topic | Arm A, no skill | Arm B, with skill |", "| --- | --- | --- | --- |"]
for q in panel:
    out.append(f"| {q} | {short[q]} | {cell(by[('A', q)])} | {cell(by[('B', q)])} |")
print("\n".join(out))
