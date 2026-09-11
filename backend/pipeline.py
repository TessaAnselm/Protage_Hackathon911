"""
In-memory session state and transform/validate logic for a single
migration run. A hackathon demo runs one migration at a time, so a
module-level dict is enough — no need for a real session store.
"""
import sqlite3
from backend.schema import TARGET_FIELDS, validate_row

SESSION: dict = {}

MODERN_DB = sqlite3.connect(":memory:", check_same_thread=False)
MODERN_DB.execute(
    f"CREATE TABLE customers ({', '.join(f + ' TEXT' for f in TARGET_FIELDS)})"
)
MODERN_DB.commit()


def reset_session():
    SESSION.clear()
    MODERN_DB.execute("DELETE FROM customers")
    MODERN_DB.commit()


def transform_row(row: dict, mapping: list[dict]) -> dict:
    out = {f: "" for f in TARGET_FIELDS}
    for m in mapping:
        target = m.get("target_field")
        if target in out:
            out[target] = (row.get(m["source_field"]) or "").strip()
    return out


def rejected_values(row: dict, rejected_mapping: list[dict]) -> list[dict]:
    items = []
    for m in rejected_mapping:
        source = m.get("source_field")
        if source in row:
            items.append({
                "source_field": source,
                "value": row.get(source) or "",
                "reason": "rejected by human approval gate",
            })
    return items


def process_rows(rows: list[dict], mapping: list[dict], rejected_mapping: list[dict] | None = None):
    """Yield one result per row, loading approved mappings and quarantining rejected data."""
    rejected_mapping = rejected_mapping or []
    seen_ids = set()
    for i, row in enumerate(rows):
        transformed = transform_row(row, mapping)
        rejected_data = rejected_values(row, rejected_mapping)
        errors = validate_row(transformed)
        cust_id = transformed.get("customer_id")
        if cust_id and cust_id in seen_ids:
            errors.append(f"duplicate customer_id '{cust_id}'")
        elif cust_id:
            seen_ids.add(cust_id)
        if errors:
            yield {
                "index": i,
                "status": "quarantined",
                "reasons": errors,
                "row": transformed,
                "quarantined_data": rejected_data,
            }
        else:
            placeholders = ", ".join("?" for _ in TARGET_FIELDS)
            MODERN_DB.execute(
                f"INSERT INTO customers ({', '.join(TARGET_FIELDS)}) VALUES ({placeholders})",
                [transformed[f] for f in TARGET_FIELDS],
            )
            MODERN_DB.commit()
            yield {
                "index": i,
                "status": "loaded",
                "reasons": [],
                "row": transformed,
                "quarantined_data": rejected_data,
            }


def loaded_count() -> int:
    return MODERN_DB.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
