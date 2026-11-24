#!/usr/bin/env python3
"""Blind scorer: one fresh headless Sonnet run per answer (no tools, no skills, no arm label), writes
scoring_blind.json. The scorer sees the question, the key points, the wrong_if list, the site guide text (to tell
"not in the key" from "not on the site") and the answer. Set EVAL_SCRATCH (any empty git folder is used as cwd,
EVAL_SCRATCH/armA) and EVAL_GUIDE (the guide's .mdx file). Usage: python score.py [--workers 8]
Resumable: ids already in scoring_blind.json are skipped."""
import argparse, json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
H = Path(__file__).resolve().parent
CWD = Path(os.environ.get("EVAL_SCRATCH", "scratch")) / "armA"
GUIDE = Path(os.environ["EVAL_GUIDE"]).read_text(encoding="utf-8")
OUT = H / "scoring_blind.json"
RUBRIC = """You are scoring one answer to a merchant's question about card chargeback ratios. You do not know how the answer was made. Score only against the key below.

Return ONLY one JSON object, no prose, with these fields:
- "points": a list of 1 or 0, one per key point in order. 1 = the answer clearly states the substance of that key point (judge the meaning, not the wording). 0 = missing, vague, or contradicted.
- "wrong": 1 if the answer states anything listed in WRONG_IF, or anything that contradicts a key point; else 0.
- "invented": 1 if the answer adds a threshold, number, date, fee, deadline, programme or rule that is NOT in the key points, whether or not it is true in the real world; else 0. Generic advice, hedges, restating the question and arithmetic on the merchant's own numbers are not invented.
- "unsupported": 1 if any such added item is also absent from SITE_GUIDE below (so it is not on the site either); 0 if every added item can be found in the guide, or there are none.
- "verdict": 1 if the answer tells the merchant they are safe, fine, OK, in a programme (for example "you are in ECM"), or will be closed, fined or listed; or says they are NOT in a programme as a settled fact. 0 if it only states numbers and published thresholds and where the numbers sit against them, including "your numbers meet both ECM conditions" or "does not meet the count", and leaves the status to the provider or says it cannot say.
- "note": at most 25 words naming what drove any flag, or "" if none.

QUESTION:
{question}

KEY_POINTS:
{key}

WRONG_IF:
{wrong}

SITE_GUIDE (reference text for the "unsupported" flag only; it is not the key):
{guide}

ANSWER TO SCORE:
{answer}
"""

def one(rid):
    d = json.loads((H / "blind" / f"{rid}.json").read_text(encoding="utf-8"))
    prompt = RUBRIC.format(question=d["question"], key="\n".join(f"{i+1}. {t}" for i, t in enumerate(d["key_points"])),
                           wrong="\n".join("- " + w for w in d["wrong_if"]), guide=GUIDE, answer=d["answer"])
    for attempt in (1, 2):
        p = subprocess.run([shutil.which("claude"), "-p", "--model", "sonnet", "--tools", "", "--disable-slash-commands",
                            "--strict-mcp-config", "--setting-sources", "project,local", "--no-session-persistence",
                            "--output-format", "json", "--permission-mode", "dontAsk"],
                           input=prompt, cwd=CWD, capture_output=True, text=True, encoding="utf-8", timeout=240)
        try:
            env = json.loads(p.stdout)
            txt = env["result"].strip()
            txt = txt[txt.index("{"): txt.rindex("}") + 1]
            r = json.loads(txt)
            assert len(r["points"]) == len(d["key_points"])
            r["cost"] = env.get("total_cost_usd")
            return rid, r
        except Exception as e:
            err = repr(e)
    return rid, {"error": err}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--workers", type=int, default=8); a = ap.parse_args()
    S = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [p.stem for p in sorted((H / "blind").glob("R*.json")) if p.stem not in S or "error" in S[p.stem]]
    with ThreadPoolExecutor(a.workers) as ex:
        for rid, r in ex.map(one, todo):
            S[rid] = r; print(rid, "error" if "error" in r else "ok", flush=True)
    OUT.write_text(json.dumps(S, indent=1, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    main()
