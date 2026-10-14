from __future__ import annotations

import os
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import statuses as S
from .config import CORS_ORIGINS, GROUP_A_FILENAME, GROUP_B_FILENAME, MAX_UPLOAD_MB, SUPPORTED_EXTENSIONS, UPLOAD_DIR
from .db import Batch, BillFile, SessionLocal, init_db
from .excel import build_group_a, build_group_b
from .final_report import build_final_report
from .usage import inputs as usage_inputs_mod
from .usage import service as usage_service
from .usage.usage import UsageError
import tempfile
from .extraction import ocr_available
from .processing import process_file, summarize
from .rules import contract_from_filename

@asynccontextmanager
async def lifespan(_app):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="Telecom Bill Processing System", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def file_dto(f: BillFile) -> dict:
    dec = lambda v: None if v is None else str(v.normalize() if hasattr(v, "normalize") else v)  # noqa: E731
    return {
        "id": f.id, "file_name": f.file_name, "file_type": f.file_type, "status": f.status, "group": f.group,
        "contract_number": f.contract_number, "contract_source": f.contract_source,
        "subscription_number": f.subscription_number, "bill_period": f.bill_period, "bill_month": f.bill_month,
        "total_charges": dec(f.total_charges), "vat": dec(f.vat), "total_without_vat": dec(f.total_without_vat),
        "related_company": f.related_company, "cost_center": f.cost_center, "allocations": f.allocations,
        "rounding_adjustment": dec(f.rounding_adjustment), "errors": f.errors or [], "notes": f.notes or [],
        "extraction_method": f.extraction_method, "read_attempts": f.read_attempts,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "processed_at": f.processed_at.isoformat() if f.processed_at else None,
    }


def batch_dto(b: Batch) -> dict:
    return {"id": b.id, "created_at": b.created_at.isoformat(), "summary": summarize(b.files),
            "files": [file_dto(f) for f in b.files]}


def _batch(db: Session, batch_id: str) -> Batch:
    b = db.get(Batch, batch_id)
    if not b:
        raise HTTPException(404, "Batch not found")
    return b


@app.get("/api/health")
def health():
    return {"status": "ok", "ocr_available": ocr_available(), "supported": sorted(SUPPORTED_EXTENSIONS)}


@app.post("/api/batches")
def create_batch(db: Session = Depends(get_db)):
    b = Batch()
    db.add(b)
    db.commit()
    return batch_dto(b)


@app.get("/api/batches")
def list_batches(db: Session = Depends(get_db)):
    batches = db.scalars(select(Batch).order_by(Batch.created_at.desc())).all()
    return [{"id": b.id, "created_at": b.created_at.isoformat(), "summary": summarize(b.files)} for b in batches]


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str, db: Session = Depends(get_db)):
    return batch_dto(_batch(db, batch_id))


@app.post("/api/batches/{batch_id}/files")
async def upload_files(batch_id: str, files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    b = _batch(db, batch_id)
    folder = os.path.join(UPLOAD_DIR, b.id)
    os.makedirs(folder, exist_ok=True)
    for up in files:
        name = os.path.basename(up.filename or "unnamed")
        ext = os.path.splitext(name)[1].lower()
        rec = BillFile(batch_id=b.id, file_name=name, file_type=(ext.lstrip(".").upper() or "UNKNOWN"),
                       status=S.QUEUED, errors=[], notes=[])
        hint = contract_from_filename(name)
        if hint:
            rec.notes = [f"Filename suggests contract {hint} (confirmed only after extraction)"]
        data = await up.read()
        if ext not in SUPPORTED_EXTENSIONS:
            rec.status, rec.errors = S.UNSUPPORTED, [f"'{ext or 'no extension'}' is not supported (use PDF, DOCX, XLSX or XLS)"]
        elif len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            rec.status, rec.errors = S.READ_FAILURE, [f"File exceeds {MAX_UPLOAD_MB} MB limit"]
        else:
            db.add(rec)
            db.flush()
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
            rec.stored_path = os.path.join(folder, f"{rec.id}_{safe}")
            with open(rec.stored_path, "wb") as fh:
                fh.write(data)
        db.add(rec)
    db.commit()
    db.refresh(b)
    return batch_dto(b)


@app.post("/api/files/{file_id}/process")
def process_one(file_id: str, db: Session = Depends(get_db)):
    f = db.get(BillFile, file_id)
    if not f:
        raise HTTPException(404, "File not found")
    if f.status == S.UNSUPPORTED and not f.stored_path:
        process_file(f)  # records routing info; status stays Unsupported
    else:
        f.status = S.PROCESSING
        db.commit()
        process_file(f)
    db.commit()
    return file_dto(f)


@app.get("/api/files/{file_id}/text")
def file_text(file_id: str, db: Session = Depends(get_db)):
    """Raw text the extractor read from the bill (first 20,000 chars), for diagnosing Needs Review."""
    f = db.get(BillFile, file_id)
    if not f:
        raise HTTPException(404, "File not found")
    return {"file_name": f.file_name, "method": f.extraction_method, "text": f.text_excerpt or ""}


@app.post("/api/batches/{batch_id}/process")
def process_batch(batch_id: str, db: Session = Depends(get_db)):
    b = _batch(db, batch_id)
    for f in b.files:
        if f.status == S.QUEUED:
            process_file(f)
            db.commit()
    return batch_dto(b)


@app.delete("/api/batches/{batch_id}/queue")
def clear_queue(batch_id: str, db: Session = Depends(get_db)):
    """Remove files that have not been processed yet. Processed outcomes are kept as history."""
    b = _batch(db, batch_id)
    for f in list(b.files):
        if f.status in (S.QUEUED, S.UNSUPPORTED) and f.processed_at is None:
            if f.stored_path and os.path.exists(f.stored_path):
                os.remove(f.stored_path)
            db.delete(f)
    db.commit()
    db.refresh(b)
    return batch_dto(b)


@app.get("/api/batches/{batch_id}/reports")
def report_availability(batch_id: str, db: Session = Depends(get_db)):
    b = _batch(db, batch_id)
    a = [f for f in b.files if f.group == "A"]
    bb = [f for f in b.files if f.group == "B"]
    return {
        "group_a": {"file_name": GROUP_A_FILENAME, "records": len(a),
                    "processed": sum(f.status == S.PROCESSED for f in a), "available": bool(a)},
        "group_b": {"file_name": GROUP_B_FILENAME, "records": len(bb),
                    "processed": sum(f.status == S.PROCESSED for f in bb), "available": bool(bb)},
    }


def _ensure_processed(b: Batch):
    if any(f.status in (S.QUEUED, S.PROCESSING) for f in b.files):
        raise HTTPException(409, "Some files have not been processed yet. Process the queue before exporting.")


@app.get("/api/batches/{batch_id}/reports/group-a")
def download_group_a(batch_id: str, db: Session = Depends(get_db)):
    b = _batch(db, batch_id)
    _ensure_processed(b)
    if not any(f.group == "A" for f in b.files):
        raise HTTPException(404, "No Group A bills in this batch")
    return Response(build_group_a(b.files), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{GROUP_A_FILENAME}"'})


@app.get("/api/batches/{batch_id}/reports/group-b")
def download_group_b(batch_id: str, db: Session = Depends(get_db)):
    b = _batch(db, batch_id)
    _ensure_processed(b)
    if not any(f.group == "B" for f in b.files):
        raise HTTPException(404, "No Group B bills in this batch")
    return Response(build_group_b(b.files), media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{GROUP_B_FILENAME}"'})


@app.get("/api/reports/final")
def download_final_report(db: Session = Depends(get_db)):
    """Cumulative report across all batches (every month processed so far)."""
    files = db.scalars(select(BillFile).where(BillFile.status == S.PROCESSED)).all()
    if not files:
        raise HTTPException(404, "No successfully processed bills yet")
    content, name = build_final_report(files)
    return Response(content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------------- Usage-based allocation (Dialog B698359 / SLT 003 311 8626) ----------------

@app.get("/api/usage/reference")
def usage_reference():
    ref = usage_service.reference_files()
    return {k: (os.path.basename(v) if v else None) for k, v in ref.items()}


@app.get("/api/usage/inputs")
def usage_inputs():
    """Files currently stored for the SLT and Dialog page, with their previews."""
    return usage_inputs_mod.current()


@app.post("/api/usage/inputs/{kind}")
async def usage_store_input(kind: str, file: UploadFile = File(...)):
    name = os.path.basename(file.filename or kind)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "upload" + os.path.splitext(name)[1].lower())
        with open(path, "wb") as fh:
            fh.write(await file.read())
        try:
            return usage_inputs_mod.store(kind, name, path)
        except UsageError as exc:
            raise HTTPException(422, str(exc)) from exc


@app.delete("/api/usage/inputs/{kind}")
def usage_remove_input(kind: str):
    if kind not in usage_inputs_mod.KINDS:
        raise HTTPException(404, "Unknown input type")
    usage_inputs_mod.remove(kind)
    return usage_inputs_mod.current()


@app.post("/api/usage/allocate-stored")
def usage_allocate_stored():
    """Run the allocation with the files already stored on the server."""
    cur = usage_inputs_mod.current()
    bills = [(cur[k]["file_name"], usage_inputs_mod.stored_path(k)) for k in ("slt", "dialog") if cur[k]]
    if not cur["usage"]:
        raise HTTPException(422, "Upload the usage Excel first")
    try:
        return usage_service.run(bills, usage_inputs_mod.stored_path("usage"),
                                 usage_inputs_mod.stored_path("master"), usage_inputs_mod.stored_path("map"))
    except UsageError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/usage/preview-bill")
async def usage_preview_bill(bill: UploadFile = File(...)):
    """Read one SLT / Dialog bill and return its bill value breakdown (no allocation)."""
    name = os.path.basename(bill.filename or "bill.pdf")
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "Bill must be a PDF")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "bill.pdf")
        with open(path, "wb") as fh:
            fh.write(await bill.read())
        return usage_service.preview_bill(name, path)


@app.post("/api/usage/allocate")
async def usage_allocate(bills: list[UploadFile] = File(...), usage: UploadFile = File(...),
                         master: UploadFile | None = File(None), map_file: UploadFile | None = File(None),
                         save_reference: bool = False):
    if len(bills) > usage_service.MAX_BILLS:
        raise HTTPException(400, "Only maximum 2 bills allowed")
    with tempfile.TemporaryDirectory() as tmp:
        async def store(up: UploadFile, allowed: tuple[str, ...]) -> str:
            name = os.path.basename(up.filename or "file")
            if not name.lower().endswith(allowed):
                raise HTTPException(400, f"{name}: expected {' / '.join(allowed)}")
            path = os.path.join(tmp, uuid.uuid4().hex + "_" + re.sub(r"[^A-Za-z0-9._-]", "_", name))
            with open(path, "wb") as fh:
                fh.write(await up.read())
            return path
        bill_paths = [(os.path.basename(b.filename or "bill.pdf"), await store(b, (".pdf",))) for b in bills]
        usage_path = await store(usage, (".xlsx",))
        master_path = await store(master, (".xlsx",)) if master and master.filename else None
        map_path = await store(map_file, (".xlsx",)) if map_file and map_file.filename else None
        if save_reference:
            if master_path:
                usage_service.save_reference("master", master_path)
            if map_path:
                usage_service.save_reference("map", map_path)
        try:
            return usage_service.run(bill_paths, usage_path, master_path, map_path)
        except UsageError as exc:
            raise HTTPException(422, str(exc)) from exc


@app.get("/api/usage/latest")
def usage_latest():
    return usage_service.latest_by_bill()


@app.get("/api/usage/results/{run_id}/{file_name}")
def usage_result(run_id: str, file_name: str):
    path = usage_service.result_path(run_id, file_name)
    if not path:
        raise HTTPException(404, "Result not found")
    with open(path, "rb") as fh:
        return Response(fh.read(), media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{file_name}"'})
