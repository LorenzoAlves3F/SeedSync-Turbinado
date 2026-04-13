"""Tests for SQL identifier sanitization."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ingestion.validator import sanitize_identifier, validate_required_columns


class TestSanitizeIdentifier:
    def test_normal_name_unchanged(self):
        assert sanitize_identifier("nome") == "nome"

    def test_uppercase_lowercased(self):
        assert sanitize_identifier("WHATSAPP") == "whatsapp"

    def test_spaces_become_underscores(self):
        assert sanitize_identifier("data de nascimento") == "data_de_nascimento"

    def test_hyphens_become_underscores(self):
        assert sanitize_identifier("phone-number") == "phone_number"

    def test_special_chars_removed(self):
        assert sanitize_identifier("atendido?") == "atendido"

    def test_leading_digit_prefixed(self):
        result = sanitize_identifier("1st_column")
        assert result.startswith("f_")

    def test_empty_string_returns_empty(self):
        assert sanitize_identifier("") == ""

    def test_max_length_63_chars(self):
        long_name = "a" * 100
        assert len(sanitize_identifier(long_name)) <= 63

    def test_template_placeholders_stripped(self):
        # {{ and }} are not alphanumeric — should be removed
        result = sanitize_identifier("{{campo}}")
        assert "{{" not in result and "}}" not in result

    def test_mixed_case_and_spaces(self):
        assert sanitize_identifier("  Nome Completo  ") == "nome_completo"


class TestValidateRequiredColumns:
    def test_all_present_returns_valid(self):
        row = {"NOME": "João", "WHATSAPP": "11999999999"}
        ok, missing = validate_required_columns(row, ["NOME", "WHATSAPP"])
        assert ok is True
        assert missing == []

    def test_missing_field_reported(self):
        row = {"NOME": "João"}
        ok, missing = validate_required_columns(row, ["NOME", "WHATSAPP"])
        assert ok is False
        assert "WHATSAPP" in missing

    def test_empty_string_counts_as_missing(self):
        row = {"NOME": "", "WHATSAPP": "11999999999"}
        ok, missing = validate_required_columns(row, ["NOME", "WHATSAPP"])
        assert ok is False
        assert "NOME" in missing

    def test_whitespace_only_counts_as_missing(self):
        row = {"NOME": "   ", "WHATSAPP": "11999999999"}
        ok, missing = validate_required_columns(row, ["NOME", "WHATSAPP"])
        assert ok is False
