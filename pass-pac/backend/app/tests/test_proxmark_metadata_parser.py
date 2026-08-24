import unittest

from app.services.proxmark_metadata_parser import parse_metadata_output


class ProxmarkMetadataParserTests(unittest.TestCase):
    def test_parses_mifare_classic_metadata(self) -> None:
        output = """
        [+] UID: 04 11 22 33
        [+] ATQA: 00 04
        [+] SAK: 08
        [+] Prng detection: weak PRNG
        [=] Magic capabilities... Gen 1a
        """

        fields = parse_metadata_output("hf_mifare_classic", output).fields

        self.assertEqual(fields["uid"], "04:11:22:33")
        self.assertEqual(fields["uid_length_bytes"], 4)
        self.assertEqual(fields["nonce_type"], "weak_prng")
        self.assertTrue(fields["magic_card_indicator"])

    def test_parses_real_non_unique_uid_and_ats_metadata(self) -> None:
        output = """
        [+] UID: CF 74 D0 B4   ( FNUID, fixed, non-unique ID )
        [+] ATQA: 00 08
        [+] SAK: 20 [1]
        [+] ATS: 14 78 80 75 02 57 69 4C 4C 55 00 0B 00 00 00 00 20 22 01 28 [ 51 60 ]
        [=] FSCI is 8 (FSC = 256)
        [=] SFGI = 5, FWI = 7
        [=] NAD is NOT supported, CID is supported
        [+] 57694C4C55000B0000000020220128 - WiLLU
        """

        fields = parse_metadata_output("hf_iso14443a", output).fields

        self.assertTrue(fields["non_unique_uid"])
        self.assertTrue(fields["fixed_uid"])
        self.assertEqual(fields["ats_length_bytes"], 20)
        self.assertEqual(fields["fsc_bytes"], 256)
        self.assertEqual(fields["fwi"], 7)
        self.assertFalse(fields["nad_supported"])
        self.assertTrue(fields["cid_supported"])

    def test_parses_type2_memory_and_protection_metadata(self) -> None:
        output = """
        [+] TYPE: NTAG 213
        [=] available memory.... 144 bytes
        [=] 45 pages
        [=] AUTH0: 04
        [=] originality signature verified
        """

        fields = parse_metadata_output("hf_type2", output).fields

        self.assertEqual(fields["memory_size_bytes"], 144)
        self.assertEqual(fields["page_count"], 45)
        self.assertTrue(fields["password_protection_indicator"])
        self.assertTrue(fields["signature_present"])

    def test_parses_iso15693_memory_metadata(self) -> None:
        output = """
        [+] UID: E0 04 01 23 45 67 89 AB
        [=] Manufacturer: NXP Semiconductors
        [=] DSFID: 00
        [=] AFI: 00
        [=] Memory: 64 blocks x 4 bytes
        [=] IC reference: 01
        """

        fields = parse_metadata_output("hf_iso15693", output).fields

        self.assertEqual(fields["uid"], "E0:04:01:23:45:67:89:AB")
        self.assertEqual(fields["block_count"], 64)
        self.assertEqual(fields["memory_size_bytes"], 256)
        self.assertEqual(fields["manufacturer"], "NXP Semiconductors")

    def test_parses_lf_hid_and_t55xx_metadata(self) -> None:
        hid = parse_metadata_output(
            "lf_hid",
            "[+] HID Prox H10301 26-bit FC: 118 Card: 1603\n[=] raw: 2006ec0c86",
        ).fields
        t55xx = parse_metadata_output(
            "lf_t55xx",
            "[=] Chip Type......... T55x7\n[=] Modulation........ FSK2a\n[=] Config block...... 00107060",
        ).fields

        self.assertEqual(hid["facility_code"], 118)
        self.assertEqual(hid["card_number"], 1603)
        self.assertEqual(t55xx["chip_type"], "T55x7")
        self.assertEqual(t55xx["configuration_block"], "00107060")


if __name__ == "__main__":
    unittest.main()
