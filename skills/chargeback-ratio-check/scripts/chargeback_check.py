#!/usr/bin/env python3
"""Works out a card chargeback ratio and sets it beside the published monitoring thresholds.

The arithmetic is a port of the chargeback ratio calculator in Waverunner's guide
(https://waverunner.ai/blog/chargeback-ratio/): this month's chargebacks divided by last
month's transactions, the way Mastercard's chargeback monitoring counts it. Visa's and the
acquirers' own tests count differently. The calculator shows the ratio, never a judgement on
the account; this script adds, per programme in data/programs.json, the published threshold
(always a ratio and a minimum) and where the two numbers sit against each condition.

The script uses the Python standard library only and opens no network connection.

Usage:
    python chargeback_check.py --chargebacks 45 --transactions 2500
    python chargeback_check.py --rules

Prints one JSON object. Exit code 0 on success, 2 when the input cannot be used.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "programs.json"

# The input limits of the site's calculator.
CHARGEBACK_LIMITS = {"chargebacks": 10_000_000, "transactions": 1_000_000_000}
NOTE = "An estimate; your provider confirms which test applies to you."
METHOD = (
    "This month's chargebacks divided by last month's transactions, the way Mastercard's chargeback monitoring "
    "counts it (the transactions of the month before). Visa's and the acquirers' own tests count differently."
)
ASSUMES = (
    "Mastercard counts Mastercard chargebacks over Mastercard transactions, per merchant ID. If the two numbers "
    "cover all cards or several merchant IDs, the comparison below is the calculator's estimate, not Mastercard's count."
)
NOT_AVAILABLE = "Not available"


class InputError(Exception):
    """The input cannot be used. The message is written for the merchant."""


# --- The port of the site's calculator --------------------------------------------------------------


def js_round(x: float) -> int:
    """JavaScript's Math.round for zero or more: a half goes up (2.5 becomes 3), unlike Python's round()."""
    whole = math.floor(x)
    return int(whole) + (1 if x - whole >= 0.5 else 0)


def count(value, maximum: int) -> int:
    """A whole count inside the limits; anything that is not a finite number becomes 0."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return 0
    return js_round(min(maximum, max(0, value)))


def normalise_chargeback_inputs(chargebacks, transactions) -> dict:
    """Whole counts inside the limits (NaN and negatives become 0)."""
    return {
        "chargebacks": count(chargebacks, CHARGEBACK_LIMITS["chargebacks"]),
        "transactions": count(transactions, CHARGEBACK_LIMITS["transactions"]),
    }


def chargeback_ratio(chargebacks, transactions) -> dict:
    """Ratio, percent and basis points; all three None without transactions, never 0 or infinity."""
    n = normalise_chargeback_inputs(chargebacks, transactions)
    if n["transactions"] == 0:
        return {**n, "ratio": None, "percent": None, "bps": None}
    ratio = n["chargebacks"] / n["transactions"]
    return {**n, "ratio": ratio, "percent": ratio * 100, "bps": ratio * 10_000}


def _rounded(x: float, places: int) -> Decimal:
    """Rounds the way Intl.NumberFormat does: half away from zero, on the shortest decimal form of the number."""
    return Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def format_percent(percent: float) -> str:
    """ "1.50%": two decimals, thousands separated."""
    return f"{_rounded(percent, 2):,f}%"


def format_bps(bps: float) -> str:
    """ "150 bps", "11.7 bps": at most one decimal."""
    text = f"{_rounded(bps, 1):,f}"
    return f"{text[:-2] if text.endswith('.0') else text} bps"


def format_count(value: float) -> str:
    """ "6,000"."""
    return f"{_rounded(value, 0):,f}"


# --- Comparing with the published thresholds -------------------------------------------------------


def ratio_meets(chargebacks: int, transactions: int, bps: int, rule: str) -> bool:
    """Compares in whole numbers: 45 over 2,500 is 180 bps exactly, never 179.99999999999997."""
    left, right = chargebacks * 10_000, bps * transactions
    return left > right if rule == "over" else left >= right


def exact_bps(chargebacks: int, transactions: int) -> str:
    """The basis points to four decimals, cut rather than rounded, so a figure under a line never reads as on it."""
    value = (Decimal(chargebacks) * 10_000 / Decimal(transactions)).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
    return f"{value.normalize():,f}"


def plural(n: int, one: str, many: str) -> str:
    return f"{format_count(n)} {one if n == 1 else many}"


def source_view(sources: dict, key) -> dict | None:
    if not key:
        return None
    s = sources[key]
    return {"publisher": s["publisher"], "title": s["title"], "url": s["url"], "checked": s["checked"]}


def on_your_numbers(prog: dict, result: dict) -> dict:
    """Where the two numbers sit against one programme's conditions, as plain facts."""
    if prog.get("computeFrom") != "this-month-over-last-month":
        return {"computed": False, "why": prog["notComputed"]}
    if result["bps"] is None:
        return {"computed": False, "why": "No transactions last month, so there is no ratio to compare."}
    cb, tx = result["chargebacks"], result["transactions"]
    shown = format_bps(result["bps"])
    r = prog["ratio"]
    meets = ratio_meets(cb, tx, r["bps"], r["rule"])
    ratio_line = {"condition": r["text"], "yours": shown, "meets": meets}
    if not meets and _rounded(result["bps"], 1) >= r["bps"]:
        if cb * 10_000 == r["bps"] * tx:  # only an "over" rule can miss on an exact tie
            ratio_line["note"] = f"The ratio is exactly {r['bps']} bps, and this condition asks for more than that."
        else:
            ratio_line["note"] = (
                f"Rounded, the ratio shows as {format_percent(result['percent'])} ({shown}), but it is "
                f"{exact_bps(cb, tx)} bps, just under {r['bps']} bps."
            )
    lines = [ratio_line]
    # Only ECM and HECM are computed, and both minimums are a count of chargebacks.
    for m in prog["minimums"]:
        lines.append({"condition": m["text"], "yours": plural(cb, "chargeback", "chargebacks"), "meets": cb >= m["value"]})
    met = sum(1 for line in lines if line["meets"])
    if met == len(lines):
        words = "The numbers meet both conditions as the guide states them: the ratio and the minimum count."
    elif met == 0:
        words = "The numbers meet neither condition as the guide states them: not the ratio, not the minimum count."
    elif lines[0]["meets"]:
        words = "The numbers meet the ratio condition and not the minimum count, as the guide states them."
    else:
        words = "The numbers meet the minimum count and not the ratio condition, as the guide states them."
    return {
        "computed": True,
        "conditions": lines,
        "meetsAllConditions": met == len(lines),
        "inWords": words,
        "assumes": ASSUMES,
    }


def programme_view(prog: dict, sources: dict, result: dict | None) -> dict:
    out = {
        "id": prog["id"],
        "name": prog["name"],
        "network": prog["network"],
        "kind": prog["kind"],
        "basis": prog["basis"],
        "appliesTo": prog["appliesTo"],
        "region": prog["region"],
        "effectiveFrom": prog["effectiveFrom"],
        "period": prog["period"],
        "howItCounts": prog["howItCounts"],
        "threshold": prog["threshold"],
        "ratioCondition": prog["ratio"]["text"] if prog["ratio"] else None,
        "minimumConditions": [m["text"] for m in prog["minimums"]],
    }
    if result is not None:
        out["onYourNumbers"] = on_your_numbers(prog, result)
    for key in ("when", "publishedFollowUp", "leaving", "fees", "feeNote", "minimumsNote"):
        if prog.get(key):
            out[key] = prog[key]
    out["ask"] = prog["ask"]
    out["source"] = source_view(sources, prog["source"])
    counting = prog.get("howItCountsSource")
    if counting and counting != prog["source"]:
        out["countingSource"] = source_view(sources, counting)
    if prog.get("tableOnly"):
        out["tableOnly"] = True
    if prog.get("caveat"):
        out["caveat"] = prog["caveat"]
    return out


def load_data() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def report(data: dict, result: dict | None) -> dict:
    sources = data["sources"]
    facts = []
    for fact in data["facts"]:
        f = {"id": fact["id"], "text": fact["text"], "source": source_view(sources, fact["source"])}
        for key in ("provider", "sourceNote"):
            if fact.get(key):
                f[key] = fact[key]
        facts.append(f)
    return {
        "programmes": [programme_view(p, sources, result) for p in data["programmes"]],
        "facts": facts,
        "askYourProvider": data["askYourProvider"],
        "basisMeaning": data["basisMeaning"],
        "source": {
            "guide": data["guide"]["title"],
            "guideUrl": data["guide"]["url"],
            "calculatorUrl": data["guide"]["calculatorUrl"],
            "guideUpdated": data["guide"]["updated"],
            "copied": data["copied"],
            "note": data["note"],
        },
    }


# --- Reading the numbers ----------------------------------------------------------------------------

GROUPED = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")
# "98.000" is 98 thousand in much of Europe and 98 elsewhere: refused rather than guessed.
DOT_GROUPED = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})+$")


def shorten(raw: str) -> str:
    text = str(raw).strip()
    return text if len(text) <= 40 else text[:40] + "..."


def read_number(raw, flag: str):
    """A count as the merchant typed it ("1500", "1,500", "1500.0"): the number, None when not given.

    Raises InputError when it is not a finite number. Below zero, a fraction or over the limit is not an
    error here: the calculator's own rules handle those, and input_notes() says what they changed.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    shown = shorten(text)
    if DOT_GROUPED.match(text):
        raise InputError(
            f"{flag} got \"{shown}\", which could mean a number with decimals or a number in thousands. "
            "Write the count without a dot, such as 98000 or 98,000."
        )
    if GROUPED.match(text):
        text = text.replace(",", "")
    try:
        value = float(text)
    except ValueError:
        value = float("nan")
    if not math.isfinite(value):
        raise InputError(f"{flag} takes a count written in digits, such as 45 or 2,500. \"{shown}\" is not one.")
    return value


def input_notes(given: dict, typed: dict, used: dict) -> list:
    """Says when the calculator's rules changed a number: below zero, not whole, or over its limit."""
    words = {"chargebacks": "chargebacks this month", "transactions": "transactions last month"}
    notes = []
    for key, value in given.items():
        if value == used[key]:
            continue
        shown = shorten(typed[key])
        if value < 0:
            why = "is below zero, so the calculator counts it as 0"
        elif value > CHARGEBACK_LIMITS[key]:
            why = f"is more than the calculator takes, so it counts {format_count(used[key])}"
        else:
            why = f"is not a whole number, so the calculator rounds it to {format_count(used[key])}"
        notes.append(f"The number given for {words[key]} ({shown}) {why}.")
    return notes


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse would print usage text; every failure here is one JSON object
        raise InputError(
            "The options could not be read. Give both numbers, for example: --chargebacks 45 --transactions 2500 "
            f"({message})."
        )


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    def fail(message: str) -> int:
        print(json.dumps({"error": message}, ensure_ascii=False, indent=2))
        return 2

    p = Parser(description="Work out a chargeback ratio and set it beside the published thresholds.")
    p.add_argument("--chargebacks", help="chargebacks received this month")
    p.add_argument("--transactions", help="card transactions processed last month")
    p.add_argument("--rules", action="store_true", help="print the programmes, facts and questions without a ratio")
    try:
        args = p.parse_args(argv)
        chargebacks = read_number(args.chargebacks, "--chargebacks")
        transactions = read_number(args.transactions, "--transactions")
    except InputError as exc:
        return fail(str(exc))

    data = load_data()
    if chargebacks is None or transactions is None:
        if args.rules and chargebacks is None and transactions is None:
            print(json.dumps(report(data, None), ensure_ascii=False, indent=2))
            return 0
        return fail(
            "Give both numbers: --chargebacks, the chargebacks received this month, and --transactions, the card "
            "transactions processed last month. For example: --chargebacks 45 --transactions 2500."
        )

    result = chargeback_ratio(chargebacks, transactions)
    used = {"chargebacks": result["chargebacks"], "transactions": result["transactions"]}
    out = {
        "chargebacks": result["chargebacks"],
        "transactions": result["transactions"],
        "ratio": result["ratio"],
        "percent": result["percent"],
        "bps": result["bps"],
    }
    notes = input_notes(
        {"chargebacks": chargebacks, "transactions": transactions},
        {"chargebacks": args.chargebacks, "transactions": args.transactions},
        used,
    )
    if notes:
        out["inputNotes"] = notes
    if result["bps"] is None:
        out["display"] = {"percent": NOT_AVAILABLE, "bps": NOT_AVAILABLE, "detail": "Enter last month's transactions"}
    else:
        out["display"] = {
            "percent": format_percent(result["percent"]),
            "bps": format_bps(result["bps"]),
            "counted": f"{plural(used['chargebacks'], 'chargeback', 'chargebacks')} over "
            f"{plural(used['transactions'], 'transaction', 'transactions')}",
            "bpsMeaning": "1 basis point is 0.01%",
        }
    out["method"] = METHOD
    out["note"] = NOTE
    out.update(report(data, result))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # anything unforeseen still ends in the same shape as any other refusal
        print(json.dumps({"error": f"The check could not run ({type(exc).__name__}). Check the two numbers and try once more."}))
        sys.exit(2)
