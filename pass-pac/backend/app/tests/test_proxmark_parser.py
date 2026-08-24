import unittest

from app.services.proxmark_parser import parse_identity_output


class ProxmarkParserTests(unittest.TestCase):
    def test_parses_mifare_classic_identity(self) -> None:
        output = """
        [=] Searching for ISO14443-A tag...
        [+] UID: 04 68 29 6A 8E 67 80
        [+] ATQA: 00 44
        [+] SAK: 08
        [=] Possible types:
        [=] MIFARE Classic 1K CL2
        """

        result = parse_identity_output("hf", output)

        self.assertTrue(result.detected)
        self.assertEqual(result.card_type, "MIFARE Classic 1K CL2")
        self.assertEqual(result.protocol, "ISO 14443-A")
        self.assertEqual(result.uid, "04 68 29 6A 8E 67 80")
        self.assertEqual(result.fields["uid_length_bytes"], "7")

    def test_search_progress_is_not_reported_as_a_card_type(self) -> None:
        result = parse_identity_output(
            "hf",
            "Searching for MIFARE Classic\nNo tag found",
        )

        self.assertFalse(result.detected)
        self.assertIsNone(result.card_type)

    def test_failed_fingerprint_falls_back_to_generic_iso_type(self) -> None:
        result = parse_identity_output(
            "hf",
            """
            [+] UID: CF 74 D0 B4
            [+] ATQA: 00 08
            [+] SAK: 20
            [+] Possible types:
            [!] failed to fingerprint
            [=] -------------------------- ATS ----------------------------------
            [+] ATS: 14 78 80 75 02
            [+] Valid ISO 14443-A tag found
            """,
        )

        self.assertTrue(result.detected)
        self.assertEqual(result.card_type, "ISO 14443-A tag")

    def test_parses_lf_identifier(self) -> None:
        result = parse_identity_output(
            "lf",
            "[+] EM 410x ID 05006A39B0\n[+] 40-bit credential found",
        )

        self.assertTrue(result.detected)
        self.assertEqual(result.card_type, "EM 410x")
        self.assertEqual(result.uid, "05 00 6A 39 B0")
        self.assertEqual(result.fields["bit_length"], "40")


if __name__ == "__main__":
    unittest.main()
