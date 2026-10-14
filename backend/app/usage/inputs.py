"""Stored inputs for the SLT and Dialog page. Each file is saved on the server the moment it is
uploaded, validated, and previewed, so it survives page refreshes and restarts.

kinds: slt, dialog (bill PDFs), usage (usage Excel), master (Emp.xlsx), map (map.xlsx).
Master and map are stored in the reference ("Knowledge") folder and become the defaults.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from decimal import Decimal

from ..config import UPLOAD_DIR
from .bill import DIALOG, SLT
from .service import REFERENCE_DIR, preview_bill
from .usage import UsageError, norm, read_map, read_master, read_usage_workbook

INPUT_DIR = os.path.join(UPLOAD_DIR, "usage_inputs")
KINDS = {"slt": ".pdf", "dialog": ".pdf", "usage": ".xlsx", "master": ".xlsx", "map": ".xlsx"}


def _paths(kind: str) -> tuple[str, str]:
    folder = REFERENCE_DIR if kind in ("master", "map") else INPUT_DIR
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, kind)
    return base + KINDS[kind], base + ".meta.json"


def _gb(v: Decimal) -> str:
    return str(round(v, 4))


def make_preview(kind: str, name: str, path: str) -> dict:
    """Validate the file and describe what was read. Raises UsageError if it is not usable."""
    if kind in ("slt", "dialog"):
        p = preview_bill(name, path)
        expected = SLT if kind == "slt" else DIALOG
        if p.get("bill_type") != expected:
            found = p.get("bill_type") or "not a Dialog/SLT bill"
            raise UsageError(f"This is not the {'SLT' if kind == 'slt' else 'Dialog'} bill ({found})")
        return p
    if kind == "usage":
        sheets = read_usage_workbook(path)
        users, names = {}, {}
        for s in sheets:
            for u, gb in s.usage.items():  # combine by matching key, as the allocation does
                k = norm(u)
                names.setdefault(k, u)
                users[k] = users.get(k, Decimal(0)) + gb
        top = sorted(users.items(), key=lambda kv: kv[1], reverse=True)[:5]
        return {"sheets": [{"name": s.name, "type": "Source User (summed)" if s.kind == "source_user" else "username (first occurrence)",
                            "user_col": s.user_col, "usage_col": s.usage_col, "unit": s.unit or "GB (assumed)",
                            "users": len(s.usage), "total_gb": _gb(sum(s.usage.values(), Decimal(0))),
                            "excluded_rows": s.excluded_rows, "duplicates_removed": s.duplicates_removed}
                           for s in sheets],
                "users": len(users), "total_gb": _gb(sum(users.values(), Decimal(0))),
                "sample": [[names[k], _gb(v)] for k, v in top]}
    people = read_master(path) if kind == "master" else read_map(path)
    if not people:
        raise UsageError("No rows found (check the column headers)")
    emp = {p.emp_no for p in people}
    return {"rows": len(people), "employees": len(emp),
            "companies": sorted({p.company for p in people if p.company}),
            "sample": [[p.key, p.emp_no, p.emp_name, p.company, p.dimension] for p in people[:5]]}


def store(kind: str, name: str, tmp_path: str) -> dict:
    if kind not in KINDS:
        raise UsageError("Unknown input type")
    if not name.lower().endswith(KINDS[kind]):
        raise UsageError(f"{name}: expected a {KINDS[kind]} file")
    try:
        preview = make_preview(kind, name, tmp_path)
    except UsageError:
        raise
    except Exception as exc:  # noqa: BLE001 - unreadable workbook / pdf
        raise UsageError(f"{name} could not be read: {exc}") from exc
    path, meta_path = _paths(kind)
    shutil.copyfile(tmp_path, path)
    meta = {"kind": kind, "file_name": name, "size": os.path.getsize(path),
            "stored_at": datetime.now(timezone.utc).isoformat(), "preview": preview}
    with open(meta_path, "w") as fh:
        json.dump(meta, fh)
    return meta


def current() -> dict:
    out = {}
    for kind in KINDS:
        path, meta_path = _paths(kind)
        meta = None
        if os.path.exists(path) and os.path.exists(meta_path):
            with open(meta_path) as fh:
                meta = json.load(fh)
        elif os.path.exists(path):  # default master/map saved before previews existed
            meta = {"kind": kind, "file_name": os.path.basename(path), "stored_at": None, "preview": None}
        out[kind] = meta
    return out


def remove(kind: str):
    for p in _paths(kind):
        if os.path.exists(p):
            os.remove(p)


def stored_path(kind: str) -> str | None:
    p = _paths(kind)[0]
    return p if os.path.exists(p) else None
