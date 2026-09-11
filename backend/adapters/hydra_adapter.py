"""
HydraDB sponsor adapter — stores mapping relationships and migration
history so the system can recall what worked previously. Real: uses the
hydra_db SDK against HYDRA_API_KEY. A successful mapping is ingested as a
memory item carrying a machine-readable payload; recall runs a semantic
query and filters results back down to an exact column-signature match.
"""
import json
import os

from hydra_db import HydraDB

LIVE = True
DATABASE = "default-tenant"
_MARKER = "MIGRATION_MAPPING::"

_client = None


def _get_client() -> HydraDB:
    global _client
    if _client is None:
        _client = HydraDB(token=os.environ["HYDRA_API_KEY"])
    return _client


def _signature(columns: list[str]) -> str:
    return "|".join(sorted(c.strip().lower() for c in columns))


def find_similar(columns: list[str]) -> dict | None:
    sig = _signature(columns)
    try:
        resp = _get_client().query(
            database=DATABASE,
            query=f"field mapping for a file with columns: {', '.join(columns)}",
            type="memory",
            max_results=5,
        )
    except Exception:
        return None
    for chunk in resp.data.chunks or []:
        content = chunk.chunk_content or ""
        if not content.startswith(_MARKER):
            continue
        try:
            record = json.loads(content[len(_MARKER):])
        except json.JSONDecodeError:
            continue
        if record.get("signature") == sig:
            return record
    return None


def save_migration(columns: list[str], mapping: list[dict], outcome: dict) -> dict:
    record = {"signature": _signature(columns), "columns": columns, "mapping": mapping, "outcome": outcome}
    try:
        _get_client().context.ingest(
            database=DATABASE,
            type="memory",
            memories=json.dumps([{"text": _MARKER + json.dumps(record)}]),
        )
    except Exception:
        pass
    return record
