"""Per-file processing pipeline: read -> parse -> classify -> calculate -> validate -> persist."""
from __future__ import annotations

from decimal import Decimal

from . import statuses as S
from .config import classify
from .db import BillFile, now
from .extraction import ReadFailure, UnsupportedFormat, extract_text
from .parser import parse_bill
from .usage.bill import read_bill_value
from .rules import contract_from_filename, evaluate


def _reset(f: BillFile):
    for attr in ("group", "contract_number", "contract_source", "subscription_number", "bill_period", "bill_month",
                 "total_charges", "vat", "total_without_vat", "allocation_per_company", "rounding_adjustment",
                 "related_company", "cost_center", "allocations", "extraction_method", "text_excerpt"):
        setattr(f, attr, None)
    f.errors, f.notes = [], []


def _route_by_filename(f: BillFile):
    c = contract_from_filename(f.file_name)
    if c:
        f.contract_number, f.contract_source, f.group = c, "filename", classify(c)


def process_file(f: BillFile) -> BillFile:
    _reset(f)
    f.processed_at = now()
    try:
        if not f.stored_path:
            raise UnsupportedFormat(f"'{f.file_type}' files are not supported (use PDF, DOCX, XLSX or XLS)")
        result = extract_text(f.stored_path)
    except UnsupportedFormat as exc:
        f.status, f.errors, f.read_attempts = S.UNSUPPORTED, [str(exc)], 0
        _route_by_filename(f)
        return f
    except ReadFailure as exc:
        f.status, f.errors, f.read_attempts = S.READ_FAILURE, [str(exc)], 2
        _route_by_filename(f)
        return f

    f.read_attempts = result.attempts
    f.extraction_method = result.method
    f.text_excerpt = result.text[:20000]
    # Dialog B698359 / SLT 003 311 8626 bills are allocated by usage on the Usage Allocation page.
    usage_bill = read_bill_value(f.file_name, result.text)
    if usage_bill.bill_type:
        f.status, f.contract_number, f.contract_source = S.USAGE_BILL, usage_bill.reference, "document"
        f.bill_period = usage_bill.bill_period
        f.notes = [f"{usage_bill.bill_type} bill: process it on the Usage Allocation page with the usage Excel"]
        if usage_bill.value is not None:
            f.notes.append(f"Bill value to allocate: {usage_bill.value:,.2f}")
        f.errors = usage_bill.errors
        return f

    bill = parse_bill(result.text)
    out = evaluate(bill)

    f.contract_number = bill.contract_number
    f.contract_source = "document" if bill.contract_number else None
    if not f.contract_number:
        _route_by_filename(f)
    f.group = out.group or (f.group if f.contract_source == "filename" else None)
    f.subscription_number = bill.subscription_number
    f.bill_period, f.bill_month = bill.bill_period, bill.bill_month
    f.total_charges, f.vat = bill.total_charges, bill.vat
    f.related_company, f.cost_center = out.related_company, out.cost_center
    f.notes = list(result.warnings) + bill.notes
    f.errors = out.errors
    f.status = out.status

    # Text was read but contains no recognisable bill data at all -> treat as unreadable.
    if not any([bill.contract_number, bill.subscription_number, bill.total_charges is not None, bill.vat is not None]):
        f.status = S.READ_FAILURE
        f.errors = ["No bill fields could be identified in the document text"] + f.errors

    if out.status == S.PROCESSED:
        f.total_without_vat = out.total_without_vat
        f.allocation_per_company = out.allocation_per_company
        f.rounding_adjustment = out.rounding_adjustment
        f.allocations = [{"dimension": a.dimension, "company": a.company, "amount": str(a.amount),
                          "subscription": a.subscription,
                          "charges": None if a.charges is None else str(a.charges),
                          "levies": None if a.levies is None else str(a.levies)}
                         for a in out.allocations] or None
        if out.allocations and out.allocations[0].subscription:
            f.notes.append("Allocated per subscription from the itemised charges table")
    return f


def summarize(files: list[BillFile]) -> dict:
    ok = [f for f in files if f.status == S.PROCESSED]
    tot = lambda attr: str(sum((Decimal(str(getattr(f, attr))) for f in ok), Decimal(0)))  # noqa: E731
    return {
        "total_files": len(files),
        "processed": len(ok),
        "failed": sum(1 for f in files if f.status in S.FAILED_STATUSES),
        "ignored": sum(1 for f in files if f.status == S.IGNORED),
        "queued": sum(1 for f in files if f.status == S.QUEUED),
        "group_a": sum(1 for f in files if f.group == "A"),
        "group_b": sum(1 for f in files if f.group == "B"),
        "group_a_processed": sum(1 for f in ok if f.group == "A"),
        "group_b_processed": sum(1 for f in ok if f.group == "B"),
        "total_charges": tot("total_charges"),
        "total_vat": tot("vat"),
        "total_without_vat": tot("total_without_vat"),
    }
