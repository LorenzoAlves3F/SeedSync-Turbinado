"""Tests for lead fingerprinting and deduplication logic extracted from LeadIngester."""
import hashlib
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# Replicate the fingerprinting logic from ingester.py so we can test it in isolation
def make_fingerprint(row: dict) -> str:
    """Mirror of the fingerprint logic in LeadIngester.process_batch."""
    def get_fuzzy(target: str, row: dict) -> str:
        for k in row.keys():
            if str(target).lower() == str(k).lower().strip():
                return row[k]
        return ""

    name = str(get_fuzzy("NOME", row)).strip().lower()
    phone = str(get_fuzzy("WHATSAPP", row)).strip().lower()

    if not name and not phone:
        payload_str = json.dumps(row, sort_keys=True)
    else:
        payload_str = f"{name}|{phone}"

    return hashlib.sha256(payload_str.encode()).hexdigest()


class TestFingerprintDeterminism:
    def test_same_name_and_phone_produce_same_fingerprint(self):
        row1 = {"NOME": "João Silva", "WHATSAPP": "11999999999", "CIDADE": "SP"}
        row2 = {"NOME": "João Silva", "WHATSAPP": "11999999999", "CIDADE": "RJ"}
        # Extra columns must NOT affect the fingerprint
        assert make_fingerprint(row1) == make_fingerprint(row2)

    def test_different_phone_produces_different_fingerprint(self):
        row1 = {"NOME": "João Silva", "WHATSAPP": "11999999999"}
        row2 = {"NOME": "João Silva", "WHATSAPP": "11888888888"}
        assert make_fingerprint(row1) != make_fingerprint(row2)

    def test_different_name_produces_different_fingerprint(self):
        row1 = {"NOME": "João", "WHATSAPP": "11999999999"}
        row2 = {"NOME": "Maria", "WHATSAPP": "11999999999"}
        assert make_fingerprint(row1) != make_fingerprint(row2)

    def test_case_insensitive_name_same_fingerprint(self):
        row1 = {"NOME": "JOÃO SILVA", "WHATSAPP": "11999999999"}
        row2 = {"NOME": "joão silva", "WHATSAPP": "11999999999"}
        assert make_fingerprint(row1) == make_fingerprint(row2)

    def test_case_insensitive_phone_same_fingerprint(self):
        # Phone values that differ only in case (unlikely but safe to test)
        row1 = {"NOME": "Ana", "WHATSAPP": "ABC"}
        row2 = {"NOME": "Ana", "WHATSAPP": "abc"}
        assert make_fingerprint(row1) == make_fingerprint(row2)


class TestFingerprintFallback:
    def test_empty_name_and_phone_uses_full_row_hash(self):
        row = {"NOME": "", "WHATSAPP": "", "EMAIL": "lead@test.com"}
        fp = make_fingerprint(row)
        # Must be a valid SHA256 hex digest
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_empty_name_and_phone_different_rows_differ(self):
        row1 = {"NOME": "", "WHATSAPP": "", "EMAIL": "a@test.com"}
        row2 = {"NOME": "", "WHATSAPP": "", "EMAIL": "b@test.com"}
        assert make_fingerprint(row1) != make_fingerprint(row2)

    def test_full_row_hash_is_deterministic(self):
        row = {"NOME": "", "WHATSAPP": "", "EXTRA": "value"}
        assert make_fingerprint(row) == make_fingerprint(row)


class TestFuzzyColumnMatching:
    def test_column_lookup_is_case_insensitive(self):
        # The fuzzy lookup matches regardless of column casing
        row_upper = {"NOME": "Test", "WHATSAPP": "123"}
        row_lower = {"nome": "Test", "whatsapp": "123"}
        assert make_fingerprint(row_upper) == make_fingerprint(row_lower)

    def test_missing_column_treated_as_empty(self):
        row_with_phone = {"NOME": "Ana", "WHATSAPP": "11999999999"}
        row_no_phone = {"NOME": "Ana"}
        # These differ: one has phone, other falls to empty
        assert make_fingerprint(row_with_phone) != make_fingerprint(row_no_phone)
