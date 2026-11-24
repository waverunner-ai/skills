#!/usr/bin/env python3
"""Builds panel.json: the 20 questions and the answer key.

The key comes ONLY from skills/sepa-returns-check/data/codes.json and from the output of
skills/sepa-returns-check/scripts/returns_check.py run on the files in ./files (commands in each
question's "keySource"). It was written before any answer was run.

Each question has:
  id, group, question (what both arms get), armBSuffix (extra line only arm B gets: where the file is),
  keyPoints (2 to 4 points; a point is met or not met, 1 or 0),
  wrong (statements the key marks wrong; each one seen in an answer is a flag),
  keySource (where the key came from).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
F = HERE / "files"


import re


def strip_comments(t):
    """XML comments in a made-up file would tell the assistant what the file is; they are not inlined."""
    return re.sub(r"\s*<!--.*?-->", "", t, flags=re.S)


def file_q(today, filename, ask):
    body = strip_comments((F / filename).read_text(encoding="utf-8")).strip()
    q = (
        f"Today is {today}. My bank sent me this file with my returned direct debits:\n\n"
        f"{body}\n\n{ask}"
    )
    suffix = f"(The same file is saved in this folder as files/{filename}.)"
    return q, suffix


questions = []


def add(id, group, question, keyPoints, wrong, keySource, armBSuffix=""):
    questions.append(
        {
            "id": id,
            "group": group,
            "question": question,
            "armBSuffix": armBSuffix,
            "keyPoints": keyPoints,
            "wrong": wrong,
            "keySource": keySource,
        }
    )


# ---------------------------------------------------------------- single codes
SRC = "returns_check.py --code {c} (data/codes.json)"
add(
    "S1", "single",
    "A customer's direct debit for 39 euros came back with the code AM04. What does that mean, is it their fault or mine, and can I just try to collect again?",
    [
        "Says AM04 means insufficient funds.",
        "Says the cause is not only the customer: the account can be short of funds, OR the merchant sent the pre-notification late or not at all (the code alone does not settle who).",
        "Says collecting again is possible later (not now), and gives the Waverunner default as a default: at most 2 new attempts, each at least 5 days after the new pre-notification.",
        "Mentions the advance notice: a Core debit needs pre-notification at least 14 calendar days before collection unless a different period was agreed.",
    ],
    ["Presents the 2 attempts or the 5-day wait as a rule of the SEPA scheme or the EPC.", "Says to collect again at once or the next day."],
    SRC.format(c="AM04"),
)
add(
    "S2", "single",
    "My bank returned a debit with the code MD01. What is that, and may I debit that customer again?",
    [
        "Says MD01 means no mandate (no valid mandate covers the debit).",
        "Says do not collect again until a valid mandate exists (stop meanwhile).",
        "Says the code alone does not say who must act; check the bank's mandate status, a customer cancellation or B2B confirmation, and the mandate reference that was sent.",
    ],
    ["Says to retry the debit.", "States flatly that it is the customer's fault, or flatly the merchant's."],
    SRC.format(c="MD01"),
)
add(
    "S3", "single",
    "We got a refund claim with the reason MD06 on a 59 euro subscription payment. What does it mean, who caused it, and should I charge them again?",
    [
        "Says MD06 means the customer had a Core debit refunded (refund request by the end customer).",
        "Says the cause is either a debit that did not match the amount in the pre-notification, or the customer's unconditional refund right; a refund request alone does not mean the merchant made a mistake.",
        "Says do not retry automatically; talk to the customer before collecting again.",
    ],
    ["Says to charge them again automatically or at once.", "Says a refund request proves the merchant made an error, or proves the customer did something wrong."],
    SRC.format(c="MD06"),
)
add(
    "S4", "single",
    "What does MS03 mean on a returned direct debit? Whose fault is it, and can I charge the customer again?",
    [
        "Says MS03 means the bank gave no specific reason (reason not specified, agent generated).",
        "Says a real reason may be hidden behind it, naming at least two of AC04, AM04, MD07, RR01, RR02, RR03, RR04.",
        "Says ask the customer or the provider which reason applies before any new debit.",
        "Says the default afterwards is one retry, no sooner than 7 days, and with the Core pre-notification of at least 14 calendar days unless agreed otherwise.",
    ],
    ["Says to retry straight away or blind.", "States who is at fault as a fact (the code names no party; it depends on the hidden reason)."],
    SRC.format(c="MS03"),
)
add(
    "S5", "single",
    "A debit came back as AC04. Did the customer do something wrong, and can I just retry next week?",
    [
        "Says AC04 means a closed account number (the customer closed the bank account).",
        "Says the customer caused it: they closed the account after the previous collection.",
        "Says do not collect from the closed account; ask the customer for a new account first.",
    ],
    ["Says to retry the same account next week or soon."],
    SRC.format(c="AC04"),
)
add(
    "S6", "single",
    "One of my long-time subscribers' debits was returned with MD07. What does that mean and what should I do?",
    [
        "Says MD07 means the customer is deceased (end customer deceased).",
        "Says stop collecting and close the agreement; no retry.",
        "Says no party is named as at fault (does not blame anyone).",
    ],
    ["Says to retry or send another payment request to this customer."],
    SRC.format(c="MD07"),
)
add(
    "S7", "single",
    "My customer's bank bounced my debit with SL01. What is that? Do I try again?",
    [
        "Says SL01 means a specific service offered by the customer's bank (for example a creditor block or an amount limit) stopped the debit.",
        "Says no party is named; the cause is a service on the customer's account, such as a block set against the merchant or a limit on amount or frequency.",
        "Says do not collect again before talking to the customer; the block or limit may still apply, so agree how to pay.",
    ],
    ["Says to retry automatically without talking to the customer."],
    SRC.format(c="SL01"),
)
add(
    "S8", "single",
    "A debit was rejected with ED05. What does that mean, and can I simply send it again?",
    [
        "Says ED05 means settlement between the banks failed.",
        "Says the cause is the customer's bank (its funding for settling direct debits with other banks was not enough).",
        "Says the default is one retry, only after the provider confirms settlement can go ahead, and after a new pre-notification (Core: at least 14 calendar days unless agreed otherwise).",
    ],
    ["Says to resend at once or without checking with the provider.", "Blames the customer for ED05."],
    SRC.format(c="ED05"),
)

# ---------------------------------------------------------------- files
cmd = "returns_check.py files/{f} --today {t}"

q, sfx = file_q("2026-11-03", "returns-october.xml",
                "How many debits came back, how much money is that, which ones should I collect again and when, and which should I leave alone?")
add("F1", "file", q,
    [
        "Counts 5 returned debits totalling 200.50 euros (ORDER-1006 with status ACCP is not a return).",
        "Says the two AM04 debits (ORDER-1001 and ORDER-1002, 78.00 euros together) may be collected again, earliest 2026-11-17, and says this assumes a new advance notice sent today.",
        "Says MD01 (ORDER-1004) is a stop until a valid mandate exists, and AC04 (ORDER-1003) is not to be collected from the closed account (needs a new account).",
        "Says MS03 (ORDER-1005) is not retried blind: ask the customer or provider which reason applies first.",
    ],
    ["Counts ORDER-1006 as a return.", "Gives a retry date before 2026-11-17 for the AM04 debits.", "Says to retry MD01, AC04 or MS03 as they are."],
    cmd.format(f="returns-october.xml", t="2026-11-03"), sfx)

q, sfx = file_q("2026-11-03", "returns-october.csv",
                "What should I collect again and when, what do I need to talk to the customer about first, and what do I stop? Add up what came back.")
add("F2", "file", q,
    [
        "Counts 5 returned debits totalling 1,395.90 euros.",
        "Says the AM04 debit (ORDER-2001, 39.00) can be collected again, earliest 2026-11-17.",
        "Says MD07 (1,239.00) is a stop and close the agreement, and MD06 (59.00) and SL01 (39.00) need a talk with the customer first, no automatic retry.",
        "Says AB05 is not one of the 25 codes in the guidance and sends the merchant to the bank or provider rather than giving a collect-again rule for it as known.",
    ],
    ["Gets the total wrong (for example reads 1.239,00 as 1.239).", "Says to retry MD07, MD06 or SL01 automatically."],
    cmd.format(f="returns-october.csv", t="2026-11-03"), sfx)

q, sfx = file_q("2026-11-04", "returns-camt054-november.xml",
                "Which of these should I collect again, on what date, and which ones need something done first? Give me the totals too.")
add("F3", "file", q,
    [
        "Counts 6 returned debits totalling 323.40 euros; the 250.00 payout entry (PAYOUT-0042) is not a return.",
        "Says three debits can be collected again (AM04 SUB-7001 49.90 and SUB-7002 120.00, ED05 SUB-7003 30.00; 199.90 together), earliest 2026-11-18, assuming a new advance notice sent today.",
        "Says AC01 (SUB-7004, 75.50) is not collected until the IBAN is corrected.",
        "Says MD06 (SUB-7005) and MS03 (SUB-7006) are not retried automatically: talk to the customer, or ask the customer or provider which reason applies.",
    ],
    ["Counts the 250.00 payout as a return.", "Gives a retry date before 2026-11-18.", "Says to retry AC01, MD06 or MS03 as they are."],
    cmd.format(f="returns-camt054-november.xml", t="2026-11-04"), sfx)

q, sfx = file_q("2026-11-12", "mahnungen-nov.csv",
                "What do I collect again and when, and what needs a talk, a fix or a stop? How much money is that in all?")
add("F4", "file", q,
    [
        "Counts 7 returned debits totalling 5,004.25 euros (the last row with no reason code is not a return) and reads the European numbers right (1.249,00 is 1,249.00).",
        "Says only the AM04 debit (MND-0001, 1,249.00) can be collected again, earliest 2026-11-26, assuming a new advance notice sent today.",
        "Says MD01 (12.00) is a stop, AC04 (39.90) needs a new account, and MD06 (89.50), MS03 (2,500.75) and SL01 (24.00) need a talk or a question to the customer or provider first.",
        "Says XX99 (1,089.10) is not one of the 25 codes in the guidance and does not state a meaning for it; sends the merchant to the bank or provider.",
    ],
    ["Gets an amount wrong because of the European number format.", "Counts the row with an empty reason code as a return.", "States a meaning for XX99."],
    cmd.format(f="mahnungen-nov.csv", t="2026-11-12"), sfx)

q, sfx = file_q("2026-11-03", "returns-october.csv",
                "My provider charges me 0.35 euros for each failed debit and 5 euros for each refund claim. What did these returns cost me in fees, and how much money did I not collect?")
add("F5", "file", q,
    [
        "Says 5 debits came back and 1,395.90 euros was not collected.",
        "Gives the fees as 6.05 euros: 3 failed debits (AM04, MD07, SL01) at 0.35 plus 1 refund claim (MD06) at 5.00; the AB05 debit carries no fee because its code is outside the 25.",
        "Reports the money not collected and the fees as two separate figures, not added into one sum.",
        "Says AB05 is not one of the 25 codes in the guidance, so it is not counted as a failed debit with a fee.",
    ],
    ["Adds the fees and the uncollected amount into one figure.", "Gives a fee total other than 6.05 (for example 7.40 by counting AB05 as a failed debit)."],
    "returns_check.py files/returns-october.csv --today 2026-11-03 --fee-failed 0.35 --fee-refund 5", sfx)

q, sfx = file_q("2026-11-04", "returns-camt054-november.xml",
                "I collect through Mollie. Which of these might Mollie already be retrying or cancelling on its own, and what should I do myself?")
add("F6", "file", q,
    [
        "Says that for AM04, Mollie may retry subscriptions (up to 5 times, once daily, depending on the failure reason) and the merchant should check the provider's schedule before adding an own attempt.",
        "Says that after AC01 Mollie may cancel the subscription at once, so the IBAN must be corrected.",
        "Says that Mollie may cancel the subscription after 3 failures with MS03, and after 3 MD06 failures.",
        "Says the merchant still talks to the customer for MD06 and asks first for MS03.",
    ],
    ["States that Mollie retries or cancels for ED05 (the data has no Mollie note for ED05).", "Gives Mollie behaviour the data does not state, as fact."],
    "data/codes.json collectAgainDetail and description texts naming Mollie, for the codes in files/returns-camt054-november.xml", sfx)

# ---------------------------------------------------------------- traps
add(
    "T1", "trap",
    "My bank sent back a debit with the code AB05. What does AB05 mean and when can I debit again?",
    [
        "Says AB05 is not one of the 25 SEPA Direct Debit reason codes covered (or that it cannot confirm it from this guidance).",
        "Does not state a meaning or a collect-again rule for AB05 as known fact.",
        "Sends the merchant to their bank or payment provider for the meaning.",
    ],
    ["States a meaning for AB05 as fact.", "Gives a retry date or retry rule for AB05."],
    "returns_check.py --code AB05 (exit 2: not one of the 25 reason codes in the EPC guidance)",
)
add(
    "T2", "trap",
    "A debit came back with MS03. Can I just retry it next week?",
    [
        "Says no: do not retry blind; first ask the customer or provider which reason applies.",
        "Says MS03 can stand in for another code (AC04, AM04, MD07, RR01 to RR04), for example a closed account, insufficient funds or a death.",
        "Says that even if you retry, the default is one retry, no sooner than 7 days, and with a Core pre-notification of at least 14 calendar days unless agreed otherwise, so next week is too early.",
    ],
    ["Says yes, retry next week.", "Gives a retry date next week."],
    SRC.format(c="MS03"),
)
add(
    "T3", "trap",
    "A customer got a refund on their last payment, the reason on the bank file is MD06. Can I charge them again right away?",
    [
        "Says no automatic retry; talk to the customer first (Waverunner recommends no automatic retry).",
        "Says the refund may be the customer's unconditional refund right, or the debit may not have matched the amount in the pre-notification; a refund request alone does not mean the merchant made a mistake.",
        "Says MD06 is a refund claim and applies to Core debits only.",
    ],
    ["Says yes, charge again right away.", "Says the refund proves the merchant erred or the customer cheated."],
    SRC.format(c="MD06"),
)
add(
    "T4", "trap",
    "Today is Saturday 2026-11-07 and I am sending the customer a new advance notice today. A 45 euro AM04 debit from 2 November 2026 came back. What is the earliest date I can collect again?",
    [
        "Gives 2026-11-23 (Monday) as the earliest date.",
        "Does not give Saturday 2026-11-21 as the date (it is a weekend day).",
        "States the assumption: a Core advance notice of 14 calendar days from today, unless a different period was agreed with the customer.",
    ],
    ["Gives 2026-11-21 as the collection date.", "Gives a date earlier than 2026-11-21."],
    "returns_check.py files/weekend-one-row.csv --today 2026-11-07 gives retryOn 2026-11-23",
)
add(
    "T5", "trap",
    "What is the maximum number of times the SEPA scheme lets me re-present a failed AM04 debit, and how long must I wait between tries?",
    [
        "Says the scheme (EPC) sets no retry rule; any limit or wait is a default or a provider setting.",
        "Gives the Waverunner default as a default: at most 2 new attempts, each at least 5 days after the pre-notification with the new date.",
        "Mentions the Core advance notice of at least 14 calendar days before collection unless a different period was agreed.",
        "Says provider schedules differ (Stripe at most twice within 30 days if enabled; Mollie up to 5 times, once daily) and to check the provider's schedule.",
    ],
    ["States a retry limit or waiting period as a SEPA scheme or EPC rule."],
    "data/codes.json AM04 collectAgainDetail and returns_check.py output field source.defaults",
)
body = strip_comments((F / "statement-camt053-no-returns.xml").read_text(encoding="utf-8")).strip()
add(
    "T6", "trap",
    "Today is 2026-11-05. Here is my bank statement for this week:\n\n" + body + "\n\nWhich returned debits should I collect again, and when?",
    [
        "Says there are no returned or rejected debits (no reason codes) in this file.",
        "Does not invent returned debits and does not recommend collecting again any of the three entries.",
        "Says what is missing: a return file or statement with reason codes for returned debits.",
    ],
    ["Lists any entry of the file as a returned debit to collect again.", "Invents a reason code for an entry."],
    "returns_check.py files/statement-camt053-no-returns.xml (exit 2: no returned or rejected debits with a reason code)",
    "(The same file is saved in this folder as files/statement-camt053-no-returns.xml.)",
)

TYPES = {  # what each key point rests on: scheme = EPC guidance or rulebook, default = a Waverunner default,
    # file = arithmetic on the file, provider = a note about Stripe or Mollie
    "S1": "scheme scheme default scheme", "S2": "scheme default scheme", "S3": "scheme scheme default",
    "S4": "scheme scheme default default", "S5": "scheme scheme default", "S6": "scheme default scheme",
    "S7": "scheme scheme default", "S8": "scheme scheme default",
    "F1": "file default default default", "F2": "file default default scheme", "F3": "file default default default",
    "F4": "file default default scheme", "F5": "file file file scheme", "F6": "provider provider provider default",
    "T1": "scheme scheme scheme", "T2": "default scheme default", "T3": "default scheme scheme",
    "T4": "default default scheme", "T5": "scheme default scheme provider", "T6": "file file file",
}
for q in questions:
    types = TYPES[q["id"]].split()
    assert len(types) == len(q["keyPoints"]), q["id"]
    q["keyPoints"] = [{"n": i + 1, "text": t, "type": ty} for i, (t, ty) in enumerate(zip(q["keyPoints"], types))]

assert len(questions) == 20
for q in questions:
    assert 2 <= len(q["keyPoints"]) <= 4, q["id"]

(HERE / "panel.json").write_text(json.dumps({"today": "2026-11-24", "questions": questions}, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote panel.json with", len(questions), "questions")
