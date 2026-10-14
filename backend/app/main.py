from __future__ import annotations

import os
import re
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
