import io
import json
import math
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "chargeback-ratio-check"
SCRIPT = SKILL / "scripts" / "chargeback_check.py"
sys.path.insert(0, str(SKILL / "scripts"))

import chargeback_check as cc  # noqa: E402

DATA = cc.load_data()
PROGRAMMES = {p["id"]: p for p in DATA["programmes"]}
GUIDE_URL = "https://waverunner.ai/blog/chargeback-ratio/"


def run(*argv):
    out = io.StringIO()
    with redirect_stdout(out):
        status = cc.main(list(argv))
    return status, json.loads(out.getvalue())


def programme(out, pid):
    return next(p for p in out["programmes"] if p["id"] == pid)


class PortOfTheSiteTests(unittest.TestCase):
    """The five tests of the site's calculator, one for one."""

    def test_divides_this_months_chargebacks_by_last_months_transactions(self):
        r = cc.chargeback_ratio(90, 6_000)
        self.assertAlmostEqual(r["ratio"], 0.015, places=10)
        self.assertAlmostEqual(r["percent"], 1.5, places=10)
        self.assertAlmostEqual(r["bps"], 150, places=10)

    def test_gives_no_ratio_without_transactions_instead_of_infinity_or_nan(self):
        self.assertEqual(
            cc.chargeback_ratio(12, 0),
            {"chargebacks": 12, "transactions": 0, "ratio": None, "percent": None, "bps": None},
        )
        self.assertIsNone(cc.chargeback_ratio(math.nan, math.nan)["ratio"])

    def test_is_zero_with_no_chargebacks(self):
        self.assertEqual(cc.chargeback_ratio(0, 1_000)["bps"], 0)

    def test_rounds_to_whole_counts_and_floors_negatives_and_nan_at_zero(self):
        self.assertEqual(cc.normalise_chargeback_inputs(4.6, -3), {"chargebacks": 5, "transactions": 0})
        self.assertEqual(cc.normalise_chargeback_inputs(math.nan, 10), {"chargebacks": 0, "transactions": 10})

    def test_prints_percent_with_two_decimals_and_basis_points_with_at_most_one(self):
        self.assertEqual(cc.format_percent(1.5), "1.50%")
        self.assertEqual(cc.format_percent(0.1166666), "0.12%")
        self.assertEqual(cc.format_bps(150), "150 bps")
        self.assertEqual(cc.format_bps(11.6666), "11.7 bps")
        self.assertEqual(cc.format_count(6000), "6,000")


class RoundsLikeJavaScript(unittest.TestCase):
    """Values printed by Node's Math.round and Intl.NumberFormat('en-GB') on 2026-11-24."""

    def test_math_round(self):
        for x, want in {0.5: 1, 1.5: 2, 2.5: 3, 4.5: 5, 4.6: 5, 0.49999999999999994: 0}.items():
            self.assertEqual(cc.js_round(x), want, x)

    def test_percent(self):
        cases = {0.125: "0.13%", 1.005: "1.01%", 2.675: "2.68%", 0.005: "0.01%", 0.0049: "0.00%", 1e9: "1,000,000,000.00%"}
        for x, want in cases.items():
            self.assertEqual(cc.format_percent(x), want, x)

    def test_basis_points(self):
        cases = {0.25: "0.3 bps", 0.05: "0.1 bps", 0.15: "0.2 bps", 1.45: "1.5 bps", 2.25: "2.3 bps", 15000: "15,000 bps", 149.96: "150 bps"}
        for x, want in cases.items():
            self.assertEqual(cc.format_bps(x), want, x)

    def test_counts(self):
        self.assertEqual([cc.format_count(x) for x in (0, 2.5, 1234567)], ["0", "3", "1,234,567"])

    def test_limits(self):
        self.assertEqual(cc.normalise_chargeback_inputs(2e7, 2e9), {"chargebacks": 10_000_000, "transactions": 1_000_000_000})
        self.assertEqual(cc.normalise_chargeback_inputs(math.inf, -math.inf), {"chargebacks": 0, "transactions": 0})


class ComparesInWholeNumbers(unittest.TestCase):
    def test_45_over_2500_is_1_8_percent_exactly(self):
        self.assertLess(cc.chargeback_ratio(45, 2500)["percent"], 1.8)  # 1.7999999999999998 in floating point
        self.assertEqual(cc.format_percent(cc.chargeback_ratio(45, 2500)["percent"]), "1.80%")
        self.assertTrue(cc.ratio_meets(45, 2500, 180, "at least"))
        self.assertFalse(cc.ratio_meets(45, 2500, 180, "over"))

    def test_on_the_line(self):
        self.assertTrue(cc.ratio_meets(90, 6000, 150, "at least"))
        self.assertFalse(cc.ratio_meets(90, 6000, 150, "over"))

    def test_rounding_never_hides_the_side_of_the_line(self):
        status, out = run("--chargebacks", "14996", "--transactions", "1000000")
        ratio = programme(out, "mastercard-ecm")["onYourNumbers"]["conditions"][0]
        self.assertEqual((status, ratio["yours"], ratio["meets"]), (0, "150 bps", False))
        self.assertIn("149.96 bps, just under 150 bps", ratio["note"])

    def test_a_tie_on_an_over_rule_says_so(self):
        prog = dict(PROGRAMMES["mastercard-ecm"], ratio={"bps": 150, "rule": "over", "text": "over 1.5%"})
        line = cc.on_your_numbers(prog, cc.chargeback_ratio(90, 6000))["conditions"][0]
        self.assertFalse(line["meets"])
        self.assertIn("exactly 150 bps", line["note"])


class Data(unittest.TestCase):
    # Where the guide gives a ratio and a minimum, the data must carry both.
    BOTH = {
        "mastercard-ecm",
        "mastercard-hecm",
        "visa-vamp-merchant",
        "visa-vamp-merchant-cemea",
        "visa-vamp-acquirer-above-standard",
        "visa-vamp-acquirer-excessive",
        "mastercard-match-04",
    }

    def test_every_programme_has_a_source_and_a_read_date(self):
        for p in DATA["programmes"]:
            source = DATA["sources"][p["source"]]
            self.assertTrue(source["publisher"] and source["title"], p["id"])
            self.assertTrue(source["url"].startswith("https://"), p["id"])
            self.assertLessEqual(date.fromisoformat(source["checked"]).isoformat(), DATA["copied"], p["id"])
            self.assertIn(p["basis"], DATA["basisMeaning"], p["id"])
            self.assertTrue(p["ask"], p["id"])
            if p.get("howItCountsSource"):
                self.assertIn(p["howItCountsSource"], DATA["sources"], p["id"])

    def test_a_ratio_and_a_minimum_where_the_guide_gives_both(self):
        for pid in self.BOTH:
            self.assertTrue(PROGRAMMES[pid]["ratio"], pid)
            self.assertTrue(PROGRAMMES[pid]["minimums"], pid)
            for m in PROGRAMMES[pid]["minimums"]:
                self.assertTrue(m["value"] > 0 and m["unit"] and m["text"], pid)
        self.assertTrue(PROGRAMMES["braintree-vamp-fines"]["ratio"])
        self.assertEqual(PROGRAMMES["braintree-vamp-fines"]["minimums"], [])
        self.assertIn("no minimum", PROGRAMMES["braintree-vamp-fines"]["minimumsNote"])
        self.assertIsNone(PROGRAMMES["shopify-payments-risk-review"]["ratio"])

    def test_the_figures_the_guide_states(self):
        def line(pid):
            p = PROGRAMMES[pid]
            return (p["ratio"]["bps"], p["ratio"]["rule"], [m["value"] for m in p["minimums"]])

        self.assertEqual(line("mastercard-ecm"), (150, "at least", [100]))
        self.assertEqual(line("mastercard-hecm"), (300, "at least", [300]))
        self.assertEqual(line("visa-vamp-merchant"), (150, "at least", [1500]))
        self.assertEqual(line("visa-vamp-merchant-cemea"), (220, "at least", [150, 75000]))
        self.assertEqual(line("visa-vamp-acquirer-above-standard"), (50, "at least", [1500, 150, 75000]))
        self.assertEqual(line("visa-vamp-acquirer-excessive"), (70, "at least", [1500, 150, 75000]))
        self.assertEqual(line("mastercard-match-04"), (150, "over", [5000]))
        self.assertEqual(PROGRAMMES["visa-vamp-merchant"]["effectiveFrom"], "2026-04-01")
        self.assertEqual(PROGRAMMES["visa-vamp-merchant"]["region"], "Asia Pacific, Canada, the EU and the US")
        fees = {(f["acquirerLevel"], f["usdPerCount"], f["from"]) for f in PROGRAMMES["braintree-vamp-fines"]["fees"]}
        self.assertEqual(fees, {("Above Standard", 4, "2026-01-01"), ("Excessive", 8, "2025-10-01")})

    def test_read_dates_match_the_guide(self):
        checked = {k: v["checked"] for k, v in DATA["sources"].items()}
        self.assertEqual(checked["visa-vamp"], "2026-11-04")
        self.assertEqual(checked["tabapay"], "2026-11-04")
        self.assertEqual(checked["mastercard-spme"], "2026-10-30")
        self.assertEqual(checked["verifi"], "2026-10-30")

    def test_secondary_and_table_only_figures_are_marked(self):
        for p in DATA["programmes"]:
            if p["source"] == "tabapay":
                self.assertEqual(p["basis"], "secondary", p["id"])
                self.assertIn("TabaPay", p["caveat"], p["id"])
        cemea = PROGRAMMES["visa-vamp-merchant-cemea"]
        self.assertTrue(cemea["tableOnly"])
        self.assertIn("table", cemea["caveat"])

    def test_only_ecm_and_hecm_are_worked_out_from_the_two_numbers(self):
        computed = {p["id"] for p in DATA["programmes"] if p["computeFrom"]}
        self.assertEqual(computed, {"mastercard-ecm", "mastercard-hecm"})
        for p in DATA["programmes"]:
            if not p["computeFrom"]:
                self.assertTrue(p["notComputed"], p["id"])

    def test_facts_name_a_known_source_or_none(self):
        for fact in DATA["facts"]:
            self.assertTrue(fact["source"] is None or fact["source"] in DATA["sources"], fact["id"])

    def test_the_only_waverunner_links_are_the_guide(self):
        allowed = {GUIDE_URL, GUIDE_URL + "#chargeback-ratio-calculator-what-is-my-ratio"}
        for path in SKILL.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".json", ".py"}:
                text = path.read_text(encoding="utf-8")
                for url in re.findall(r"https://waverunner\.ai[^\s)\"'`>]*", text):
                    self.assertIn(url.rstrip(".,"), allowed, f"{path.name}: {url}")
                self.assertNotIn(chr(0x2014), text, path.name)  # no em dash


class CommandLine(unittest.TestCase):
    def test_the_guides_example(self):
        status, out = run("--chargebacks", "1500", "--transactions", "98000")
        self.assertEqual(status, 0)
        self.assertEqual((out["display"]["percent"], out["display"]["bps"]), ("1.53%", "153.1 bps"))
        self.assertEqual(out["display"]["counted"], "1,500 chargebacks over 98,000 transactions")
        self.assertTrue(programme(out, "mastercard-ecm")["onYourNumbers"]["meetsAllConditions"])
        self.assertFalse(programme(out, "mastercard-hecm")["onYourNumbers"]["meetsAllConditions"])
        self.assertFalse(programme(out, "visa-vamp-merchant")["onYourNumbers"]["computed"])
        self.assertFalse(programme(out, "mastercard-match-04")["onYourNumbers"]["computed"])
        self.assertEqual(out["note"], "An estimate; your provider confirms which test applies to you.")
        self.assertEqual(programme(out, "mastercard-ecm")["source"]["publisher"], "TabaPay")
        self.assertEqual(programme(out, "mastercard-ecm")["countingSource"]["publisher"], "Verifi")

    def test_the_calculators_starting_numbers_meet_the_ratio_not_the_count(self):
        _, out = run("--chargebacks", "90", "--transactions", "6000")
        ecm = programme(out, "mastercard-ecm")["onYourNumbers"]["conditions"]
        self.assertEqual([c["meets"] for c in ecm], [True, False])

    def test_the_worked_examples_match_the_script(self):
        text = (SKILL / "examples" / "worked-examples.md").read_text(encoding="utf-8")
        commands = re.findall(r"--chargebacks (\d+) --transactions (\d+)", text)
        self.assertEqual(len(commands), 2)
        for cb, tx in commands:
            _, out = run("--chargebacks", cb, "--transactions", tx)
            self.assertIn(f'"percent": "{out["display"]["percent"]}"', text)
            self.assertIn(out["programmes"][0]["onYourNumbers"]["inWords"], text)

    def test_zero_transactions_is_not_available_never_zero(self):
        status, out = run("--chargebacks", "12", "--transactions", "0")
        self.assertEqual((status, out["ratio"], out["bps"]), (0, None, None))
        self.assertEqual(out["display"]["percent"], "Not available")
        self.assertFalse(programme(out, "mastercard-ecm")["onYourNumbers"]["computed"])

    def test_the_calculators_rules_are_applied_and_said(self):
        status, out = run("--chargebacks", "-5", "--transactions", "4.6")
        self.assertEqual((status, out["chargebacks"], out["transactions"]), (0, 0, 5))
        self.assertEqual(len(out["inputNotes"]), 2)
        _, out = run("--chargebacks", "1,500", "--transactions", "3e9")
        self.assertEqual((out["chargebacks"], out["transactions"]), (1500, 1_000_000_000))
        self.assertIn("more than the calculator takes", out["inputNotes"][0])

    def test_bad_input_ends_in_an_error_object(self):
        cases = [
            ("--chargebacks", "45"),
            ("--transactions", "100"),
            ("--chargebacks", "abc", "--transactions", "100"),
            ("--chargebacks", "nan", "--transactions", "100"),
            ("--chargebacks", "45", "--transactions", "inf"),
            ("--chargebacks", "1e400", "--transactions", "100"),
            ("--chargebacks", "", "--transactions", "100"),
            ("--chargebacks", "1,5", "--transactions", "100"),
            ("--chargebacks", "45", "--transactions", "98.000"),
            ("--chargebacks", "45", "--transactions", "1.000.000"),
            ("--chargebacks", "45", "--transactions", "100", "--foo"),
            ("--chargebacks",),
            (),
        ]
        for argv in cases:
            status, out = run(*argv)
            self.assertEqual(status, 2, argv)
            self.assertEqual(list(out), ["error"], argv)

    def test_rules_alone(self):
        status, out = run("--rules")
        self.assertEqual(status, 0)
        self.assertNotIn("ratio", out)
        self.assertNotIn("onYourNumbers", out["programmes"][0])
        self.assertEqual(len(out["programmes"]), len(DATA["programmes"]))

    def test_no_verdict_words(self):
        banned = ["safe", "you will", "will be closed", "you are in", "is fine", "are fine", "verdict"]
        for argv in (("--rules",), ("--chargebacks", "1500", "--transactions", "98000"), ("--chargebacks", "1", "--transactions", "1000000")):
            _, out = run(*argv)
            text = json.dumps(out).lower()
            for word in banned:
                self.assertNotIn(word, text, (argv, word))

    def test_runs_from_another_folder_and_never_prints_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            for argv, want in (
                (["--chargebacks", "-5", "--transactions", "100"], 0),
                (["--chargebacks", "45"], 2),
                (["--transactions", "x", "--chargebacks", "1"], 2),
                (["--nope"], 2),
            ):
                done = subprocess.run(
                    [sys.executable, str(SCRIPT), *argv], cwd=tmp, capture_output=True, text=True, encoding="utf-8"
                )
                self.assertEqual(done.returncode, want, argv)
                self.assertEqual(done.stderr, "", argv)
                out = json.loads(done.stdout)
                self.assertEqual("error" in out, want == 2, argv)


if __name__ == "__main__":
    unittest.main()
