"""
Modiqo Rote sponsor adapter — captures a successful migration workflow
and deterministically replays it for similar future files.

"Modiqo Rote" is the `rote` CLI (a substrate between agents and APIs),
already installed and authenticated on this machine — LIVE is real,
checked via `rote whoami`. Rote's own play system (`rote play ...`) is
built for an agent to crystallize its *own* interactive API/browser/shell
sessions into reusable TypeScript plays; it isn't a runtime library for
another backend to call per-request with arbitrary JSON. So mapping
capture/replay for MigrationOps stays app-owned state (this file), while
connection identity is the one thing genuinely delegated to Rote.
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "plays.json"


def _check_live() -> bool:
    if not shutil.which("rote"):
        return False
    try:
        proc = subprocess.run(["rote", "whoami"], capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return "ok:" in proc.stdout


LIVE = _check_live()


def _load() -> list[dict]:
    if not STORE_PATH.exists():
        return []
    return json.loads(STORE_PATH.read_text())


def _save(plays: list[dict]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(plays, indent=2))


def _signature(columns: list[str]) -> str:
    return "|".join(sorted(c.strip().lower() for c in columns))


def capture_play(columns: list[str], mapping: list[dict]) -> dict:
    plays = _load()
    play = {
        "signature": _signature(columns),
        "columns": columns,
        "mapping": mapping,
        "captured_at": time.time(),
    }
    plays = [p for p in plays if p["signature"] != play["signature"]]
    plays.append(play)
    _save(plays)
    return play


def find_play(columns: list[str]) -> dict | None:
    sig = _signature(columns)
    for play in _load():
        if play["signature"] == sig:
            return play
    return None
