#!/usr/bin/env python3
"""Runs the 20 questions through two arms of headless Claude Code (Sonnet), one fresh `claude -p` per answer.

Arm A: no tools, no MCP servers, no skills (--tools "", --disable-slash-commands), run from an empty git folder.
Arm B: the plugin payments@waverunner-ai installed at project scope in its own git folder; tools
       Bash, Read, Glob, Skill only; Bash allowed only for `python` and `cd` (the skill's own instructions say to
       run the script from its folder, and `cd X && python ...` is a compound command); the plugin's folder is
       added as a working directory so that `cd` into it is allowed; no web tool, no MCP.
Both arms: --model sonnet, --setting-sources project,local (the user's own settings, MCP servers and skills are
not loaded), --strict-mcp-config, no session saved, permission mode dontAsk (anything not allowed is refused,
never asked). The raw stream-json of every run is kept in raw/.

Usage: python run.py [--arms A B] [--ids S1 F3 ...] [--workers 4]
Resumable: a run whose answer file exists is skipped. A run that fails or passes 240 s is logged in raw/attempts.log
and counts as failed; run the same command again to retry it.
"""
import argparse
import json
import shutil
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Set both before a run: the folder that holds the two scratch git folders, and where the plugin was installed.
# The test of 2026-11-24 ran the plugin under its first name, payments-skills; it is called payments since.
SCRATCH = Path(os.environ.get("EVAL_SCRATCH", "scratch"))
PLUGIN_DIR = os.environ.get("EVAL_PLUGIN_DIR", "")
TIMEOUT = 240

COMMON = [
    "-p", "--model", "sonnet", "--strict-mcp-config", "--setting-sources", "project,local",
    "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--permission-mode", "dontAsk",
]
ARMS = {
    "A": {"cwd": SCRATCH / "armA", "args": ["--tools", "", "--disable-slash-commands"]},
    "B": {
        "cwd": SCRATCH / "armB",
        "args": [
            "--tools", "Bash,Read,Glob,Skill",
            "--allowedTools", "Bash(python:*)", "Bash(cd:*)", "Read", "Glob", "Skill",
            "--add-dir", PLUGIN_DIR,
        ],
    },
}


def prompt_for(q, arm):
    p = q["question"]
    if arm == "B" and q.get("armBSuffix"):
        p += "\n\n" + q["armBSuffix"]
    return p


def kill_tree(pid):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)


def one(arm, q):
    ans = HERE / "answers" / arm / f"{q['id']}.md"
    raw = HERE / "raw" / f"{arm}-{q['id']}.jsonl"
    if ans.exists():
        return f"skip {arm}-{q['id']}"
    cfg = ARMS[arm]
    cmd = [shutil.which("claude")] + COMMON + cfg["args"]
    t0 = time.time()
    status = "ok"
    out = ""
    proc = subprocess.Popen(cmd, cwd=cfg["cwd"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8")
    try:
        out, err = proc.communicate(prompt_for(q, arm), timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        kill_tree(proc.pid)
        out, err = "", ""
        status = "timeout"
    raw.write_text(out, encoding="utf-8")
    result = ""
    for line in out.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "result":
            result = e.get("result") or ""
            if e.get("is_error"):
                status = "error"
    if status == "ok" and not result.strip():
        status = "empty"
    with open(HERE / "raw" / "attempts.log", "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {arm}-{q['id']} {status} {time.time() - t0:.0f}s\n")
    if status == "ok":
        ans.write_text(result, encoding="utf-8")
    return f"{status} {arm}-{q['id']} {time.time() - t0:.0f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", default=["A", "B"])
    ap.add_argument("--ids", nargs="+")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    panel = json.loads((HERE / "panel.json").read_text(encoding="utf-8"))
    qs = [q for q in panel["questions"] if not a.ids or q["id"] in a.ids]
    for arm in a.arms:
        (HERE / "answers" / arm).mkdir(parents=True, exist_ok=True)
    (HERE / "raw").mkdir(exist_ok=True)
    jobs = [(arm, q) for q in qs for arm in a.arms]
    with ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(lambda j: one(*j), jobs):
            print(r, flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
