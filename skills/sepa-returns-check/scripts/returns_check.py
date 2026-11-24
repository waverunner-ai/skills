#!/usr/bin/env python3
"""Reads a bank's SEPA Direct Debit return file and says what to do with each returned debit.

Formats: pain.002 (payment status report), camt.054 and camt.053 (debit notification, statement),
and CSV or TSV exports from a bank or payment provider.

Four things are read per returned debit: the reason code, the amount, a date and the debit's own
reference (end-to-end ID, else mandate ID). The name and account fields are not read, and a
reference that holds an IBAN is dropped. A reference is whatever the merchant put in it:
if that is a customer's name, it shows, unless --no-references is given. The script uses the Python
standard library and opens no network connection.

Usage:
    python returns_check.py <file> [--today YYYY-MM-DD] [--fee-failed 3.50] [--fee-refund 15]
                                   [--no-rows] [--no-references]
    python returns_check.py --code AM04

Prints one JSON object. Exit code 0 on success, 2 when the file cannot be read as a return file.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "codes.json"

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 20_000
# A Core debit is announced 14 calendar days ahead unless the merchant and customer agreed another period.
PRE_NOTIFICATION_DAYS = 14
# Stripe's published price list for Ireland, read 2026-10-30. Every bank and provider charges its own.
DEFAULT_FEE_FAILED = 3.50
DEFAULT_FEE_REFUND = 15.00

CODE = re.compile(r"^(?:[A-Z]{2}\d{2}|CNOR|DNOR)$")
ISO_DAY = re.compile(r"^(\d{4}-\d{2}-\d{2})")
EU_DAY = re.compile(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})")
PLAIN_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")

REASON_HEADER = re.compile(r"reason|code|grund|reden|motif|motivo|causale|rsn", re.I)
AMOUNT_HEADER = re.compile(r"amount|betrag|bedrag|montant|import[eo]|\bvalue\b|\bsum(?:me)?\b", re.I)
DATE_HEADER = re.compile(r"date|datum|fecha|data|dt", re.I)
# A reference column holds an ID. "Mandate holder" or "Customer name" is a person, never a reference.
REF_HEADER = re.compile(
    r"end.?to.?end|e2e|referen|kenmerk|r[eé]f[eé]rence|riferimento|mandat\w*[\s_-]*(?:id|ref|nr|no|num)|\bref\b", re.I
)
PERSON_HEADER = re.compile(r"name|holder|inhaber|naam|nom\b|nombre|titulaire|debtor|schuldner|kunde\b|customer\s*$", re.I)

# IBAN length per country, for the countries in the SEPA area. Used to keep account numbers out of the output.
IBAN_LENGTH = {
    "AD": 24, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "EE": 20, "ES": 24,
    "FI": 18, "FR": 27, "GB": 22, "GI": 23, "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IS": 26, "IT": 27, "LI": 21,
    "LT": 20, "LU": 20, "LV": 21, "MC": 27, "MD": 24, "ME": 22, "MK": 19, "MT": 31, "NL": 18, "NO": 15, "PL": 28,
    "PT": 25, "RO": 24, "RS": 22, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "VA": 22, "AL": 28,
}  # fmt: skip
IBAN_START = re.compile(r"[A-Z]{2}\d{2}")


def holds_iban(value: str) -> bool:
    """True when the value contains a valid IBAN anywhere in it (right length for its country, check digits pass)."""
    s = re.sub(r"[^A-Z0-9]", "", value.upper())
    for m in IBAN_START.finditer(s):
        length = IBAN_LENGTH.get(m.group()[:2])
        candidate = s[m.start() : m.start() + length] if length else ""
        if length and len(candidate) == length:
            moved = candidate[4:] + candidate[:4]
            if int("".join(str(int(ch, 36)) for ch in moved)) % 97 == 1:
                return True
    return False


class ReturnFileError(Exception):
    """The file is not a return file this script can read. The message is written for the merchant."""


def load_codes() -> tuple[dict, dict]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    return {c["code"]: c for c in data["codes"]}, data


def money(n: float) -> float:
    """Rounds to cents, half up (10.125 becomes 10.13)."""
    return math.floor(n * 100 + 0.5) / 100 if math.isfinite(n) and abs(n) < 1e15 else 0.0


# --- XML -------------------------------------------------------------------------------------------


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def kids(el, name):
    return [c for c in el if local(c.tag) == name]


def at(el, path: str):
    """The first descendant reached by a path of local names ("Rsn/Cd"), in any namespace version."""
    cur = el
    for name in path.split("/"):
        if cur is None:
            return None
        found = kids(cur, name)
        cur = found[0] if found else None
    return cur


def text(el) -> str:
    return (el.text or "").strip() if el is not None else ""


def xml_amount(el) -> float:
    value = text(el)
    return money(float(value)) if PLAIN_NUMBER.match(value) else 0.0


def real_day(iso: str):
    """The date when it exists in the calendar, else nothing (2026-13-45 and 2027-02-31 are dropped)."""
    try:
        return date.fromisoformat(iso).isoformat()
    except ValueError:
        return None


def iso_day(value: str):
    m = ISO_DAY.match(value)
    return real_day(m.group(1)) if m else None


def clean_ref(value: str):
    """A debit's own reference. Placeholders and anything that holds an IBAN are left out."""
    v = value.strip()
    if not v or v.upper() == "NOTPROVIDED" or holds_iban(v):
        return None
    return v[:35]


def row(code, amount, day=None, reference=None) -> dict:
    out = {"code": code, "amount": amount}
    if day:
        out["date"] = day
    if reference:
        out["reference"] = reference
    return out


def parse_pain002(root) -> list[dict]:
    rows = []
    for tx in root.iter():
        if local(tx.tag) != "TxInfAndSts":
            continue
        code = text(at(tx, "StsRsnInf/Rsn/Cd")).upper()
        if not CODE.match(code):
            continue
        ref = at(tx, "OrgnlTxRef")
        amount_el = at(ref, "Amt/InstdAmt")
        if amount_el is None:
            amount_el = at(ref, "Amt")
        reference = clean_ref(text(at(tx, "OrgnlEndToEndId"))) or clean_ref(text(at(ref, "MndtRltdInf/MndtId")))
        rows.append(row(code, xml_amount(amount_el), iso_day(text(at(ref, "ReqdColltnDt"))), reference))
    return rows


def parse_camt(root) -> list[dict]:
    rows = []
    # The entry a transaction sits in (Ntry/NtryDtls/TxDtls) carries the date and, for a single
    # transaction, the amount.
    for entry in root.iter():
        if local(entry.tag) != "Ntry":
            continue
        for details in kids(entry, "NtryDtls"):
            for tx in kids(details, "TxDtls"):
                code = text(at(tx, "RtrInf/Rsn/Cd")).upper()
                if not CODE.match(code):
                    continue
                amount_el = None
                for path in ("Amt", "AmtDtls/TxAmt/Amt", "AmtDtls/InstdAmt/Amt"):
                    amount_el = at(tx, path)
                    if amount_el is not None:
                        break
                if amount_el is None:
                    amount_el = at(entry, "Amt")
                day = None
                for path in ("BookgDt/Dt", "BookgDt/DtTm", "ValDt/Dt"):
                    day = iso_day(text(at(entry, path)))
                    if day:
                        break
                reference = clean_ref(text(at(tx, "Refs/EndToEndId"))) or clean_ref(text(at(tx, "Refs/MndtId")))
                rows.append(row(code, xml_amount(amount_el), day, reference))
    return rows


# --- CSV -------------------------------------------------------------------------------------------


def parse_amount(raw: str) -> float:
    """ "1.234,56", "1,234.56", "-12,50 EUR" and "12.5" all become numbers."""
    s = re.sub(r"[^\d,.-]", "", raw)
    if s in ("", "-"):
        return 0.0
    if s.rfind(",") > s.rfind("."):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return money(abs(float(s)))
    except ValueError:
        return 0.0


def parse_date(raw: str):
    """ "2026-10-03", "03.10.2026", "03/10/2026" (day first, as European banks write it)."""
    s = raw.strip()
    day = iso_day(s)
    if day:
        return day
    m = EU_DAY.match(s)
    if not m:
        return None
    d, mo, y = m.groups()
    return real_day(f"{y}-{mo.zfill(2)}-{d.zfill(2)}")


def split_csv_line(line: str, sep: str) -> list[str]:
    """One line into cells. Quotes may wrap a cell; a broken quote spoils only its own line."""
    out, cur, quoted, i = [], "", False, 0
    while i < len(line):
        ch = line[i]
        if quoted:
            if ch == '"' and line[i + 1 : i + 2] == '"':
                cur += '"'
                i += 1
            elif ch == '"':
                quoted = False
            else:
                cur += ch
        elif ch == '"':
            quoted = True
        elif ch == sep:
            out.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    out.append(cur)
    return [c.strip() for c in out]


def parse_csv(content: str, known: dict) -> list[dict]:
    lines = [line for line in re.split(r"\r?\n", content) if line.strip()]
    if not lines:
        return []
    sep = max(("\t", ";", ","), key=lambda s: lines[0].count(s))
    table = [split_csv_line(line, sep) for line in lines]
    width = max(len(r) for r in table)

    def cell(r, i):
        return r[i] if i < len(r) else ""

    # The code column: the one with the most known codes, a reason-like header breaking ties
    # (short IBAN or country fields can look like codes).
    code_col, best = -1, 0
    for col in range(width):
        hits = sum(1 for r in table if cell(r, col).upper() in known)
        if hits == 0:
            continue
        score = hits * 2 + (1 if REASON_HEADER.search(cell(table[0], col)) else 0)
        if score > best:
            best, code_col = score, col
    if code_col < 0:
        return []

    has_header = not CODE.match(cell(table[0], code_col).upper())
    header = table[0] if has_header else []

    def find(pattern, taken):
        for i, h in enumerate(header):
            if i not in taken and pattern.search(h) and not PERSON_HEADER.search(h):
                return i
        return -1

    amount_col = find(AMOUNT_HEADER, {code_col})
    # Before the date column: "Mandate ID" would otherwise match "date".
    ref_col = find(REF_HEADER, {code_col, amount_col})
    date_col = find(DATE_HEADER, {code_col, amount_col, ref_col})

    rows = []
    for r in table[1:] if has_header else table:
        code = cell(r, code_col).upper()
        if not CODE.match(code):
            continue
        rows.append(
            row(
                code,
                parse_amount(cell(r, amount_col)) if amount_col >= 0 else 0.0,
                parse_date(cell(r, date_col)) if date_col >= 0 else None,
                clean_ref(cell(r, ref_col)) if ref_col >= 0 else None,
            )
        )
    return rows


# --- Reading a file ----------------------------------------------------------------------------------


def detect_type(content: str) -> str:
    """Which format a file is, from its content (never from its name)."""
    head = content[:4000]
    if re.search(r"<\s*(?:\w+:)?CstmrPmtStsRpt[\s>]", head) or "pain.002" in head:
        return "pain.002"
    if re.search(r"<\s*(?:\w+:)?BkToCstmrDbtCdtNtfctn[\s>]", head) or "camt.054" in head:
        return "camt.054"
    if re.search(r"<\s*(?:\w+:)?BkToCstmrStmt[\s>]", head) or "camt.053" in head:
        return "camt.053"
    return "csv"


def parse_return_file(content: str, known: dict) -> tuple[str, list[dict]]:
    kind = detect_type(content)
    if kind == "csv":
        rows = parse_csv(content, known)
    else:
        # A bank's file never declares its own entities; refusing them keeps a crafted file from
        # expanding in memory.
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", content, re.I):
            raise ReturnFileError("This XML file declares its own entities, which a bank's return file never does.")
        try:
            root = ET.fromstring(content.encode("utf-8"))
        except ET.ParseError as exc:
            raise ReturnFileError("This file is not valid XML. Export it again from your bank and try once more.") from exc
        rows = parse_pain002(root) if kind == "pain.002" else parse_camt(root)
    if not rows:
        if kind == "csv":
            raise ReturnFileError("No SEPA reason codes found. The file needs a column with codes such as AM04 or MD06.")
        raise ReturnFileError(f"This {kind} file holds no returned or rejected debits with a reason code.")
    return kind, rows[:MAX_ROWS]


# --- Deciding ----------------------------------------------------------------------------------------


def add_days_to_workday(iso: str, days: int) -> str:
    """Adds days and moves a Saturday or Sunday to the Monday after."""
    d = date.fromisoformat(iso) + timedelta(days=days)
    if d.weekday() == 5:
        d += timedelta(days=2)
    elif d.weekday() == 6:
        d += timedelta(days=1)
    return d.isoformat()


def bucket_of(entry: dict) -> str:
    """retry, fix, contact or stop. A code that needs a question first (MS03) counts as contact."""
    again = entry["collectAgain"]
    return "contact" if again["action"] == "retry" and again["askFirst"] else again["action"]


def retry_date(entry: dict, r: dict, base: str):
    """The earliest new attempt: the later of the default wait and a pre-notification sent on the base day."""
    again = entry["collectAgain"]
    if bucket_of(entry) != "retry" or again["afterDays"] is None:
        return None
    start = r["date"] if r.get("date") and r["date"] > base else base
    return max(add_days_to_workday(start, again["afterDays"]), add_days_to_workday(base, PRE_NOTIFICATION_DAYS))


def fee_for(entry: dict, fee_failed: float, fee_refund: float) -> float:
    return fee_refund if entry["comesAs"] == ["Refund"] else fee_failed


def code_view(entry: dict) -> dict:
    return {
        "code": entry["code"],
        "name": entry["name"],
        "comesAs": entry["comesAs"],
        "scheme": entry["scheme"],
        "meaning": entry["description"],
        "whoCaused": entry["whoCaused"],
        "collectAgain": entry["collectAgain"]["decision"],
        "collectAgainDetail": entry["collectAgainDetail"],
        "canArriveAsMs03": entry["canArriveAsMs03"],
        "customerMessage": entry.get("customerMessage"),
        "page": entry["url"],
    }


def summarise(
    rows: list[dict], known: dict, base: str, fee_failed: float, fee_refund: float, with_rows: bool, with_refs: bool = True
) -> dict:
    fee_failed, fee_refund = money(fee_failed), money(fee_refund)
    buckets = {k: {"count": 0, "amount": 0.0} for k in ("retry", "fix", "contact", "stop")}
    unknown = {"count": 0, "amount": 0.0, "codes": []}
    by_code: dict[str, dict] = {}
    calendar: dict[str, dict] = {}
    plans = []
    total = fees = 0.0

    for r in rows:
        amount = money(max(r["amount"], 0.0))
        total += amount
        entry = known.get(r["code"])
        plan = {k: r[k] for k in ("reference", "date") if r.get(k) and (with_refs or k != "reference")}
        plan.update({"code": r["code"], "amount": amount})
        if entry is None:
            unknown["count"] += 1
            unknown["amount"] += amount
            if r["code"] not in unknown["codes"]:
                unknown["codes"].append(r["code"])
            plan.update({"decision": "Ask your provider", "fee": 0.0})
            plans.append(plan)
            continue
        fee = fee_for(entry, fee_failed, fee_refund)
        fees += fee
        bucket = bucket_of(entry)
        buckets[bucket]["count"] += 1
        buckets[bucket]["amount"] += amount
        t = by_code.setdefault(entry["code"], {**code_view(entry), "bucket": bucket, "count": 0, "amount": 0.0})
        t["count"] += 1
        t["amount"] += amount
        day = retry_date(entry, r, base)
        if day:
            c = calendar.setdefault(day, {"date": day, "count": 0, "amount": 0.0})
            c["count"] += 1
            c["amount"] += amount
            plan["retryOn"] = day
        plan.update({"decision": entry["collectAgain"]["decision"], "bucket": bucket, "fee": fee})
        plans.append(plan)

    for b in list(buckets.values()) + [unknown] + list(by_code.values()) + list(calendar.values()):
        b["amount"] = money(b["amount"])

    out = {
        "returns": len(rows),
        "amount": money(total),
        "fees": money(fees),
        "buckets": buckets,
        "unknown": unknown,
        "byCode": sorted(by_code.values(), key=lambda t: (-t["count"], -t["amount"], t["code"])),
        "retryCalendar": sorted(calendar.values(), key=lambda c: c["date"]),
    }
    if with_rows:
        out["rows"] = plans
    return out


def fee(value: str) -> float:
    try:
        n = float(value)
    except ValueError:
        n = float("nan")
    if not math.isfinite(n) or n < 0:
        raise argparse.ArgumentTypeError("a fee is a number of euros, zero or more")
    return n


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Check a SEPA Direct Debit return file.")
    p.add_argument("file", nargs="?", help="pain.002, camt.054, camt.053, CSV or TSV")
    p.add_argument("--code", help="explain one reason code instead of reading a file")
    p.add_argument("--today", help="the day a new pre-notification would go out (YYYY-MM-DD); default today")
    p.add_argument("--fee-failed", type=fee, default=None, help="fee per failed debit, EUR (default 3.50)")
    p.add_argument("--fee-refund", type=fee, default=None, help="fee per refund claim, EUR (default 15.00)")
    p.add_argument("--no-rows", action="store_true", help="leave the per-debit list out of the output")
    p.add_argument("--no-references", action="store_true", help="leave each debit's reference out of the output")
    args = p.parse_args(argv)

    known, data = load_codes()
    source = {
        "codes": data["sources"][0]["title"],
        "codesUrl": data["sources"][0]["url"],
        "defaults": "Waverunner defaults, not EPC rules: the EPC sets no retry rule, wait or fee.",
        "license": data["license"]["name"],
        "attribution": data["attribution"],
        "dataUpdated": data["updated"],
    }

    def fail(message: str) -> int:
        print(json.dumps({"error": message}, ensure_ascii=False, indent=2))
        return 2

    if args.code:
        normal = re.sub(r"[^A-Za-z0-9]", "", args.code).upper()
        entry = known.get(normal)
        if entry is None:
            return fail(f"{normal or args.code} is not one of the 25 SEPA Direct Debit reason codes in the EPC guidance.")
        print(json.dumps({"code": code_view(entry), "source": source}, ensure_ascii=False, indent=2))
        return 0

    if not args.file:
        p.error("give a file, or --code")
    if args.today and not (re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.today) and real_day(args.today)):
        return fail("--today takes a real date written as YYYY-MM-DD.")
    path = Path(args.file)
    if not path.is_file():
        return fail(f"No file at {path}.")
    if path.stat().st_size > MAX_FILE_BYTES:
        return fail("This file is over 10 MB. A month's returns fit in far less; export a shorter period.")
    content = path.read_bytes().decode("utf-8-sig", errors="replace")
    try:
        kind, rows = parse_return_file(content, known)
    except ReturnFileError as exc:
        return fail(str(exc))

    base = args.today or date.today().isoformat()
    out = {"fileType": kind, "preNotificationSentOn": base}
    fee_failed = DEFAULT_FEE_FAILED if args.fee_failed is None else args.fee_failed
    fee_refund = DEFAULT_FEE_REFUND if args.fee_refund is None else args.fee_refund
    out.update(summarise(rows, known, base, fee_failed, fee_refund, not args.no_rows, not args.no_references))
    stripe = "Stripe's published price for Ireland, read 2026-10-30"
    out["feesUsed"] = {
        "failedDebit": money(fee_failed),
        "failedDebitFrom": stripe if args.fee_failed is None else "given by the merchant",
        "refundClaim": money(fee_refund),
        "refundClaimFrom": stripe if args.fee_refund is None else "given by the merchant",
    }
    out["source"] = source
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a file this script did not expect: say so in the same shape as any other refusal
        print(json.dumps({"error": f"This file could not be read ({type(exc).__name__}). Export it again and try once more."}))
        sys.exit(2)
