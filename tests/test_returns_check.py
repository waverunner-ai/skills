import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "sepa-returns-check"
sys.path.insert(0, str(SKILL / "scripts"))

import returns_check as rc  # noqa: E402

KNOWN, DATA = rc.load_codes()

PAIN002 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.002.001.10">
  <CstmrPmtStsRpt><OrgnlPmtInfAndSts>
    <TxInfAndSts>
      <OrgnlEndToEndId>E2E-1</OrgnlEndToEndId><TxSts>RJCT</TxSts>
      <StsRsnInf><Rsn><Cd>AM04</Cd></Rsn></StsRsnInf>
      <OrgnlTxRef><Amt><InstdAmt Ccy="EUR">40.00</InstdAmt></Amt><ReqdColltnDt>2026-11-01</ReqdColltnDt>
        <Dbtr><Nm>Jane Doe</Nm></Dbtr><DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct></OrgnlTxRef>
    </TxInfAndSts>
    <TxInfAndSts>
      <OrgnlEndToEndId>NOTPROVIDED</OrgnlEndToEndId><TxSts>RJCT</TxSts>
      <StsRsnInf><Rsn><Cd>MD01</Cd></Rsn></StsRsnInf>
      <OrgnlTxRef><Amt><InstdAmt Ccy="EUR">12.50</InstdAmt></Amt><MndtRltdInf><MndtId>MANDATE-7</MndtId></MndtRltdInf></OrgnlTxRef>
    </TxInfAndSts>
    <TxInfAndSts><OrgnlEndToEndId>E2E-3</OrgnlEndToEndId><TxSts>ACCP</TxSts></TxInfAndSts>
  </OrgnlPmtInfAndSts></CstmrPmtStsRpt>
</Document>"""

CAMT054 = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.08">
  <BkToCstmrDbtCdtNtfctn><Ntfctn>
    <Ntry>
      <Amt Ccy="EUR">59.00</Amt><BookgDt><Dt>2026-11-03</Dt></BookgDt>
      <NtryDtls><TxDtls>
        <Refs><EndToEndId>DE89370400440532013000</EndToEndId><MndtId>M-9</MndtId></Refs>
        <RtrInf><Rsn><Cd>MD06</Cd></Rsn></RtrInf>
        <RltdPties><Dbtr><Nm>John Roe</Nm></Dbtr></RltdPties>
      </TxDtls></NtryDtls>
    </Ntry>
    <Ntry>
      <Amt Ccy="EUR">100.00</Amt><BookgDt><DtTm>2026-11-04T09:00:00</DtTm></BookgDt>
      <NtryDtls>
        <TxDtls><Refs><EndToEndId>A</EndToEndId></Refs><Amt Ccy="EUR">60.00</Amt><RtrInf><Rsn><Cd>AC04</Cd></Rsn></RtrInf></TxDtls>
        <TxDtls><Refs><EndToEndId>B</EndToEndId></Refs><AmtDtls><TxAmt><Amt Ccy="EUR">40.00</Amt></TxAmt></AmtDtls><RtrInf><Rsn><Cd>AM04</Cd></Rsn></RtrInf></TxDtls>
        <TxDtls><Refs><EndToEndId>C</EndToEndId></Refs><Amt Ccy="EUR">5.00</Amt></TxDtls>
      </NtryDtls>
    </Ntry>
  </Ntfctn></BkToCstmrDbtCdtNtfctn>
</Document>"""


def run(*argv):
    out = io.StringIO()
    with redirect_stdout(out):
        status = rc.main(list(argv))
    return status, json.loads(out.getvalue())


class Data(unittest.TestCase):
    def test_the_25_codes_each_carry_a_decision(self):
        self.assertEqual(len(KNOWN), 25)
        for entry in KNOWN.values():
            self.assertIn(entry["collectAgain"]["action"], {"retry", "fix", "contact", "stop"})
            self.assertTrue(entry["description"] and entry["collectAgainDetail"])

    def test_only_ms03_asks_first(self):
        self.assertEqual([c for c, e in KNOWN.items() if e["collectAgain"]["askFirst"]], ["MS03"])


class Files(unittest.TestCase):
    def test_detects_the_type_from_content(self):
        self.assertEqual(rc.detect_type(PAIN002), "pain.002")
        self.assertEqual(rc.detect_type(CAMT054), "camt.054")
        self.assertEqual(rc.detect_type("<Document><BkToCstmrStmt>"), "camt.053")
        self.assertEqual(rc.detect_type("a;b;c"), "csv")

    def test_pain002_reads_code_amount_date_and_never_a_name_or_iban(self):
        kind, rows = rc.parse_return_file(PAIN002, KNOWN)
        self.assertEqual(kind, "pain.002")
        self.assertEqual(
            rows,
            [
                {"code": "AM04", "amount": 40.0, "date": "2026-11-01", "reference": "E2E-1"},
                {"code": "MD01", "amount": 12.5, "reference": "MANDATE-7"},
            ],
        )
        self.assertNotIn("Jane", json.dumps(rows))
        self.assertNotIn("DE89", json.dumps(rows))

    def test_camt054_reads_per_transaction_and_drops_an_iban_used_as_reference(self):
        kind, rows = rc.parse_return_file(CAMT054, KNOWN)
        self.assertEqual(kind, "camt.054")
        self.assertEqual(
            rows,
            [
                {"code": "MD06", "amount": 59.0, "date": "2026-11-03", "reference": "M-9"},
                {"code": "AC04", "amount": 60.0, "date": "2026-11-04", "reference": "A"},
                {"code": "AM04", "amount": 40.0, "date": "2026-11-04", "reference": "B"},
            ],
        )

    def test_csv_with_european_numbers_dates_and_a_mandate_column(self):
        text = "Mandate ID;Datum;Betrag;Grund\nM-1;03.10.2026;1.234,56 EUR;AM04\nM-2;04/10/2026;-12,50;md01\nM-3;;5;OK\n"
        kind, rows = rc.parse_return_file(text, KNOWN)
        self.assertEqual(kind, "csv")
        self.assertEqual(
            rows,
            [
                {"code": "AM04", "amount": 1234.56, "date": "2026-10-03", "reference": "M-1"},
                {"code": "MD01", "amount": 12.5, "date": "2026-10-04", "reference": "M-2"},
            ],
        )

    def test_csv_without_a_header_and_with_quoted_commas(self):
        kind, rows = rc.parse_return_file('"Doe, Jane",AM04,40\n"Roe, John",MD06,59\n', KNOWN)
        self.assertEqual([r["code"] for r in rows], ["AM04", "MD06"])

    def test_a_name_or_an_account_number_never_becomes_the_reference(self):
        _, rows = rc.parse_return_file("Mandate holder;Reference;Amount;Reason\nMax Mustermann;R-1;10,00;AM04\n", KNOWN)
        self.assertEqual(rows, [{"code": "AM04", "amount": 10.0, "reference": "R-1"}])
        _, rows = rc.parse_return_file("Customer name;Amount;Reason\nMax Mustermann;10,00;AM04\n", KNOWN)
        self.assertNotIn("reference", rows[0])
        self.assertIsNone(rc.clean_ref("DE89370400440532013000-2026-10"))
        self.assertIsNone(rc.clean_ref("Mustermann / DE89 3704 0044 0532 0130 00"))
        self.assertEqual(rc.clean_ref("INV2026110300012345"), "INV2026110300012345")
        self.assertEqual(rc.clean_ref("ORDER-1001"), "ORDER-1001")

    def test_a_name_column_is_never_read_as_the_amount(self):
        _, rows = rc.parse_return_file("Consumer name;Betrag;Code\nMax 2 Mustermann;39,00;AM04\n", KNOWN)
        self.assertEqual(rows[0]["amount"], 39.0)

    def test_quotes_with_spaces_and_one_broken_line(self):
        _, rows = rc.parse_return_file('Ref, "Amount", "Code"\nA1, "39.00", "AM04"\n', KNOWN)
        self.assertEqual(rows, [{"code": "AM04", "amount": 39.0, "reference": "A1"}])
        _, rows = rc.parse_return_file('Ref;Name;Amount;Code\nA1;"Mueller GmbH;10;AM04\nA2;x;20;MD01\nA3;y;30;AC04\n', KNOWN)
        self.assertEqual([r["code"] for r in rows], ["MD01", "AC04"])

    def test_rounding_is_half_up_and_fees_round_per_debit(self):
        self.assertEqual(rc.money(10.125), 10.13)
        out = rc.summarise([{"code": "AM04", "amount": 1}] * 3, KNOWN, "2026-11-03", 3.333, 15, False)
        self.assertEqual(out["fees"], 9.99)

    def test_amounts(self):
        for raw, want in {"1.234,56": 1234.56, "1,234.56": 1234.56, "-12,50 EUR": 12.5, "12.5": 12.5, "": 0.0}.items():
            self.assertEqual(rc.parse_amount(raw), want)

    def test_refuses_bad_files_in_words_for_the_merchant(self):
        for content in ("<Document><CstmrPmtStsRpt>", "name;city\nJane;Berlin\n", PAIN002.replace("AM04", "").replace("MD01", "")):
            with self.assertRaises(rc.ReturnFileError):
                rc.parse_return_file(content, KNOWN)

    def test_refuses_xml_that_declares_entities(self):
        bomb = '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]>' + PAIN002.split("?>", 1)[1]
        with self.assertRaises(rc.ReturnFileError):
            rc.parse_return_file(bomb, KNOWN)


class Decisions(unittest.TestCase):
    def test_weekend_moves_to_monday(self):
        self.assertEqual(rc.add_days_to_workday("2026-11-02", 5), "2026-11-09")  # Saturday the 7th
        self.assertEqual(rc.add_days_to_workday("2026-11-03", 5), "2026-11-09")  # Sunday the 8th
        self.assertEqual(rc.add_days_to_workday("2026-11-03", 14), "2026-11-17")

    def test_retry_waits_for_the_notice_and_the_default_wait(self):
        am04 = KNOWN["AM04"]
        self.assertEqual(rc.retry_date(am04, {"code": "AM04", "amount": 1, "date": "2026-10-28"}, "2026-11-03"), "2026-11-17")
        # A debit dated after the notice day: the wait counts from that date.
        self.assertEqual(rc.retry_date(am04, {"code": "AM04", "amount": 1, "date": "2026-11-20"}, "2026-11-03"), "2026-11-25")

    def test_ms03_is_never_on_the_calendar(self):
        self.assertEqual(rc.bucket_of(KNOWN["MS03"]), "contact")
        self.assertIsNone(rc.retry_date(KNOWN["MS03"], {"code": "MS03", "amount": 1}, "2026-11-03"))

    def test_no_stop_fix_or_contact_code_gets_a_date(self):
        for entry in KNOWN.values():
            if rc.bucket_of(entry) != "retry":
                self.assertIsNone(rc.retry_date(entry, {"code": entry["code"], "amount": 1}, "2026-11-03"))

    def test_a_refund_claim_costs_the_refund_fee(self):
        self.assertEqual(rc.fee_for(KNOWN["MD06"], 3.5, 15), 15)
        self.assertEqual(rc.fee_for(KNOWN["MD01"], 3.5, 15), 3.5)


class CommandLine(unittest.TestCase):
    def test_the_xml_example(self):
        status, out = run(str(SKILL / "examples" / "returns-october.xml"), "--today", "2026-11-03")
        self.assertEqual(status, 0)
        self.assertEqual((out["fileType"], out["returns"], out["amount"], out["fees"]), ("pain.002", 5, 200.5, 17.5))
        self.assertNotIn("cost", out)
        self.assertIn("Stripe", out["feesUsed"]["failedDebitFrom"])
        self.assertEqual({k: v["count"] for k, v in out["buckets"].items()}, {"retry": 2, "fix": 1, "contact": 1, "stop": 1})
        self.assertEqual(out["retryCalendar"], [{"date": "2026-11-17", "count": 2, "amount": 78.0}])
        self.assertEqual(sum(v["count"] for v in out["buckets"].values()) + out["unknown"]["count"], out["returns"])

    def test_the_csv_example_counts_a_code_outside_the_25_as_unknown(self):
        status, out = run(str(SKILL / "examples" / "returns-october.csv"), "--today", "2026-11-03", "--fee-failed", "2", "--fee-refund", "10")
        self.assertEqual(status, 0)
        self.assertEqual(out["unknown"], {"count": 1, "amount": 19.9, "codes": ["AB05"]})
        self.assertEqual(out["fees"], 16.0)  # three failed debits at 2, one refund claim at 10, none for the unknown
        self.assertEqual(out["rows"][-1]["decision"], "Ask your provider")
        self.assertEqual(out["feesUsed"]["failedDebitFrom"], "given by the merchant")
        self.assertEqual(out["rows"][2]["amount"], 1239.0)

    def test_no_rows(self):
        _, out = run(str(SKILL / "examples" / "returns-october.csv"), "--no-rows")
        self.assertNotIn("rows", out)

    def test_one_code(self):
        status, out = run("--code", "am-04")
        self.assertEqual((status, out["code"]["code"], out["code"]["name"]), (0, "AM04", "Insufficient Funds"))
        status, out = run("--code", "ZZ99")
        self.assertEqual(status, 2)
        self.assertIn("error", out)

    def test_bad_input_ends_in_an_error_object_never_a_traceback(self):
        import tempfile

        cases = {
            "us-date.csv": "Ref,Date,Amount,Code\nA,12/31/2026,10,AM04\n",
            "no-such-day.csv": "Ref;Date;Amount;Code\nA;31.02.2027;10;AM04\n",
            "long-cell.csv": "Ref;Amount;Code\n" + "x" * 200000 + ";10;AM04\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, content in cases.items():
                path = Path(tmp) / name
                path.write_text(content, encoding="utf-8")
                status, out = run(str(path), "--today", "2026-11-03")
                self.assertEqual(status, 0, name)
                self.assertNotIn("date", out["rows"][0], name)
            path = Path(tmp) / "ok.csv"
            path.write_text("Ref;Amount;Code\nA;10;AM04\n", encoding="utf-8")
            status, out = run(str(path), "--today", "2026-02-30")
            self.assertEqual(status, 2)
            self.assertIn("error", out)
            status, out = run(str(path), "--no-references")
            self.assertNotIn("reference", out["rows"][0])
            with self.assertRaises(SystemExit):
                run(str(path), "--fee-failed", "nan")

    def test_a_missing_file(self):
        status, out = run(str(ROOT / "no-such-file.xml"))
        self.assertEqual(status, 2)


if __name__ == "__main__":
    unittest.main()
