#!/usr/bin/env python3
"""Reads raw/*.jsonl and writes telemetry.csv: per run, whether the skill was loaded and the script actually ran.

skill_loaded : a Skill tool call naming sepa-returns-check was made.
script_ran   : a Bash call with returns_check.py got a result that is not a permission refusal or error.
script_denied: number of Bash calls refused by the permission system.
tools_used   : tool names used, counted.
"""
import csv
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = []
for raw in sorted((HERE / "raw").glob("*.jsonl")):
    arm, qid = raw.stem.split("-", 1)
    uses, results = {}, {}
    init_tools, turns, cost, model = None, None, None, None
    for line in raw.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        t = e.get("type")
        if t == "system" and e.get("subtype") == "init":
            init_tools, model = e.get("tools"), e.get("model")
        if t == "assistant":
            for b in e["message"]["content"]:
                if b.get("type") == "tool_use":
                    uses[b["id"]] = b
        if t == "user" and isinstance(e["message"]["content"], list):
            for b in e["message"]["content"]:
                if b.get("type") == "tool_result":
                    results[b["tool_use_id"]] = b
        if t == "result":
            turns, cost = e.get("num_turns"), e.get("total_cost_usd")
    names = Counter(u["name"] for u in uses.values())
    skill = any(u["name"] == "Skill" and "sepa-returns-check" in json.dumps(u["input"]) for u in uses.values())
    ran = denied = errored = 0
    for i, u in uses.items():
        if u["name"] != "Bash":
            continue
        res = results.get(i, {})
        text = json.dumps(res.get("content", ""))
        if "denied" in text.lower() and "permission" in text.lower():
            denied += 1
        elif "returns_check.py" in json.dumps(u["input"]):
            ran += 1  # it ran; a script exit code 2 (an error message meant for the merchant) still counts
            if res.get("is_error"):
                errored += 1
    rows.append({
        "arm": arm, "id": qid, "model": model, "skill_loaded": int(skill), "script_ran": ran, "script_exit_nonzero": errored, "bash_denied": denied,
        "tools_used": ";".join(f"{k}={v}" for k, v in sorted(names.items())), "turns": turns,
        "cost_usd": round(cost, 4) if cost else cost,
    })
with open(HERE / "telemetry.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(len(rows), "runs")
