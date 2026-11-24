---
name: sepa-returns-check
description: Reads a SEPA Direct Debit return file (pain.002, camt.054, camt.053, or a CSV export from a bank or payment provider) and tells the merchant which returned debits to collect again, on what date, which need a fix or a talk with the customer first, and which to stop. Also explains a single reason code such as AM04, MD01, MD06 or MS03. Use when someone shares a return file, asks why a direct debit bounced, failed or was returned, asks what a SEPA reason code means, or asks whether and when they may debit a customer again.
license: MIT
---

# SEPA returns check

A returned SEPA Direct Debit comes back with a four-character reason code. The code decides what the merchant may do
next: collect again later, fix something first, talk to the customer, or stop. This skill reads a whole file of
returns and gives that answer per debit, with the earliest date a new attempt may go out.

## What you need

- Python 3.9 or newer. The script uses the standard library only and opens no network connection.
- The merchant's return file, or one reason code.

## Run it

The script sits in this skill's folder, the one that holds this file. Call it by its full path
(`python <skill folder>/scripts/returns_check.py ...`) and do not change directory first: the script finds its own
data, and some setups allow `python` but refuse `cd`. The lines below show the path from the skill folder. Always
pass `--today` when the merchant names a date; without it the script uses the machine's date.

A file:

```bash
python scripts/returns_check.py <path-to-file> --today <YYYY-MM-DD>
```

One code:

```bash
python scripts/returns_check.py --code AM04
```

Options:

| Option | What it does | Default |
| --- | --- | --- |
| `--today` | The day a new advance notice to the customer would go out | today |
| `--fee-failed` | What the merchant's bank or provider charges per failed debit, in euros | 3.50 |
| `--fee-refund` | What it charges per refund claim (code MD06), in euros | 15.00 |
| `--no-rows` | Leaves out the per-debit list, for a very large file | off |
| `--no-references` | Leaves each debit's reference out of the list | off |

The fee defaults are Stripe's published prices for Ireland, read on 30 October 2026. If the merchant gives one fee or
both, pass what they gave. `feesUsed` in the output says where each fee came from; say so in the answer.

To try it without a real file, use `examples/returns-october.xml` or `examples/returns-october.csv`.

## What the output holds

One JSON object:

- `returns`, `amount`, `fees`: how many debits came back, what they total, and the fees charged for them. The amount
  is money that was not collected, not money lost: report it and the fees as two figures, never as one sum.
- `buckets`: the returns with a known code, sorted into four groups.
  - `retry`: collect again later.
  - `fix`: correct the account, the mandate or the file first.
  - `contact`: talk to the customer before any new collection.
  - `stop`: do not collect again on this mandate.
- `unknown`: debits whose code is outside the 25 that the scheme's guidance covers. They sit in no group and carry no
  fee, so the four groups and `unknown` together add up to `returns`. Do not guess what such a code means; tell the
  merchant to ask their bank or provider.
- `byCode`: each code in the file with its name, meaning, who caused it, the collect-again answer, a message for the
  customer, and a page with the full explanation.
- `retryCalendar`: the `retry` debits totalled per day: how many may go out again on each date, and their amount.
- `rows`: each debit with its reference, its date, its decision and, for a `retry` debit, `retryOn`, the earliest
  date for that debit. `date` is the collection date in a pain.002 or CSV file and the booking date in a camt file.

## How to answer

1. Lead with the count and the money: how many debits came back, what they total, the fees, and how the groups split.
2. Then one short table, a row per code: code, what it means in plain words, how many, the amount, what to do.
3. Give the retry dates as dates. Say what they assume (see the rules below).
4. Offer the customer messages for the codes in the file. Each has the placeholders `[amount]`, `[date]` and `[link]`.
   Fill the first two from `rows`. Leave `[link]` for the merchant: it is a page of their own shop.
5. For a single code, answer in three parts: what it means, who caused it, whether to collect again. `--code` gives
   no date. If the merchant asks when, say the earliest is the day the advance notice period ends, and work out a
   date only if they tell you when the notice goes out.

## Rules that keep the answer right

- **Scheme facts and defaults are different things. Keep them apart.** The code names, how a code arrives and which
  scheme it belongs to come from the European Payments Council's guidance (EPC173-14, version 8.1, 30 September 2026).
  Whether to collect again, how long to wait and how many times are Waverunner's defaults. The EPC sets no retry rule.
  When the data says "our 5-day wait", write "a default wait of 5 days".
- **A retry date assumes a new advance notice.** The Core scheme asks the merchant to tell the customer about a debit
  at least 14 calendar days ahead, unless the two agreed a different period. Each retry date is the later of that
  notice, counted from `--today`, and the default wait, moved to Monday when it falls on a weekend. If the merchant
  agreed a different notice period with the customer, say the date changes with it and do not invent one.
- **MS03 hides the real reason.** A bank may send MS03 ("reason not specified") in place of the true code. Any code
  with `canArriveAsMs03: true` may be behind it. So an MS03 is never retried blind: the merchant asks the customer or
  the provider which reason applies first.
- **Never retry a `stop` or `contact` debit to see what happens.** With MD01 no valid mandate covers the debit. With
  MD06 the customer had the debit refunded; the merchant talks to them before any new debit.
- **Provider notes apply only to that provider.** Some texts say what Stripe or Mollie does. Pass such a note on only
  when the merchant uses that provider, or say plainly that it applies to that provider.
- **Add nothing the output does not say.** No meaning for an unknown code, no extra legal step, no timing rule from
  memory. If the merchant needs more, the code's page (`page`) is the place to send them.
- **Read nothing beyond the script's output.** The script takes only the code, amount, date and the debit's own
  reference from the file. Do not open the file yourself to pull out names or account numbers, and do not repeat any
  that the merchant pastes. A reference is whatever the merchant put in it; if their references hold customer names,
  run with `--no-references`.
- **This is not legal advice.** A merchant with a dispute over a mandate should ask their bank or a lawyer.

## If it fails

The script exits with code 2 and prints `{"error": "..."}` in words meant for the merchant. Pass that message on. The
usual causes: the file is a statement with no returns in it, the CSV has no column of reason codes, or the export is
not valid XML.

## Where the data comes from

`data/codes.json` is a copy of the open file at https://waverunner.ai/tools/sepa-return-codes/codes.json. Waverunner's
defaults and text in it are under CC BY 4.0; the codes, names and types are the EPC's and ISO 20022's. The same decoder
runs in the browser at https://waverunner.ai/tools/sepa-return-codes/ for anyone who would rather not use a terminal.
