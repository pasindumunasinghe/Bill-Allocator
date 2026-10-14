"""Bill detection and bill-value extraction for usage-based allocation (Dialog B698359 / SLT 003 311 8626).

Every figure is read from the PDF text. A value that is missing or appears with conflicting
amounts makes the bill invalid; nothing is guessed or hardcoded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from ..parser import AMOUNT, DATE, parse_amount

DIALOG = "DIALOG"
SLT = "SLT"
DIALOG_CONTRACT = "B698359"
DIALOG_SUBSCRIPTION = "994620243"
SLT_ACCOUNT = "003 311 8626"

DIALOG_RE = re.compile(r"CONTRACT\s*(?:NUMBER|NO\.?)\s*[:\-]?\s*B698359(?![A-Z0-9])", re.I)
SLT_RE = re.compile(r"Account\s*(?:Number|No\.?)\s*[:\-]?\s*003\s*311\s*8626(?!\d)", re.I)
AMT = rf"(?P<amt>{AMOUNT})"


@dataclass
class BillValue:
    file_name: str
    bill_type: str | None = None
    reference: str | None = None  # contract / account number
    bill_period: str | None = None
    components: list[tuple[str, Decimal]] = field(default_factory=list)  # what makes up the bill value
    vat: Decimal | None = None
    value: Decimal | None = None
    errors: list[str] = field(default_factory=list)


def _one(lines: list[str], pattern: str, name: str, bv: BillValue) -> Decimal | None:
    rx = re.compile(pattern + r"\s*[:\-]?\s*(?:Rs\.?\s*)?" + AMT + r"(?![\d/%])", re.I)
    vals = list(dict.fromkeys(parse_amount(m.group("amt")) for ln in lines for m in [rx.search(ln)] if m))
    if not vals:
        bv.errors.append(f"{name} not found in bill")
        return None
    if len(vals) > 1:
        bv.errors.append(f"{name} ambiguous: {', '.join(map(str, vals))}")
        return None
    return vals[0]


def _period(lines: list[str]) -> str | None:
    rng = re.compile(rf"({DATE})\s*-\s*({DATE})")
    for i, ln in enumerate(lines):
        if re.search(r"Bill\s*Period", ln, re.I) and "charges" not in ln.lower():
            m = rng.search(ln)
            if m:
                return f"{m.group(1)} - {m.group(2)}"
            # SLT prints "01/06/2026 -" / "Bill Period" / "30/06/2026" on separate lines
            around = " ".join(lines[max(0, i - 1):i]) + " " + " ".join(lines[i + 1:i + 2])
            m = rng.search(around)
            if m:
                return f"{m.group(1)} - {m.group(2)}"
    return None


def read_bill_value(file_name: str, text: str) -> BillValue:
    bv = BillValue(file_name)
    lines = [ln.strip() for ln in text.splitlines() if "(cid:" not in ln]
    if DIALOG_RE.search(text):
        bv.bill_type, bv.reference = DIALOG, DIALOG_CONTRACT
    elif SLT_RE.search(text):
        bv.bill_type, bv.reference = SLT, SLT_ACCOUNT
    else:
        bv.errors.append(f"Not a Dialog ({DIALOG_CONTRACT}) or SLT ({SLT_ACCOUNT}) bill")
        return bv
    bv.bill_period = _period(lines)

    if bv.bill_type == DIALOG:
        row = re.compile(rf"^{DIALOG_SUBSCRIPTION}((?:\s+-?(?:\d{{1,3}}(?:,\d{{3}})+|\d+)\.\d{{2}}){{3,}})\s*$")
        totals = list(dict.fromkeys(parse_amount(m.group(1).split()[-1]) for ln in lines for m in [row.match(ln)] if m))
        sub_total = None
        if len(totals) == 1:
            sub_total = totals[0]
        else:
            bv.errors.append(f"Subscription {DIALOG_SUBSCRIPTION} total "
                             + ("not found in Subscription Charges summary" if not totals else f"ambiguous: {totals}"))
        levies = _one(lines, r"Government\s+Taxes\s*&\s*Levies", "Government Taxes & Levies", bv)
        bv.vat = _one(lines, r"^VAT(?:\s+Amount)?", "VAT", bv)
        if sub_total is not None and levies is not None:
            bv.components = [(f"Subscription {DIALOG_SUBSCRIPTION} Total Value", sub_total),
                             ("Government Taxes & Levies", levies)]
            bv.value = sub_total + levies
    else:
        total = _one(lines, r"Total\s+charges\s+for\s+the\s+period(?!\s+in)", "Total charges for the period", bv)
        bv.vat = _one(lines, r"VAT\s*-\s*18\s*%", "VAT-18%", bv)
        if total is not None and bv.vat is not None:
            bv.components = [("Total charges for the period", total), ("Less: VAT-18%", -bv.vat)]
            bv.value = total - bv.vat
    if bv.value is not None and bv.value <= 0:
        bv.errors.append("Bill value is not positive")
    return bv
