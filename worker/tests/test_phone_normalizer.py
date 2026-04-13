"""Tests for Brazilian phone number normalization."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.phone.normalizer import normalize


class TestNormalizeValidMobile:
    def test_nine_digit_rj_mobile_no_country_code(self):
        # DDD 21 (Rio de Janeiro): 11 digits not starting with 1 → correctly detected as BR
        result = normalize("21987654321")
        assert result.valid is True
        assert result.country == "BR"
        assert result.mobile_likely is True
        assert result.phone == "5521987654321"

    def test_nine_digit_with_country_code(self):
        result = normalize("5511987654321")
        assert result.valid is True
        assert result.phone == "5511987654321"

    def test_nine_digit_rj_mobile_explicit(self):
        result = normalize("21912345678")
        assert result.valid is True
        assert result.mobile_likely is True

    def test_international_prefix_00_normalized(self):
        # "00" prefix is converted to "+" before stripping country code
        result = normalize("005521987654321")
        assert result.valid is True
        assert result.phone == "5521987654321"


class TestNormalizeLandlineAndEdgeCases:
    def test_eight_digit_starting_with_low_digit_flagged_as_landline(self):
        result = normalize("1133334444")
        assert "landline_suspected" in result.flags

    def test_eight_digit_starting_with_mobile_digit_flagged(self):
        result = normalize("1199998888")
        assert "possible_missing_ninth_digit" in result.flags
        assert result.valid is True

    def test_leading_zero_stripped(self):
        # Country code 55 + leading zero + DDD 21 → stripping triggers inside _normalize_br
        result = normalize("55021987654321")
        assert "stripped_leading_zero" in result.flags
        assert result.valid is True

    def test_assumed_br_without_country_code(self):
        # DDD 21: 11 digits, doesn't start with "1" → hits the BR fallback path
        result = normalize("21987654321", default_country="BR")
        assert "assumed_br" in result.flags or result.country == "BR"


class TestNormalizeInvalidInputs:
    def test_empty_string_invalid(self):
        result = normalize("")
        assert result.valid is False
        assert "empty_input" in result.flags

    def test_none_coerced_to_empty(self):
        # normalize() coerces None via `raw or ""`
        result = normalize(None)
        assert result.valid is False

    def test_invalid_ddd_rejected(self):
        # DDD 20 does not exist in Brazil
        result = normalize("20987654321")
        assert result.valid is False
        assert "invalid_ddd" in result.flags

    def test_too_short_number_invalid(self):
        result = normalize("119876")
        assert result.valid is False

    def test_too_long_number_unrecognized_country(self):
        # 15 random digits with no matching country prefix → UNKNOWN (not BR or US)
        result = normalize("990000000000001")
        # Does not match 55+12, 1+11, or the BR fallback (15 > 11) → UNKNOWN
        assert result.country == "UNKNOWN"


class TestNormalizeOutputFormat:
    def test_phone_is_digits_only(self):
        result = normalize("(11) 9 8765-4321")
        assert result.phone.isdigit()

    def test_phone_starts_with_55_for_br(self):
        # Use DDD 21 to avoid ambiguity with US (11 digits starting with 1)
        result = normalize("21987654321")
        assert result.phone.startswith("55")
