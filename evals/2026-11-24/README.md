# Does the sepa-returns-check skill help? A small test, 2026-11-24

Short answer: yes on exact numbers, dates and "what is a default and what is a rule", and no measurable
gain on plain code meanings. But the key was written from the skill's own data, so the skill's 100% shows that
it passes its data on faithfully. It does not show that the data is right in the real world. Read "Limits" before
quoting any number.

## What was tested

One question, asked in a shop owner's words: **does an assistant answer questions about returned SEPA Direct Debits
better with the skill than without it?**

- **Skill under test:** `skills/sepa-returns-check` of the plugin `payments`, called `payments-skills` on the day of the test (marketplace `waverunner-ai/skills`).
  The installed copy was compared with the local folder first: same content, only line endings differ.
- **Model:** Sonnet for every answer run (`claude-sonnet-5-5`, read from each run's start event). No larger model anywhere.
- **Method:** headless Claude Code, one fresh `claude -p` per answer (no shared memory between runs), run by `run.py`.
  The fallback with subagents was not needed.
  - **Arm A, no skill:** no tools at all, no web, no MCP servers, no skills, run from an empty git folder.
  - **Arm B, with skill:** the plugin installed at project scope in its own git folder. Tools: Bash, Read, Glob and Skill only.
    Bash was allowed for `python` and `cd` only. No web. The five files it needs were in a `files/` folder.
  - **Both arms:** user settings, MCP servers and user skills switched off (`--setting-sources project,local`,
    `--strict-mcp-config`), no saved session, refusals instead of prompts (`dontAsk`). Raw output of every run was kept locally (`raw/`, not in the repo).
- **Panel:** 20 questions, written with the answer key BEFORE any answer run (`build_panel.py` makes `panel.json`).
  - 8 single-code questions: AM04, MD01, MD06, MS03, AC04, MD07, SL01 and ED05 (the rarer one).
  - 6 file questions: the two example files, two small invented files of mine (a camt.054 and a German CSV with a
    name column and European numbers like `1.249,00 EUR`), and two more questions on those files (the merchant's own
    fees; "I use Mollie"). "Today" is fixed in the question text.
  - 6 trap questions: a code outside the 25 (AB05), "retry MS03 next week?", "charge MD06 again right away?", a retry
    date that lands on a weekend, "what is the SEPA retry maximum?" (the honest answer is that the scheme sets none),
    and a statement with no returns in it.
- **Key:** only from `data/codes.json` and from the output of `returns_check.py` on the files. 2 to 4 checkable
  points per question, each tagged `scheme` (EPC text), `default` (a Waverunner default), `file` (arithmetic on the
  file) or `provider` (a Stripe or Mollie note), plus a list of statements the key marks wrong.
- **Scoring:** each point 1 or 0. Per answer, two flags: **wrong** = says something the key marks wrong;
  **invented** = states a rule, number, deadline or meaning as fact that the key does not support. "Invented" means
  "not in the key", not "false in the world" (see Limits). Answers were shuffled under random ids and scored without
  the arm label (`blind.py`, `scoring_blind.py`); `blind_map.json` holds the mapping.

## Headline numbers

| | Arm A, no skill | Arm B, with skill |
| --- | --- | --- |
| Key points met | **49 of 69 (71%)** | **69 of 69 (100%)** |
| Single-code questions | 20 of 26 | 26 of 26 |
| File questions | 16 of 24 | 24 of 24 |
| Trap questions | 13 of 19 | 19 of 19 |
| Answers with a wrong statement | 5 of 20 | 0 of 20 |
| Answers with an invented fact | 17 of 20 | 0 of 20 |

By kind of point (met of possible): arm A got scheme facts 20 of 29, Waverunner defaults 19 of 26, file arithmetic
8 of 10, provider notes 2 of 4. Arm B got every one.

**Did the skill load?** In all 20 arm B runs the Skill tool was called, and in all 20 the script actually ran
(`telemetry.csv`, read from the tool calls, not from the answers). 18 runs gave normal output; for T1 (AB05) and T6
(no returns) the script exited with code 2 and its built-in message, which is the designed behaviour. In T4 the
assistant used `--code AM04` and worked the date out by the skill's rules. No run needed a retry. Cost of all 40
answer runs: about 1.70 USD.

Arm A tied arm B on 8 of the 20 questions (S2, S3, S5, S7, F1, F4, T4, T6). On these, plain Sonnet already had the
meaning and the right action. Arm B was ahead on the other 12.

## All 20 questions

Points met out of points possible. "wrong" and "invented" are the flags above.

| Q | Topic | Arm A, no skill | Arm B, with skill |
| --- | --- | --- | --- |
| S1 | AM04: meaning, fault, retry | 2/4 (wrong, invented) | 4/4 |
| S2 | MD01 | 3/3 (invented) | 3/3 |
| S3 | MD06 refund claim | 3/3 (invented) | 3/3 |
| S4 | MS03 | 3/4 (invented) | 4/4 |
| S5 | AC04, retry next week | 3/3 (invented) | 3/3 |
| S6 | MD07 | 2/3 (invented) | 3/3 |
| S7 | SL01 | 3/3 | 3/3 |
| S8 | ED05 (the rarer code) | 1/3 (invented) | 3/3 |
| F1 | pain.002 example file, today 2026-11-03 | 4/4 (invented) | 4/4 |
| F2 | CSV example file (has AB05), 2026-11-03 | 2/4 (invented) | 4/4 |
| F3 | camt.054 file I made, 2026-11-04 | 3/4 (wrong, invented) | 4/4 |
| F4 | German CSV with names, 2026-11-12 | 4/4 | 4/4 |
| F5 | CSV example plus the merchant's own fees | 1/4 (wrong, invented) | 4/4 |
| F6 | camt.054, "I use Mollie" | 2/4 (wrong, invented) | 4/4 |
| T1 | AB05, a code outside the 25 | 0/3 (wrong, invented) | 3/3 |
| T2 | "just retry MS03 next week?" | 2/3 (invented) | 3/3 |
| T3 | "charge MD06 again right away?" | 2/3 (invented) | 3/3 |
| T4 | weekend retry date (Saturday 2026-11-07) | 3/3 (invented) | 3/3 |
| T5 | "what is the SEPA retry maximum?" | 3/4 (invented) | 4/4 |
| T6 | statement with no returns in it | 3/3 | 3/3 |

Per-answer detail with a note for every flag: `scores.csv`.

## The three clearest failures of each arm

**Arm A, no skill** (answers in `answers/A/`)

1. **F3, wrong retry date.** For the camt.054 file with today 2026-11-04 it wrote: "The earliest possible due date is
   2026-11-05, because SEPA Core needs submission one business day ahead." The key date is 2026-11-18, one 14-day
   advance notice later. A merchant following this would collect without the notice.
2. **F5, wrong fees, one figure.** With fees of 0.35 and 5.00 it gave "Fees: 6.75 EUR" (key: 6.05; it counted the
   refund claim twice) and then "Including fees, the returns cost you 1,402.65 EUR", adding money not collected and
   fees into one sum. It also called the AB05 debit "worth re-presenting".
3. **F6, Mollie.** For a Mollie merchant it said the subscription "usually carries on at the next interval, with no
   automatic same-cycle retry". The data says Mollie may retry an AM04 subscription up to 5 times, once a day, so
   the merchant could add a second, double attempt.

Also worth knowing: on T1 it said AB05 is "Timeout Creditor Agent" and the debit can go "usually right away", with no
pointer to the bank. The key marks that wrong because AB05 is outside the 25 codes. In the real world AB05 is in the
ISO list, so this may be true (see Limits). S1 also said the fault is "generally not yours", where the key says the
merchant's late or missing advance notice can cause AM04.

**Arm B, with skill** (answers in `answers/B/`). Nothing failed against the key, so these are the weakest spots found
outside it:

1. **F6, wrong "today".** The question said "Today is 2026-11-04", but the assistant ran the script with
   `--today 2026-11-24` (the system date). It gave 8 December as the earliest date, and added that with a notice on
   4 November it would be 18 November. The caveat was there, the first date was wrong for the stated day. The other
   six dated file runs passed the stated date correctly.
2. **F6, fees for the wrong provider.** The merchant said Mollie. It still used the script's default fees (Stripe, Ireland),
   but said so and asked for the Mollie fees.
3. **T1, a guess beyond the data.** On AB05 it correctly said the code is not one of the 25 and sent the merchant to the
   bank, but also wrote "It's probably not a standard SEPA code. Some banks ... send their own internal codes". That is
   a hedge from nowhere in the data. I scored it fine because it states no meaning and no rule.

Style, not scored: arm B answers are longer and often add Stripe and Mollie notes and a customer message nobody asked for.

## Found in passing (not fixed)

1. **The skill can be blocked by a strict Bash allow-list.** SKILL.md says paths are relative to the skill's folder, so
   the assistant runs `cd "<plugin folder>" && python scripts/returns_check.py ...`. With only `Bash(python:*)`
   allowed, that compound command was refused in my first throwaway run, and the assistant fell back to reading
   `codes.json` by hand. It worked once I also allowed `cd` and added the plugin folder as a working directory. In an
   interactive session the user would just approve the prompt. SKILL.md also never states the absolute path; the
   assistant found it from the plugin list.
2. **German CSV headers are not recognised for the date.** In `scripts/returns_check.py`, `DATE_HEADER` matches
   `date|datum|fecha|data|dt`. The header `Faelligkeit` (and `Fälligkeit`) matches none, so my German CSV rows came out
   with no `date`. It changed nothing in this test, because the retry date came from "today plus 14 days", but a
   collection date after "today" would be ignored.
3. **Default fees are Stripe's, even when the merchant names another provider.** The skill says to pass the merchant's
   fees; when none are given the Stripe figure is used and labelled. The assistant did label it (F6, F1, F2, F3, F4).

(The odd `�` I saw next to "customer's bank" in `codes.json` was my terminal, not the file.)

## Limits of this test

- **The key is circular.** I wrote it only from `codes.json` and the script's output, as asked. Arm B reads exactly
  that data, so 69 of 69 shows faithful passing on, not that the data is right. Arm A never saw the data, so some of
  its misses are "does not know a Waverunner default", which cannot be known from outside. By the tags: arm A's
  `default` and `provider` points were 21 of 30 while its `scheme` and `file` points were 28 of 39.
- **"Invented" does not mean false.** Arm A's 17 flags are mostly real SEPA facts the key does not hold: the 8-week and
  13-month refund windows, the 36-month mandate lapse, the D-1 submission deadline, AB05 as an ISO code. A merchant
  may well be helped by those. I did not check them against the rulebook.
- **One model, one run each, n = 20 questions.** No repeats, so run-to-run noise is unknown (one F6 date slip may be
  noise). The differences on single questions (one point) mean little; the gap overall is large.
- **I wrote the questions and the key, and I scored.** One Sonnet scorer, with judgement calls on a few points
  (for example T5 point 4 and S6 point 3 were scored on the gist). Blind scoring was only partial: answers often name
  "Waverunner default" or "the returns checker", and arm A answers mention a code repo, so the arm was often
  recognisable.
- **The two arms did not get identical conditions.** Arm B's questions about files added one line telling it where
  the file is stored (the same text was pasted in both). Arm B needed `Bash(cd:*)` and the plugin folder as an added
  directory (see Found in passing). Both ran under Claude Code's own system prompt, so some answers mention "my
  environment says 24 Nov" or "your repo".
- **The question mix favours the skill.** F1 and F2 are the skill's own example files; four trap questions test exactly
  what SKILL.md warns about.
- **Four throwaway runs** outside the panel (an RC01 question twice, a file question twice) were used to test the
  setup. They are not counted and not kept.
- Not tested: real merchants, other models, longer sessions, privacy of the output (arm A repeated customer names from
  the German CSV, arm B did not).

## Files here

| File | What it is |
| --- | --- |
| `panel.json` | the 20 questions and the key (made by `build_panel.py` from `files/`) |
| `files/` | the two example files plus my three invented files and a one-row file used only to derive the weekend key |
| `answers/A/`, `answers/B/` | raw answer text per question |
| `raw/` | the full stream of every run; kept out of the repo because the logs carry the test machine's paths |
| `telemetry.csv`, `telemetry.py` | skill loaded and script ran, read from the tool calls |
| `scores.csv` | points per answer, flags and a note |
| `scoring_blind.py`, `blind.py`, `blind_map.json` | the blind scoring record and the shuffle |
| `run.py`, `make_table.py` | the runner and the table maker |

To repeat: build two scratch git folders; in the second run
`claude plugin marketplace add waverunner-ai/skills --scope project` and
`claude plugin install payments@waverunner-ai --scope project`; copy the five question files into its `files/`;
point `run.py` at both folders and run `python run.py`; then `python telemetry.py`. The exact flags are at the top of
`run.py`. The plugin and the marketplace were uninstalled afterwards and the marketplace list matches the one from
before the test.
