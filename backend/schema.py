import re

# Standard target schema the company migrates vendor data into.
TARGET_SCHEMA = [
    {"field": "customer_id", "required": True, "type": "string"},
    {"field": "full_name", "required": True, "type": "string"},
    {"field": "email", "required": True, "type": "email"},
    {"field": "phone", "required": False, "type": "string"},
    {"field": "country", "required": False, "type": "string"},
]

TARGET_FIELDS = [f["field"] for f in TARGET_SCHEMA]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Column-name patterns that flag a source column as sensitive (PII).
SENSITIVE_PATTERNS = {
    "email": re.compile(r"e[-_]?mail", re.I),
    "phone": re.compile(r"phone|tel|mobile", re.I),
    "ssn": re.compile(r"ssn|social[-_]?sec", re.I),
    "dob": re.compile(r"dob|birth", re.I),
    "address": re.compile(r"addr", re.I),
    "name": re.compile(r"\bname\b|_nm\b", re.I),
}


def validate_row(row: dict) -> list[str]:
    """Return a list of validation error reasons for a transformed row; empty if valid."""
    errors = []
    for field in TARGET_SCHEMA:
        value = (row.get(field["field"]) or "").strip()
        if field["required"] and not value:
            errors.append(f"missing required field '{field['field']}'")
            continue
        if value and field["type"] == "email" and not EMAIL_RE.match(value):
            errors.append(f"invalid email '{value}'")
    return errors


def flag_sensitive_columns(columns: list[str]) -> dict[str, str]:
    flags = {}
    for col in columns:
        for label, pattern in SENSITIVE_PATTERNS.items():
            if pattern.search(col):
                flags[col] = label
                break
    return flags
