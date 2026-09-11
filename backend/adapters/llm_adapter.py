"""
Field-mapping suggestions via OpenAI (LLM_API_KEY — the one key already
verified working in test_api_keys.py).
"""
import json
import os
from openai import OpenAI

LIVE = True

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["LLM_API_KEY"])
    return _client


def suggest_mappings(
    source_columns: list[str],
    sample_rows: list[dict],
    target_fields: list[dict],
    recalled_context: list[str],
) -> list[dict]:
    context_block = "\n".join(recalled_context) if recalled_context else "(no prior migrations recalled)"
    prompt = f"""You are a data migration assistant. Map each source column to the best matching
target field, or null if none fits. Target fields: {json.dumps(target_fields)}

Source columns: {json.dumps(source_columns)}
Sample rows: {json.dumps(sample_rows[:5])}

Relevant memory from previous migrations:
{context_block}

Respond with ONLY a JSON array, one object per source column:
[{{"source_field": "...", "target_field": "..." or null, "confidence": 0.0-1.0, "reasoning": "short reason"}}]"""

    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    text = resp.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("["):]
    return json.loads(text)
