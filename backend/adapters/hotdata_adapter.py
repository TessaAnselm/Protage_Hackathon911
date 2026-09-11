"""
HotData sponsor adapter — live SQL profiling of an uploaded dataset
(nulls, duplicates, invalid values, row counts). Real: uses the
hotdata-framework SDK against HOTDATA_API_KEY, running the profiling as
one SQL query over an inline VALUES table (no managed-table/parquet load
needed) scoped to a managed database created once and reused.
"""
import re

import hotdata_framework as hd

from backend.schema import flag_sensitive_columns

LIVE = True
_DB_NAME = "migrationops"
_db = None


def _get_db():
    global _db
    if _db is None:
        client = hd.from_env()
        try:
            _db = client.resolve_managed_database(_DB_NAME)
        except KeyError:
            _db = client.create_managed_database(_DB_NAME)
    return _db


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def profile_dataset(columns: list[str], rows: list[dict]) -> dict:
    client = hd.from_env()
    db = _get_db()

    col_list = ", ".join(_ident(c) for c in columns)
    value_rows = ", ".join(
        "(" + ", ".join(_lit(row.get(c, "") or "") for c in columns) + ")" for row in rows
    )

    select_parts = ["COUNT(*) AS row_count"]
    concat_expr = " || CHR(1) || ".join(_ident(c) for c in columns)
    select_parts.append(f"COUNT(*) - COUNT(DISTINCT ({concat_expr})) AS duplicate_rows")

    email_cols = [c for c in columns if re.search(r"e[-_]?mail", c, re.I)]
    for c in columns:
        alias = re.sub(r"\W", "_", c)
        select_parts.append(f"SUM(CASE WHEN TRIM({_ident(c)}) = '' THEN 1 ELSE 0 END) AS {alias}__nulls")
        select_parts.append(f"COUNT(DISTINCT {_ident(c)}) AS {alias}__distinct")
    for c in email_cols:
        alias = re.sub(r"\W", "_", c)
        select_parts.append(
            f"SUM(CASE WHEN TRIM({_ident(c)}) <> '' AND NOT regexp_like({_ident(c)}, "
            f"'^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$') THEN 1 ELSE 0 END) AS {alias}__invalid"
        )

    sql = (
        f"WITH staging({col_list}) AS (VALUES {value_rows}) "
        f"SELECT {', '.join(select_parts)} FROM staging"
    )
    result = client.execute_sql(sql, database=db)
    row = result.to_records()[0]

    column_stats = {}
    invalid_email_count = 0
    for c in columns:
        alias = re.sub(r"\W", "_", c)
        column_stats[c] = {
            "nulls": row.get(f"{alias}__nulls", 0),
            "distinct": row.get(f"{alias}__distinct", 0),
        }
        if f"{alias}__invalid" in row:
            invalid_email_count += row[f"{alias}__invalid"] or 0

    return {
        "engine": "hotdata-live",
        "row_count": row["row_count"],
        "duplicate_rows": row["duplicate_rows"],
        "invalid_email_count": invalid_email_count,
        "sensitive_columns": flag_sensitive_columns(columns),
        "column_stats": column_stats,
    }
