# Does the chargeback-ratio-check skill help? A small test, 2026-11-24

Short answer: with the skill every key point was met (62 of 62), with no wrong statement and no verdict. Without it,
Sonnet met 35 of 62 (56%), made 5 wrong statements and gave 6 verdicts. But the key was written from the website's
guide and the skill restates that same guide, so the 100% shows that the skill passes the guide on faithfully, not that
the guide is right in the real world. Read "Limits" before quoting any number.

## What was tested

One question: **does an assistant answer chargeback-ratio questions better with the skill than without it?**

- **Skill under test:** `skills/chargeback-ratio-check` of the plugin `payments` (marketplace `waverunner-ai`), from the
  local checkout of branch `skill/chargeback-ratio-check` (commit a0947a9, not pushed). The marketplace was added from the
  local folder at project scope. The installed copy was compared with the folder (`diff -r`: identical) before any run.
- **Model:** Sonnet for every answer run and every scoring run (`claude-sonnet-5-5`, read from each run's start event).
- **Method (as in `evals/2026-11-24/`):** one fresh headless `claude -p` per answer, no saved session, run by `run.py`.
  - **Arm A, no skill:** no tools, no skills, no MCP servers, run from an empty git folder.
  - **Arm B, with skill:** the plugin installed at project scope in its own git folder. Tools: Bash, Read and Skill only.
    Bash allowed for `python` only (this skill says to call its script by full path, so `cd` was not needed or allowed).
    The installed plugin folder was added as a working directory. No web.
  - **Both arms:** user settings, MCP servers and user skills off (`--setting-sources project,local`,
    `--strict-mcp-config`), refusals instead of prompts (`dontAsk`). The raw stream of every run is kept locally in
    `raw/` (not in the repo).
  - Changes from the earlier runner: Glob and `cd` are no longer allowed, and the telemetry counts a refused call of any tool.
- **Panel:** 20 questions with the key, written before the skill was built from the website's reviewed text
  (`panel.json`; every key point carries a type and a `ref` into the site's source files).
  - 6 plain (P1 to P6), 8 numbers (N1 to N8), 6 scenarios (S1 to S6).
  - **N7 and N8 are tagged `extension`:** they need arithmetic the skill deliberately does not do (a Visa ratio from
    fraud reports and disputes, with a divisor month the site does not give; a provider fee sum). They were run anyway.
    Every total below is given for all 20 questions and for the 18 core ones.
  - No question needed a file, so there is no `files/` folder.
- **Scoring (blind):** answers were shuffled under random ids (`blind.py`, `blind_map.json`). **The scorer was a fresh
  Sonnet run per answer** (`score.py`: no tools, no arm label, one answer at a time). It was given the question, the key
  points, the `wrong_if` list, the site's guide text (only to tell "not in the key" from "not on the site") and the
  answer. Arm labels were joined back only in `make_table.py`. Flags per answer:
  - **points:** key points met, judged on meaning.
  - **wrong:** 1 if it states anything in `wrong_if` or contradicts the key.
  - **invented:** 1 if it adds a threshold, date, fee, deadline, programme or rule that is not in the key. True facts count.
  - **unsupported (extra):** 1 if one of those additions is also absent from the guide.
  - **verdict (new):** 1 if it tells the merchant they are safe, fine, in a programme, or will be closed, fined or
    listed (or not in a programme, as a settled fact). The skill is meant to give numbers and published thresholds only.
- **Telemetry (arm B):** from the tool calls in the raw logs (`telemetry.py`), not from the answers.

## Headline numbers

| Set | Arm | Key points met | Wrong | Invented (not in key) | Not on the site either | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| All 20 questions | A, no skill | 35 of 62 (56%) | 5 of 20 | 19 of 20 | 18 of 20 | 6 of 20 |
| All 20 questions | B, with skill | 62 of 62 (100%) | 0 of 20 | 20 of 20 | 3 of 20 | 0 of 20 |
| 18 core questions | A, no skill | 32 of 56 (57%) | 5 of 18 | 17 of 18 | 16 of 18 | 5 of 18 |
| 18 core questions | B, with skill | 56 of 56 (100%) | 0 of 18 | 18 of 18 | 2 of 18 | 0 of 18 |

"Invented" is 20 of 20 for arm B by the key's own definition: arm B adds the site's other published lines (Visa, MATCH,
CEMEA, per-count fees) to almost every answer. Against the guide itself only 3 of 20 carry an addition that is not on
the site (see Limits for why that is 2 on facts).

**Did the skill load?** In 19 of 20 arm B runs the Skill tool was called, and in the same 19 the script ran
(`telemetry.csv`). It ran with `--chargebacks` and `--transactions` for the six questions that gave numbers (N1 to N6)
and with `--rules` for the other 13. No script call failed and no tool call of any kind was refused. The one run without
the skill is **P3** (what is a basis point); see "Faults found".

## All 20 questions

Points met out of points possible; flags in brackets. "invented" is against the key, and true facts count.

| Q | Group | Arm A, no skill | Arm B, with skill |
| --- | --- | --- | --- |
| P1 | plain | 2/4 (invented) | 4/4 (invented) |
| P2 | plain | 3/4 (invented) | 4/4 (invented) |
| P3 | plain | 2/2 (invented) | 2/2 (invented) |
| P4 | plain | 1/3 (invented) | 3/3 (invented) |
| P5 | plain | 3/3 (invented) | 3/3 (invented) |
| P6 | plain | 2/3 (invented) | 3/3 (invented) |
| N1 | numbers | 4/4 (invented, verdict) | 4/4 (invented) |
| N2 | numbers | 3/4 (invented) | 4/4 (invented) |
| N3 | numbers | 1/3 (invented, verdict) | 3/3 (invented) |
| N4 | numbers | 3/3 (invented, verdict) | 3/3 (invented) |
| N5 | numbers | 1/2 (wrong, invented) | 2/2 (invented) |
| N6 | numbers | 0/2 (wrong) | 2/2 (invented) |
| N7 (extension) | numbers | 2/3 (invented, verdict) | 3/3 (invented) |
| N8 (extension) | numbers | 1/3 (invented) | 3/3 (invented) |
| S1 | scenario | 2/3 (invented) | 3/3 (invented) |
| S2 | scenario | 2/4 (wrong, invented, verdict) | 4/4 (invented) |
| S3 | scenario | 0/4 (wrong, invented, verdict) | 4/4 (invented) |
| S4 | scenario | 1/2 (invented) | 2/2 (invented) |
| S5 | scenario | 0/3 (wrong, invented) | 3/3 (invented) |
| S6 | scenario | 2/3 (invented) | 3/3 (invented) |

Per-answer detail with a note for every flag: `scores.csv`.

## The three worst arm A failures

1. **S3, MATCH (0 of 4, wrong, verdict).** "Will you be listed? Probably", "within 5 days" (the guide says 5 calendar
   days from the earliest of three events), "Listings last 5 years", and no 1.5% and USD 5,000 test.
2. **S5, Braintree fee (0 of 3, wrong).** A "$5 to $10" per-event range and "about 2.2% in 2025" instead of USD 4 at
   Above Standard and USD 8 at Excessive. It said itself that it was unsure of the amounts.
3. **N6, which month to divide by (0 of 2, wrong).** The headline ratio is 1.5% (45 over this month's 3,000). The correct
   1.8% (45 over October's 2,500) appears only as what "some processors" do, and the 100-chargeback ECM minimum is never
   mentioned.

Also: N5 never said the ratio is "not available" and gave example ratios; S2 gave 2.2% as Visa's line. Arm A gave six
verdicts: N1 "you're not in the excessive tier", N3 "you're in HECM", N4 "probably fine", N7 "almost certainly not", S2, S3.

## Arm B misses against the key

None: 62 of 62 points, 0 wrong, 0 verdict. The weakest spots outside the key:

- **P3 (no skill loaded):** "1.5% is above the thresholds that card networks commonly monitor", a ratio line with no
  minimum count, which the skill's own rules forbid. It is the only arm B answer that is in effect an arm A answer.
- **N7 and N8 (extensions):** after `--rules` the model did the Visa sum (220 bps) and the fee sum (12 x USD 4 = USD 48)
  by hand, correctly, and said the script does not compute them. This shows the skill's facts are enough for the extra
  arithmetic, not that the skill does it.
- **N7:** it tells the merchant "the script doesn't compute Visa's ratio", which is implementation talk.
- **P5:** adds "a lawyer can advise you", which comes from SKILL.md's own rule, not from the guide.
- **N4, N5, S2:** a Visa CEMEA row appears for merchants who gave no region. The answers say "not computed" or that they
  cannot tell which region applies, so it is correct but adds length.

## Key doubts (scored as written)

The key was read against the site's guide (`chargeback-ratio.mdx`, updated 2026-11-06). Everything agrees except:

1. **P5 point 1:** "MATCH is Mastercard's list of terminated merchants (MATCH Pro in the high-risk guide)". This guide calls
   MATCH a "merchant screening system"; the other wording is from a different page.
2. **P5 point 2:** "a frozen account does not have to be reported ... only when the provider closes the account and the
   closure meets a reason code". The guide says the acquirer must report when the account is ended and it has reason to
   believe the merchant qualifies (code 04). It says nothing about a freeze, so the key point is an inference, a fair one.
   Arm B met it ("a freeze alone doesn't trigger it").
3. **N7 and N8** depend on arithmetic or a divisor month the guide does not give; they test the model's sums, not the site.

## Faults found in the skill or its SKILL.md

1. **P3: the skill did not trigger on a pure basis-point question.** The description names ratio questions, ECM, HECM,
   VAMP, MATCH, warnings and fees, but not "my processor's email says 150 bps" or what a basis point is. The answer
   without the skill put 1.5% above "commonly monitored thresholds" with no count. Suggest adding "basis points" and "an
   email or dashboard that quotes a ratio" to the description.
2. **N7: the merchant is told about "the script".** SKILL.md says the script does not compute Visa's ratio and the answer
   repeated that. Suggest the rules say "I cannot compute Visa's ratio from these figures".
3. **N7 and N8: nothing in SKILL.md covers arithmetic the script does not do.** The model did it by hand, correctly and
   with a note that it was its own sum, but the skill neither asks for that note nor says to show the working.
4. No refused tool call and no script error. Calling the script by full path with no `cd` works under `Bash(python:*)`,
   which removes the first "found in passing" item of the SEPA test for this skill.

## Limits of this test

- **The key is circular in one direction.** It was written from the site's text and the skill restates the same text. Arm A
  never saw the site, so some of its misses are "does not know the site's figure". Whether the guide is right in the real
  world was not checked.
- **"Invented" does not mean false.** Arm A's additions include a 2.2% Visa figure for 2025, VDMP and VFMP history and a
  5-year MATCH listing, which may be true in the real world. They were not checked against the networks' rulebooks.
- **The scorer is a model, one run per answer, and not fully blind.** Arm B answers say "the guide" or "the script", so the
  arm is often recognisable (the scorer's own note on N7 names "script"). The "unsupported" flag on N7 B is an artefact
  (the word "script", not a fact), so arm B's 3 of 20 is 2 of 20 on facts (P3, P5). I read the arm B answers for N4, N5, N7,
  N8, P3 and P5 and searched all 20 for "safe", "fine", "you are in", "likely" and "probably": no verdict, no wrong
  statement. A different scorer could differ on a point or a flag.
- **One model, one run each, n = 20.** No repeats, so run-to-run noise is unknown, and a one-point gap on a single
  question means little. The gap overall is large.
- **The questions and the key came with the brief;** I did not write or change them.
- **Plugin cache:** the install used the local folder as the marketplace source. `plugin uninstall` left the version
  folder `0.2.0` in the plugin cache (a `0.1.0` was already there from the earlier test); it is inert and was not deleted.
- Not tested: real merchants, other models, longer sessions, the published (pushed) version of the plugin.

## Cost and runs

40 answer runs (20 per arm; all succeeded first time, no retries) and 40 scorer runs (one needed a second try because the
first reply was not parseable JSON). The answer runs cost about 2.30 USD (A 0.48, B 1.83); scoring about 1.73 USD (the
guide text is in every scoring prompt); about 4.03 USD in all.

## Files here

| File | What it is |
| --- | --- |
| `panel.json` | the 20 questions and the key (written beforehand) |
| `answers/A/`, `answers/B/` | raw answer text per question |
| `raw/` | the full stream of every run; kept out of the repo because the logs carry the test machine's paths |
| `telemetry.csv`, `telemetry.py` | skill loaded, script ran, refused calls, cost, read from the tool calls |
| `scores.csv` | points and flags per answer, with a note |
| `scoring_blind.json`, `score.py`, `blind.py`, `blind_map.json` | the blind scorer's output, the scorer, the shuffle and its mapping |
| `run.py`, `make_table.py` | the runner and the table maker |
| `table.md` | the totals and the per-question table |

To repeat: make two scratch git folders; in the second run
`claude plugin marketplace add <path of the checkout> --scope project` and
`claude plugin install payments@waverunner-ai --scope project`; set `EVAL_SCRATCH` (the folder holding `armA` and `armB`)
and `EVAL_PLUGIN_DIR` (the installed plugin folder); run `python run.py` and `python telemetry.py`; run `python blind.py`;
set `EVAL_GUIDE` (the guide's `.mdx` file) and run `python score.py`; then `python make_table.py`. Afterwards uninstall the
plugin, remove the marketplace and compare `claude plugin marketplace list` with the list from before.
