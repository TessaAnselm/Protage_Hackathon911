"""
Snyk sponsor adapter — scans the application, dependencies, and
configuration for security vulnerabilities. Real: shells out to the
Snyk CLI (present on this machine) against the backend's requirements.
Requires `snyk auth` to have been run, or a SNYK_TOKEN in the
environment; otherwise reports a clear "not authenticated" status
instead of a false pass.
"""
import os
import shutil
import subprocess
from pathlib import Path

LIVE = shutil.which("snyk") is not None
BACKEND_DIR = Path(__file__).resolve().parent.parent


def scan() -> dict:
    if not LIVE:
        return {"status": "skipped", "detail": "snyk CLI not found on PATH"}

    env = os.environ.copy()
    cmd = ["snyk", "test", "--json", str(BACKEND_DIR)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env, cwd=BACKEND_DIR)
    except subprocess.TimeoutExpired:
        return {"status": "error", "detail": "snyk scan timed out"}
    except FileNotFoundError:
        return {"status": "skipped", "detail": "snyk CLI not found on PATH"}

    output = proc.stdout.strip() or proc.stderr.strip()
    if "authenticate" in output.lower() or "auth" in output.lower() and proc.returncode not in (0, 1):
        return {"status": "unauthenticated", "detail": "run `snyk auth` to enable live scanning", "raw": output[:500]}

    import json
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return {"status": "error", "detail": "could not parse snyk output", "raw": output[:1000]}

    vulns = data.get("vulnerabilities", [])
    return {
        "status": "ok",
        "vulnerability_count": len(vulns),
        "unique_ids": sorted({v.get("id") for v in vulns if v.get("id")}),
        "summary": data.get("summary"),
    }
