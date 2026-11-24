---
name: chargeback-ratio-check
description: Works out a card chargeback ratio from two numbers, this month's chargebacks and last month's transactions, the way Mastercard counts it, and sets it beside the published Visa, Mastercard and MATCH thresholds, each of which is a ratio and a minimum count, with the source and date behind each one. Use when a shop owner asks what their chargeback ratio is, which month's sales to divide by, whether a ratio such as 1.6% or 160 basis points puts them over Visa's or Mastercard's line, what a ratio quoted in an email or a dashboard from their provider means, what ECM, HECM, VAMP or MATCH mean, whether a dispute they won still counts, or what to ask their payment provider after a chargeback warning, a monitoring fee or a closure notice.
license: MIT
---

# Chargeback ratio check

A chargeback ratio is the share of a merchant's card transactions that came back as chargebacks. Card networks watch
it every month, and every one of their published lines has two parts: a ratio and a minimum count. This skill works
out the ratio from two numbers the merchant gives, the way Mastercard counts it, and sets it beside each published
line with its source and the date that source was read. It states where the numbers sit. It does not judge the
account: the merchant's payment provider confirms which test applies.

Terms used below, defined once:

- **Basis point (bps)**: one hundredth of a percent. 150 bps is 1.5%.
- **Merchant ID**: the identifier of the merchant account that a card network measures.
- **Acquirer**: the bank or processor that settles the merchant's card payments.
- **ECM and HECM**: Mastercard's Excessive Chargeback Merchant and High Excessive Chargeback Merchant levels.
- **VAMP**: the Visa Acquirer Monitoring Program, which has a test for each merchant and levels for each acquirer.
- **MATCH**: Mastercard's merchant screening list; reason code 04 is its excessive chargeback test.
- **CEMEA**: Visa's region for Central Europe, the Middle East and Africa.
- **Card-not-present**: a card payment where the card is not shown in person, such as an online order.
- **Fraud report (TC40)**: a card issuer's flag on a payment it suspects is fraudulent; Stripe and Shopify show it as
  an early fraud warning.

## What you need

- Python 3.9 or newer. The script uses the standard library only and opens no network connection.
- Two numbers from the merchant: the chargebacks received this month, and the card transactions processed last
  month. For Mastercard's count both should be Mastercard only and for one merchant ID; if the merchant has only
  all-card totals, run them and say so in the answer.
- For a plain question with no numbers (which month to divide by, what MATCH is), nothing: run `--rules`.

## Run it

The script sits in this skill's folder, the one that holds this file. Call it by its full path
(`python <skill folder>/scripts/chargeback_check.py ...`) and do not change directory first: the script finds its own
data, and some setups allow `python` but refuse `cd`. The lines below show the path from the skill folder.

The merchant's numbers:

```bash
python scripts/chargeback_check.py --chargebacks 45 --transactions 2500
```

The programmes, facts and questions alone, for a question with no numbers:

```bash
python scripts/chargeback_check.py --rules
```

Options:

| Option | What it does | Default |
| --- | --- | --- |
| `--chargebacks` | Chargebacks received this month, a whole number up to 10,000,000 | none, required with numbers |
| `--transactions` | Card transactions processed last month, a whole number up to 1,000,000,000 | none, required with numbers |
| `--rules` | Prints the programmes, facts and questions for the provider, with no ratio | off |

Both numbers may be written with thousands commas ("98,000"). Following the calculator's own rules, a number below
zero counts as 0, a fraction is rounded to a whole number, and a number over the limit counts as the limit;
`inputNotes` in the output says when that happened. Tell the merchant.

Two worked inputs with their output are in `examples/worked-examples.md`.

## What the output holds

One JSON object:

- `chargebacks`, `transactions`: the counts the calculation used.
- `ratio`, `percent`, `bps`: the ratio as a fraction, in percent and in basis points. All three are `null` when last
  month's transactions are 0: there is nothing to divide by, and the answer is "not available", never 0.
- `display`: the same figures as the guide's calculator prints them ("1.53%", "153.1 bps", "1,500 chargebacks over
  98,000 transactions"). Quote these.
- `method` and `note`: how the ratio was counted, and the calculator's standing note that the provider confirms which
  test applies.
- `programmes`: one entry per published programme or provider rule. Each holds:
  - `threshold`, `ratioCondition`, `minimumConditions`: the published line in words, always both parts.
  - `howItCounts`: what the programme divides by what, and over which month where the guide says so.
  - `region`, `effectiveFrom`, `appliesTo`: as the guide states them, or "not stated in the guide".
  - `basis`: `scheme` (the card network's own document), `secondary` (another company's summary of a network's rule)
    or `provider` (one provider's own rule, for its merchants only).
  - `source`: publisher, title, address and `checked`, the date the guide says that source was read.
  - `onYourNumbers`: for ECM and HECM, each condition with the merchant's figure and `meets` true or false, plus
    `inWords`. A `note` appears when rounding hides which side of the line the ratio is on. For every other
    programme, `computed: false` and `why`: the two numbers are not that programme's count.
  - `assumes`, on ECM and HECM: that the two numbers are Mastercard counts for one merchant ID.
  - `ask`: what to ask the provider about this programme. Some entries also carry `caveat`, `tableOnly`, `when`,
    `publishedFollowUp`, `leaving`, `fees` and `feeNote`.
- `facts`: short rules from the guide (a won dispute still counts, fraud reports count in Visa's ratio, and others),
  each with its source or `null` where the guide states it without one.
- `askYourProvider`: the guide's own lists of questions: always, for a fine, and after a warning or closure notice.
- `basisMeaning`: what `scheme`, `secondary` and `provider` mean, in one line each.
- `source`: the guide the data restates, its address, the date it was last updated, and the date the data was
  copied from it.

## How to answer

1. Lead with the ratio: the percent, the basis points and the counted line from `display`. Say how it was counted:
   this month's chargebacks over last month's transactions, the way Mastercard counts.
2. Then one short table, a row per programme the question touches (usually ECM, HECM, Visa's merchant test and MATCH
   code 04): the published line with both its parts, where the numbers sit against each part, and the source with
   its read date. For a row with `computed: false`, write what that programme counts and that the two numbers do not
   give it.
3. Name the basis wherever it is not the network's own text: "per TabaPay, a payment processor's summary, read
   4 November 2026" for ECM and HECM; "per the guide's table" for the CEMEA figures.
4. Close with what to ask the provider: the programme's `ask`, and the matching list from `askYourProvider` when the
   merchant mentions a fee, a warning or a closure. Repeat the standing note in `note`.
5. For a plain question, run `--rules` and answer from `programmes` and `facts`, with the source and its date.

## Rules that keep the answer right

- **A ratio, never a verdict.** State the numbers and the published lines. Do not call any ratio safe or fine, do
  not say the merchant is in a programme, will be fined or will be closed, and do not predict what an acquirer or a
  provider will do. "Your numbers meet both ECM conditions as the guide states them; your provider confirms whether
  Mastercard counted you" is the form.
- **A published follow-up is the programme's, not the merchant's future.** `publishedFollowUp`, `when` and `leaving`
  say what the named source lists for the programme. Give them as "per TabaPay, the ECM level comes with a
  remediation plan and assessments from month 2", never as what will happen to this merchant.
- **Every line is a ratio and a minimum.** Never give a ratio line without its minimum count or amount. A small
  account can pass a ratio and still miss the minimum; say both.
- **Visa is not chargebacks alone.** Visa's ratio counts card-not-present fraud reports plus disputes over settled
  transactions, so it cannot be worked out from chargebacks and sales alone. Say that to the merchant in those terms,
  not as something a script lacks. If the merchant gives fraud reports and settled transactions and you do the sum
  yourself, label it as your own arithmetic, not a figure from this skill. Give Visa's published line and send the merchant to the provider
  for their VAMP ratio and their acquirer's Visa level. Visa's merchant test applies only while the acquirer is below
  both acquirer levels.
- **Which month.** For Mastercard, this month's chargebacks over last month's transactions: a July ratio uses June's
  transactions. The guide does not say which month's settled transactions Visa uses, or which month's sales MATCH
  compared against; do not supply one, send the merchant to the provider.
- **Name the source and its date.** The ECM and HECM figures rest on TabaPay's summary, not on Mastercard's own rule
  text; the Mastercard counting method rests on Verifi, Visa's dispute service. The CEMEA figures appear only in the
  guide's table. Say so.
- **Add nothing the output does not say.** No threshold, fee, date, region or rule from memory, even a figure that is
  widely repeated online (a 1% line, say). If the merchant asks about a line the data does not hold, say the guide
  does not state it and that the provider can say which test applies. Do not place a country in a Visa region; the
  guide names regions only.
- **Provider rules apply only to that provider.** Braintree's fines and fees, Stripe's network totals and Shopify's
  risk review apply to merchants of that provider. Pass them on only when the merchant uses it, or say whose rule it
  is.
- **The examples are the guide's, not typical numbers.** 1,500 chargebacks over 98,000 transactions and 90 over 6,000
  are the guide's and the calculator's examples. Never present them as what a shop usually sees.
- **This is not legal advice.** A merchant facing a MATCH listing or a closure should ask their provider for the
  calculation, and a lawyer for anything beyond it.

## If it fails

The script exits with code 2 and prints `{"error": "..."}` in words meant for the merchant. Pass that message on. The
usual causes: one of the two numbers is missing, or a number is not written in digits ("about forty" is refused,
and so is "1,5", where a comma sits in place of a decimal point). "98.000" is refused too, because it reads as 98 in
some countries and 98 thousand in others. Ask the merchant for the count as a whole number.

## Where the data comes from

`data/programs.json` restates Waverunner's guide "What chargeback ratio gets my account shut down?", updated
6 November 2026, at https://waverunner.ai/blog/chargeback-ratio/. Each programme, threshold, date, region and rule
carries the source the guide names and the date the guide says that source was checked: Visa's VAMP fact sheet 2025
and TabaPay's Network Monitoring Programs (both 4 November 2026), Mastercard's Security Rules and Procedures and
Verifi's FAQ (both 30 October 2026), and Shopify, Stripe, Checkout.com and Braintree pages (4 November 2026). The
same calculator runs in the browser in that guide, at
https://waverunner.ai/blog/chargeback-ratio/#chargeback-ratio-calculator-what-is-my-ratio.
