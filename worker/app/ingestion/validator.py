import re
from typing import Any


def validate_required_columns(row: dict[str, Any], required: list[str]) -> tuple[bool, list[str]]:
    """
    Check that all required columns exist and are non-empty.

    Returns:
        (is_valid, missing_fields)
    """
    missing = []
    for field in required:
        val = row.get(field)
        if val is None or str(val).strip() == "":
            missing.append(field)
    return len(missing) == 0, missing


def sanitize_identifier(name: str) -> str:
    """
    Sanitize a string for safe use as a SQL column/table identifier.
    Only allows alphanumeric and underscores.
    """
    # 1. Lowercase and replace spaces/hyphens with _
    clean = name.strip().lower()
    clean = re.sub(r"[\s-]+", "_", clean)
    # 2. Remove any character that is NOT alphanumeric or _
    clean = re.sub(r"[^a-z0-9_]", "", clean)
    # 3. Ensure it starts with a letter or _ (not a number)
    if re.match(r"^[0-9]", clean):
        clean = "f_" + clean
    # 4. Limit length
    clean = clean[:63]
    return clean
