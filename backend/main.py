import asyncio
import csv
import io
import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from backend import pipeline
from backend.adapters import cognee_adapter, hotdata_adapter, hydra_adapter, llm_adapter, modiqo_adapter, rocketride_adapter, snyk_adapter
from backend.sample_data import SAMPLE_COLUMNS, SAMPLE_ROWS
from backend.schema import TARGET_SCHEMA

app = FastAPI(title="MigrationOps")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _load_dataset(columns, rows):
    pipeline.reset_session()
    pipeline.SESSION["columns"] = columns
    pipeline.SESSION["rows"] = rows
    return {"columns": columns, "row_count": len(rows), "sample_rows": rows}


@app.get("/api/adapters")
def adapter_status():
    return {
        "cognee": {"live": cognee_adapter.LIVE},
        "openai": {"live": llm_adapter.LIVE},
        "hotdata": {"live": hotdata_adapter.LIVE},
        "hydra": {"live": hydra_adapter.LIVE},
        "rocketride": {"live": rocketride_adapter.LIVE},
        "modiqo": {"live": modiqo_adapter.LIVE},
        "snyk": {"live": snyk_adapter.LIVE},
    }


@app.get("/api/target-schema")
def target_schema():
    return TARGET_SCHEMA


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    text = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    columns = reader.fieldnames or []
    return _load_dataset(columns, rows)


@app.post("/api/sample")
def load_sample():
    return _load_dataset(SAMPLE_COLUMNS, [dict(r) for r in SAMPLE_ROWS])


@app.post("/api/profile")
def profile():
    result = hotdata_adapter.profile_dataset(pipeline.SESSION["columns"], pipeline.SESSION["rows"])
    pipeline.SESSION["profile"] = result
    return result


@app.get("/api/recall")
async def recall():
    columns = pipeline.SESSION["columns"]
    hydra_match = hydra_adapter.find_similar(columns)
    cognee_notes = await cognee_adapter.recall_context(columns)
    play = modiqo_adapter.find_play(columns)
    result = {
        "hydra_previous_mapping": hydra_match["mapping"] if hydra_match else None,
        "cognee_notes": cognee_notes,
        "replayable_play": play is not None,
    }
    pipeline.SESSION["recall"] = result
    return result


@app.post("/api/suggest-mappings")
def suggest_mappings():
    columns = pipeline.SESSION["columns"]
    recall = pipeline.SESSION.get("recall", {})
    context = list(recall.get("cognee_notes") or [])
    if recall.get("hydra_previous_mapping"):
        context.append(f"Previous approved mapping for these exact columns: {json.dumps(recall['hydra_previous_mapping'])}")
    mapping = llm_adapter.suggest_mappings(columns, pipeline.SESSION["rows"], TARGET_SCHEMA, context)
    pipeline.SESSION["suggested_mapping"] = mapping
    return mapping


class ApproveBody(BaseModel):
    mapping: list[dict]


@app.post("/api/approve-mappings")
def approve_mappings(body: ApproveBody):
    approved = [m for m in body.mapping if m.get("approved") and m.get("target_field")]
    rejected = [m for m in body.mapping if m.get("rejected")]
    pipeline.SESSION["approved_mapping"] = approved
    pipeline.SESSION["rejected_mapping"] = rejected
    return {"ok": True}


@app.get("/api/migrate-stream")
async def migrate_stream():
    rows = pipeline.SESSION["rows"]
    mapping = pipeline.SESSION["approved_mapping"]
    rejected_mapping = pipeline.SESSION.get("rejected_mapping", [])

    async def event_gen():
        results = []
        for result in pipeline.process_rows(rows, mapping, rejected_mapping):
            results.append(result)
            yield f"data: {json.dumps(result)}\n\n"
            await asyncio.sleep(0.35)
        pipeline.SESSION["migration_results"] = results
        yield f"event: done\ndata: {json.dumps({'total': len(results)})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/api/reconcile")
def reconcile():
    results = pipeline.SESSION.get("migration_results", [])
    loaded = [r for r in results if r["status"] == "loaded"]
    quarantined = [r for r in results if r["status"] == "quarantined"]
    rejected_data = [
        {"index": r["index"], **item}
        for r in results
        for item in r.get("quarantined_data", [])
    ]
    report = {
        "source_row_count": len(pipeline.SESSION["rows"]),
        "processed_count": len(results),
        "loaded_count": len(loaded),
        "quarantined_count": len(quarantined),
        "rejected_data_count": len(rejected_data),
        "loaded_in_db_count": pipeline.loaded_count(),
        "reconciled": len(loaded) == pipeline.loaded_count(),
        "quarantine_reasons": [{"index": r["index"], "reasons": r["reasons"]} for r in quarantined],
        "rejected_data": rejected_data,
    }
    pipeline.SESSION["reconciliation"] = report
    return report


@app.post("/api/learn")
async def learn():
    columns = pipeline.SESSION["columns"]
    mapping = pipeline.SESSION["approved_mapping"]
    report = pipeline.SESSION.get("reconciliation", {})
    await cognee_adapter.remember_mapping(columns, mapping, report.get("processed_count", 0), report.get("loaded_count", 0))
    hydra_adapter.save_migration(columns, mapping, report)
    modiqo_adapter.capture_play(columns, mapping)
    return {"ok": True}


class AskBody(BaseModel):
    question: str


@app.post("/api/ask")
async def ask(body: AskBody):
    context = (
        "You are answering questions about a customer-data migration run in the "
        "MigrationOps app. Use only the facts below; if something isn't covered, say so.\n"
        f"Source columns: {pipeline.SESSION.get('columns')}\n"
        f"Approved field mapping: {json.dumps(pipeline.SESSION.get('approved_mapping', []))}\n"
        f"Reconciliation report: {json.dumps(pipeline.SESSION.get('reconciliation', {}))}"
    )
    answer = await rocketride_adapter.ask(body.question, context)
    return {"answer": answer}


@app.get("/api/security-scan")
def security_scan():
    return snyk_adapter.scan()


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
