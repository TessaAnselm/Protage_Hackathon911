"""
Cognee sponsor adapter — converts mapping documents, corrections, and
successful migrations into structured memory that later migrations can
recall from. This one is real: it calls the cognee library directly
(see test_cognee.py for the verified minimal example).
"""
import cognee

LIVE = True
_initialized = False


async def _ensure_clean_start():
    global _initialized
    if not _initialized:
        _initialized = True


async def remember_mapping(columns: list[str], mapping: list[dict], row_count: int, valid_count: int) -> None:
    lines = [f"Migration processed {row_count} rows ({valid_count} valid) for a source file with columns: {', '.join(columns)}."]
    for m in mapping:
        lines.append(f"Field '{m['source_field']}' maps to standard field '{m['target_field']}' (confidence {m.get('confidence', '?')}).")
    await cognee.add("\n".join(lines))
    await cognee.cognify()


async def recall_context(columns: list[str]) -> list[str]:
    query = f"What field mappings have worked before for a file with columns: {', '.join(columns)}?"
    try:
        results = await cognee.search(query)
    except Exception:
        return []
    return [str(r) for r in results][:5]
