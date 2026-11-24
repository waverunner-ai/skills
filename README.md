# Waverunner skills

Skills for people who run online shops and subscriptions, for use with Claude and other assistants that read the
open skill format. A skill is a folder of instructions and data that an assistant loads when your
question fits it.

Each skill here does one payments job in full, with no account, no API key and no email. The scripts run on your
own machine and open no network connection.

## Skills

| Skill | What it does |
| --- | --- |
| [sepa-returns-check](skills/sepa-returns-check/) | Reads a month's SEPA Direct Debit return file and tells you which debits to collect again, on what date, which need a fix or a talk with the customer first, and which to stop. Also explains any single reason code. |

More will follow.

## SEPA returns check

When a SEPA Direct Debit fails, the bank sends it back with a four-character reason code: AM04 for insufficient
funds, MD01 for no mandate, MD06 when the customer claimed a refund, and 22 others. The code decides what you may do
next. Collecting again on the wrong code costs another fee, and on some codes no valid mandate covers the debit
at all.

Give the skill your return file and ask:

> Here is last month's return file. What do I collect again, and when?

You get:

- how many debits came back, what they total, and the fees charged for them
- each debit sorted into one of four groups: collect again later, fix first, talk to the customer, stop
- the earliest date each retry may go out
- a message to send the customer, per code

It reads pain.002, camt.054 and camt.053 files in any version, and CSV or TSV exports from a bank or a payment
provider.

### What it reads, and what it does not

The script takes four things per returned debit: the reason code, the amount, a date and the debit's own reference.
It does not read the name or account fields, it drops a reference that holds an IBAN, and it opens no
network connection. You can check all three in
[returns_check.py](skills/sepa-returns-check/scripts/returns_check.py): one file, standard library only.

Two things to know. A reference is whatever you put in it: if yours hold customer names, add `--no-references`. And
the script's output goes to your assistant, like anything else you give it.

### Facts and defaults

The code names and meanings come from the European Payments Council's guidance on reason codes (EPC173-14, version
8.1, 30 September 2026). Whether to collect again, how long to wait and how many times are Waverunner's defaults: the
EPC sets no retry rule. The skill keeps the two apart in every answer.

## Install

**Claude Code**

```
/plugin marketplace add waverunner-ai/skills
/plugin install payments@waverunner-ai
```

**Any other assistant that reads skills:** copy `skills/sepa-returns-check/` into its skills folder.

**No assistant at all:**

```bash
python skills/sepa-returns-check/scripts/returns_check.py skills/sepa-returns-check/examples/returns-october.xml
```

It needs Python 3.9 or newer and nothing else.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Who makes this

[Waverunner](https://waverunner.ai) is a platform for running subscription and repeat-order businesses, SEPA Direct
Debit included.

The same decoder runs in the browser at
[waverunner.ai/tools/sepa-return-codes](https://waverunner.ai/tools/sepa-return-codes/).

## Licence

Code: MIT. The data file `skills/sepa-returns-check/data/codes.json`: Waverunner's defaults and text are under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the codes, names and types are the EPC's and ISO 20022's.
