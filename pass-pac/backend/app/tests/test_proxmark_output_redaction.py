import unittest

from app.services.proxmark_metadata_parser import parse_metadata_output
from app.services.proxmark_output_redaction import redact_proxmark_output


class ProxmarkOutputRedactionTests(unittest.TestCase):
    def test_emv_reader_removes_account_track_and_name_values(self) -> None:
        raw = """
        [=] Application.......... VISA CREDIT
        [=] PAN.................. 4761 7390 0101 0010
        [=] PAN Sequence......... 1
        [=] Cardhold Name........ TEST/OPERATOR
        [=] Track 2 equivalent... 4761739001010010D29122011234567890F
        [=] Currency Code........ Turkish lira ( 949 )
        [=] Effective date....... 01/24
        [=] Expiration date...... 12/29
        """

        redacted = redact_proxmark_output(raw, "emv reader")

        self.assertNotIn("4761739001010010", redacted.replace(" ", ""))
        self.assertNotIn("TEST/OPERATOR", redacted)
        self.assertNotIn("D29122011234567890F", redacted)
        self.assertIn("[REDACTED:PAN:LAST4-0010]", redacted)
        self.assertIn("[REDACTED:CARDHOLDER_NAME]", redacted)
        self.assertIn("[REDACTED:TRACK_DATA]", redacted)

    def test_emv_trace_preserves_headers_and_status_words_only(self) -> None:
        raw = """
        100 | 200 | Rdr | 00 A4 04 00 07 A0 00 00 00 03 10 10 | ok | SELECT
        220 | 330 | Tag | 70 0A 5A 08 47 61 73 90 01 01 00 10 90 00 | ok | RESPONSE
        """

        redacted = redact_proxmark_output(raw, "emv list")

        self.assertIn("00 A4 04 00 07 [REDACTED:EMV_APDU_BODY]", redacted)
        self.assertIn("[REDACTED:EMV_RESPONSE_BODY] 90 00", redacted)
        self.assertNotIn("47 61 73 90", redacted)

    def test_emv_parser_returns_research_metadata_not_pan(self) -> None:
        raw = """
        | A0000000031010 | 1 | Visa credit |
        [=] Application.......... VISA CREDIT
        [=] Language............. tr
        [=] Currency Code........ Turkish lira ( 949 )
        [=] Effective date....... 01/24
        [=] Expiration date...... 12/29
        [=] PAN.................. 4761 7390 0101 0010
        [=] PAN Sequence......... 1
        [=] Track 2 equivalent... 4761739001010010D29122011234567890F
        """
        redacted = redact_proxmark_output(raw, "emv reader")

        fields = parse_metadata_output("hf_emv_reader", redacted).fields

        self.assertEqual(fields["application_identifiers"], ["A0000000031010"])
        self.assertEqual(fields["payment_systems"], ["Visa"])
        self.assertEqual(fields["application_labels"], ["VISA CREDIT"])
        self.assertEqual(fields["currency_metadata"], ["Turkish lira ( 949 )"])
        self.assertEqual(fields["effective_dates"], ["01/24"])
        self.assertEqual(fields["expiration_dates"], ["12/29"])
        self.assertEqual(fields["pan"], "•••• 0010")
        self.assertEqual(fields["pan_sequence_numbers"], ["1"])
        self.assertEqual(fields["track_2_equivalent"], "Present (redacted)")
        self.assertTrue(fields["sensitive_data_present"])
        self.assertIn("PAN", fields["sensitive_fields_redacted"])
        self.assertNotIn("4761739001010010", str(fields))


if __name__ == "__main__":
    unittest.main()
