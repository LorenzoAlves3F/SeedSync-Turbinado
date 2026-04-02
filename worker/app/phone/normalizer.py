import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


# DDDs in Brazil that historically required the 9th digit (mobile only)
# All DDDs now officially require it, but older SIM cards from these
# regions may still be on 8-digit local numbers without it.
DDDS_WITH_NINTH_DIGIT = set(range(11, 99))  # All Brazilian DDDs

# DDD ranges that are geographically valid
VALID_DDDS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19,  # SP
    21, 22, 24,                           # RJ
    27, 28,                               # ES
    31, 32, 33, 34, 35, 37, 38,           # MG
    41, 42, 43, 44, 45, 46,               # PR
    47, 48, 49,                           # SC
    51, 53, 54, 55,                       # RS
    61,                                   # DF
    62, 64,                               # GO
    63,                                   # TO
    65, 66,                               # MT
    67,                                   # MS
    68,                                   # AC
    69,                                   # RO
    71, 73, 74, 75, 77,                   # BA
    79,                                   # SE
    81, 87,                               # PE
    82,                                   # AL
    83,                                   # PB
    84,                                   # RN
    85, 88,                               # CE
    86, 89,                               # PI
    91, 93, 94,                           # PA
    92, 97,                               # AM
    95,                                   # RR
    96,                                   # AP
    98, 99,                               # MA
}


@dataclass
class PhoneResult:
    """Result of phone normalization — always inspect `valid` and `flags`."""
    original: str
    phone: str          # Cleaned digits ready for WhatsApp (e.g. "5554912345678")
    country: str        # "BR", "US", "UNKNOWN"
    valid: bool
    mobile_likely: bool
    flags: List[str] = field(default_factory=list)


def normalize(raw: str, default_country: str = "BR") -> PhoneResult:
    """
    Deterministic phone normalization.
    No AI, no external calls — pure rules.

    Returns a PhoneResult. Always check result.valid before sending.
    """
    original = raw or ""
    flags: List[str] = []

    # ── Step 1: Strip everything except digits and leading +
    cleaned = re.sub(r"[^\d+]", "", original.strip())
    cleaned = re.sub(r"^00", "+", cleaned)  # 00XX → +XX
    digits = cleaned.lstrip("+")

    if not digits:
        return PhoneResult(original=original, phone="", country="UNKNOWN",
                           valid=False, mobile_likely=False, flags=["empty_input"])

    # ── Step 2: Country detection
    country = "UNKNOWN"
    if digits.startswith("55") and len(digits) >= 12:
        country = "BR"
        digits = re.sub(r"^\d{2}", "", digits)  # strip country code, work locally
    elif digits.startswith("1") and len(digits) == 11:
        country = "US"
    elif default_country == "BR" and 10 <= len(digits) <= 11:
        country = "BR"
        flags.append("assumed_br")
    elif not digits.startswith("55"):
        country = "UNKNOWN"
        flags.append("unknown_country")

    # ── Step 3: BR-specific normalization
    if country == "BR":
        return _normalize_br(original, digits, flags)

    # ── Step 4: Non-BR — return as-is with country code if present
    return PhoneResult(
        original=original,
        phone=digits,
        country=country,
        valid=len(digits) >= 10,
        mobile_likely=False,
        flags=flags,
    )


def _normalize_br(original: str, local_digits: str, flags: List[str]) -> PhoneResult:
    """Apply Brazil-specific rules to a local digit string (no country code prefix)."""

    # Strip any leading zeros (legacy trunk prefix)
    if local_digits.startswith("0"):
        local_digits = local_digits.lstrip("0")
        flags.append("stripped_leading_zero")

    # Must be 10 or 11 digits: DDD(2) + number(8 or 9)
    if len(local_digits) not in (10, 11):
        return PhoneResult(
            original=original,
            phone="55" + local_digits,
            country="BR",
            valid=False,
            mobile_likely=False,
            flags=flags + ["invalid_length"],
        )

    m = re.match(r"^(\d{2})(.*)$", local_digits)
    if not m:
        return PhoneResult(original=original, phone="55"+local_digits, country="BR", valid=False, mobile_likely=False, flags=flags+["regex_fail"])
    ddd = int(m.group(1))
    number = m.group(2)

    # Validate DDD
    if ddd not in VALID_DDDS:
        flags.append("invalid_ddd")
        return PhoneResult(
            original=original,
            phone="55" + local_digits,
            country="BR",
            valid=False,
            mobile_likely=False,
            flags=flags,
        )

    mobile_likely = False

    if len(number) == 9:
        # 9-digit: must start with 9 to be a valid mobile
        if number[0] == "9":
            mobile_likely = True
        else:
            flags.append("nine_digit_non_mobile")
    elif len(number) == 8:
        # 8-digit: could be landline or older mobile without 9th digit
        if number[0] in ("6", "7", "8", "9"):
            mobile_likely = True
            flags.append("possible_missing_ninth_digit")
        else:
            flags.append("landline_suspected")

    final_number = "55" + str(ddd).zfill(2) + number

    return PhoneResult(
        original=original,
        phone=final_number,
        country="BR",
        valid=True,
        mobile_likely=mobile_likely,
        flags=flags,
    )
