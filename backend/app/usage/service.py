"""Orchestrates one usage-allocation run: up to 2 bills, one usage file, master + map (uploaded or default)."""
from __future__ import annotations

import glob
import json
from datetime import datetime, timezone
import os
import shutil
import uuid

from ..config import UPLOAD_DIR
from ..extraction import ReadFailure, UnsupportedFormat, extract_text
from .bill import read_bill_value
from .report import build
from .usage import UsageError, allocate, read_master, read_map, read_usage_workbook

REFERENCE_DIR = os.environ.get("REFERENCE_DIR", "./reference")  # the "Knowledge" folder
RESULTS_DIR = os.path.join(UPLOAD_DIR, "usage_results")
MAX_BILLS = 2


def reference_files() -> dict:
    os.makedirs(REFERENCE_DIR, exist_ok=True)
    master = sorted(glob.glob(os.path.join(REFERENCE_DIR, "master*.xlsx")) + glob.glob(os.path.join(REFERENCE_DIR, "Emp*.xlsx")))
    mp = os.path.join(REFERENCE_DIR, "map.xlsx")
    return {"master": master[0] if master else None, "map": mp if os.path.exists(mp) else None}


def save_reference(kind: str, src: str):
    os.makedirs(REFERENCE_DIR, exist_ok=True)
    shutil.copyfile(src, os.path.join(REFERENCE_DIR, "master.xlsx" if kind == "master" else "map.xlsx"))


def run(bills: list[tuple[str, str]], usage_path: str, master_path: str | None, map_path: str | None) -> dict:
    """bills: [(original name, stored path)]. Returns a JSON-able result with one output per bill."""
    if not bills:
        raise UsageError("Upload at least one bill PDF")
    if len(bills) > MAX_BILLS:
        raise UsageError("Only maximum 2 bills allowed")
    ref = reference_files()
    master_path = master_path or ref["master"]
    map_path = map_path or ref["map"]
    if not master_path:
        raise UsageError("Master data (Emp.xlsx) not uploaded and no default saved")
    warnings = []
    master = read_master(master_path)
    mapping = []
    if map_path:
        try:
            mapping = read_map(map_path)
        except Exception as exc:  # noqa: BLE001 - map.xlsx is optional; continue without it
            warnings.append(f"map.xlsx could not be read ({exc}); continuing without it")
    else:
        warnings.append("map.xlsx not found; continuing with Master data only")
    sheets = read_usage_workbook(usage_path)

    run_id = uuid.uuid4().hex
    out_dir = os.path.join(RESULTS_DIR, run_id)
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for name, path in bills:
        item = {"bill_file": name, "status": "Failed", "errors": []}
        try:
            bv = read_bill_value(name, extract_text(path).text)
        except (ReadFailure, UnsupportedFormat) as exc:
            item["errors"] = [str(exc)]
            results.append(item)
            continue
        item.update(bill_type=bv.bill_type, reference=bv.reference, bill_period=bv.bill_period,
                    bill_value=None if bv.value is None else str(bv.value), vat=None if bv.vat is None else str(bv.vat))
        if bv.errors or bv.value is None:
            item["status"] = "Invalid" if bv.bill_type is None else "Failed"
            item["errors"] = bv.errors
            results.append(item)
            continue
        try:
            alloc = allocate(bv.value, sheets, master, mapping)
        except UsageError as exc:
            item["errors"] = [str(exc)]
            results.append(item)
            continue
        content, fname = build(bv, alloc)
        with open(os.path.join(out_dir, fname), "wb") as fh:
            fh.write(content)
        item.update(status="Processed Successfully", file_name=fname, download=f"/api/usage/results/{run_id}/{fname}",
                    allocated=str(alloc.allocated), mapped_users=len(alloc.users), unmapped_users=len(alloc.unmapped),
                    grand_total_usage=str(round(alloc.grand_total, 4)))
        item["preview"] = preview(bv, alloc)
        results.append(item)
    types = [r.get("bill_type") for r in results if r.get("bill_type")]
    if len(types) != len(set(types)):
        warnings.append("Two bills of the same type were uploaded; each was processed separately")
    out = {"run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(), "warnings": warnings,
           "results": results}
    with open(os.path.join(out_dir, "result.json"), "w") as fh:
        json.dump(out, fh)
    return out


def latest_by_bill() -> dict:
    """Most recent successful allocation per bill type (SLT / DIALOG), newest run first."""
    latest: dict[str, dict] = {}
    runs = []
    for p in glob.glob(os.path.join(RESULTS_DIR, "*", "result.json")):
        try:
            with open(p) as fh:
                runs.append(json.load(fh))
        except (OSError, ValueError):
            continue
    for run in sorted(runs, key=lambda r: r.get("created_at", ""), reverse=True):
        for r in run["results"]:
            if r.get("status") == "Processed Successfully" and r.get("bill_type") not in latest:
                latest[r["bill_type"]] = {**r, "created_at": run["created_at"]}
    return latest


def bill_dict(bv) -> dict:
    return {"bill_file": bv.file_name, "bill_type": bv.bill_type, "reference": bv.reference,
            "bill_period": bv.bill_period, "components": [[k, str(v)] for k, v in bv.components],
            "vat": None if bv.vat is None else str(bv.vat), "bill_value": None if bv.value is None else str(bv.value),
            "errors": bv.errors}


def preview_bill(name: str, path: str) -> dict:
    try:
        return bill_dict(read_bill_value(name, extract_text(path).text))
    except (ReadFailure, UnsupportedFormat) as exc:
        return {"bill_file": name, "bill_type": None, "errors": [str(exc)], "components": []}


def preview(bv, alloc) -> dict:
    """On-screen preview of the generated workbook."""
    s = lambda d: str(round(d, 4))  # noqa: E731
    companies: dict[str, list] = {}
    for u in alloc.users:
        if not u.all_company:
            c = companies.setdefault(u.person.company or "(blank)", [0, 0, 0])
            c[0] += 1
            c[1] += u.final
            c[2] += u.cost
    return {
        "bill": bill_dict(bv),
        "summary": {"grand_total_usage": s(alloc.grand_total), "unit_cost": str(round(alloc.unit_cost, 6)),
                    "allocated": str(alloc.allocated), "difference": str(bv.value - alloc.allocated),
                    "rounding_adjustment": str(alloc.rounding_adjustment), "all_company_pool": s(alloc.pool),
                    "recipients": alloc.recipients,
                    "unmapped_usage": s(sum((u.total for u in alloc.unmapped), 0))},
        "companies": [[k, v[0], s(v[1]), str(v[2])] for k, v in sorted(companies.items())],
        "users": [[u.raw, u.person.emp_no, u.person.emp_name, u.person.company, u.person.dimension,
                   s(u.final), str(u.cost)] for u in alloc.users],
        "unmapped": [[u.raw, s(u.total)] for u in alloc.unmapped],
    }


def result_path(run_id: str, fname: str) -> str | None:
    if not run_id.isalnum() or "/" in fname or "\\" in fname or fname.startswith("."):
        return None
    p = os.path.join(RESULTS_DIR, run_id, fname)
    return p if os.path.exists(p) else None
