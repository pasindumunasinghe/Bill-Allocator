"""Field extraction from raw bill text.

Strict rules:
- Total charges come ONLY from a value labelled "Total Charges for Bill Period".
- VAT is extracted from its own label, never derived.
- If a field is missing or ambiguous (conflicting values), it is left as None and an
  issue is recorded. Nothing is guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .config import ALL_CONTRACTS

AMOUNT = r"\(?-?\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?"
CURRENCY = r"(?:[A-Z]{3}|Rs\.?|Rs|Dhs?\.?|[$€£₹])"
AMOUNT_AFTER_LABEL = rf"\s*(?:\((?:{CURRENCY})\)\s*)?[:=\-]?\s*(?:{CURRENCY}\.?\s*)?(?P<amt>{AMOUNT})(?!\s*%)(?![\d/])"

TOTAL_LABEL = re.compile(r"Total\s*Charges?\s*for\s*(?:the\s*|this\s*)?Bill(?:ing)?(?:\s*Period)?(?![A-Za-z])", re.I)
VAT_LABEL = re.compile(
    r"(?<![A-Za-z])(?:Total\s+)?VAT(?:\s+Amount)?(?:\s*\(?\s*@?\s*\d+(?:\.\d+)?\s*%\s*\)?)?", re.I
)
VAT_REJECT = re.compile(
    r"without|excl|incl|including|excluding|before|after|payable|registration|\bTRN\b|\bno\b\.?|number|\breg\b|\bid\b|charges\s+for",
    re.I,
)
CONTRACT_LABEL = re.compile(r"Contract\s*(?:Number|No\.?|#|ID)?\s*[:\-]?\s*(?P<v>[A-Z0-9][A-Z0-9\-]{3,})", re.I)
SUBSCRIPTION_LABEL = re.compile(
    r"Subscription\s*(?:Number|No\.?|#|ID)?\s*[:\-]?\s*(?P<v>[A-Z0-9][A-Z0-9\-]{2,})", re.I
)
BILL_PERIOD_LABEL = re.compile(r"(?<!for\s)(?<!for the\s)\bBill(?:ing)?\s+Period\b(?!\s*\))", re.I)
BILL_MONTH_LABEL = re.compile(r"\bBill(?:ing)?\s+Month\s*[:\-]?\s*(?P<v>[A-Za-z]{3,9}[\s\-/]+\d{4}|\d{1,2}[/\-]\d{4})", re.I)
COST_CENTER_LABEL = re.compile(r"Cost\s*Cent(?:er|re)\s*[:\-]?\s*(?P<v>[A-Z0-9]+)", re.I)

SUB_ROW = re.compile(r"^(?P<sub>\d{8,10})(?P<amts>(?:\s+-?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}){5,})\s*$")

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
DATE = (
    r"(?:\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
    r"|\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[\s\-]?[A-Za-z]{3,9}[\s\-,]+\d{4}"
    r"|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})"
)
DATE_RANGE = re.compile(rf"(?P<start>{DATE})\s*(?:-|–|—|to|till|until)\s*(?P<end>{DATE})", re.I)


@dataclass
class ParsedBill:
    contract_number: str | None = None
    subscription_number: str | None = None
    bill_period: str | None = None
    bill_month: str | None = None
    total_charges: Decimal | None = None
    vat: Decimal | None = None
    cost_center_in_document: str | None = None
    # per-subscription rows from an itemised charges table: (subscription, [amounts...]); last = row total,
    # second-last = VAT, third-last = government taxes & levies
    subscription_rows: list[tuple[str, list[Decimal]]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def parse_amount(raw: str) -> Decimal | None:
    s = raw.replace(",", "").replace(" ", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        value = Decimal(s)  # exact: source precision preserved, no rounding
    except InvalidOperation:
        return None
    return -value if neg else value


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines()]


def _amount_for_label(lines: list[str], label: re.Pattern, reject: re.Pattern | None = None) -> list[Decimal]:
    """Amounts that directly follow `label` on the same line, or on the next non-empty line."""
    found: list[Decimal] = []
    for i, line in enumerate(lines):
        for m in label.finditer(line):
            if reject is not None and reject.search(line):
                continue
            rest = line[m.end():]
            am = re.match(AMOUNT_AFTER_LABEL, rest)
            if am is None and not rest.strip():
                nxt = next((ln for ln in lines[i + 1:] if ln), "")
                am = re.match(AMOUNT_AFTER_LABEL, " " + nxt)
                if am and len(nxt) > len(am.group(0)) + 8:
                    am = None  # next line is not a bare amount; do not guess
            if am:
                v = parse_amount(am.group("amt"))
                if v is not None:
                    found.append(v)
    return found


def _single(values: list, name: str, bill: ParsedBill):
    distinct = list(dict.fromkeys(values))
    if not distinct:
        bill.issues.append(f"{name} not found")
        return None
    if len(distinct) > 1:
        bill.issues.append(f"{name} ambiguous: multiple different values found ({', '.join(map(str, distinct))})")
        return None
    return distinct[0]


DMY = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y")
MDY = ("%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%y")


def parse_period(start: str, end: str) -> tuple[date | None, date | None]:
    """Parse both dates with the SAME convention (day-first, else month-first).
    A convention is accepted only if both dates parse and start <= end."""
    for fmts in (DMY, MDY):
        a, b = parse_date(start, fmts), parse_date(end, fmts)
        if a and b and a <= b:
            return a, b
    return None, None


def _resolve_vat_breakdown(values: list[Decimal], bill: "ParsedBill") -> list[Decimal]:
    """Bills often show VAT per line/subscription plus a VAT total. If exactly one value equals the
    sum of all the others, it is the total and is used; otherwise values are left as-is (ambiguous)."""
    distinct = list(dict.fromkeys(values))
    if len(distinct) < 3:
        return distinct
    for v in distinct:
        rest = list(values)
        rest.remove(v)
        rest = [r for r in rest if r != v]
        if rest and sum(rest) == v:
            bill.notes.append(f"VAT total {v} = sum of VAT lines ({' + '.join(map(str, rest))})")
            return [v]
    return distinct


def parse_date(raw: str, numeric_formats=DMY) -> date | None:
    raw = raw.strip().replace(",", " ")
    for fmt in numeric_formats:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    m = re.match(r"(\d{1,2})[\s\-]?([A-Za-z]{3,9})[\s\-]+(\d{4})$", raw) or None
    if m:
        d, mon, y = m.groups()
    else:
        m = re.match(r"([A-Za-z]{3,9})\s+(\d{1,2})\s+(\d{4})$", re.sub(r"\s+", " ", raw))
        if not m:
            return None
        mon, d, y = m.groups()
    month = MONTHS.get(mon[:3].lower())
    if not month:
        return None
    try:
        return date(int(y), month, int(d))
    except ValueError:
        return None


def parse_bill(text: str) -> ParsedBill:
    bill = ParsedBill()
    lines = _lines(text)

    # Contract number: labelled value first; fall back to a known contract present verbatim.
    labelled = [m.group("v").upper() for ln in lines for m in CONTRACT_LABEL.finditer(ln)]
    labelled = [v for v in labelled if any(ch.isdigit() for ch in v)]
    if labelled:
        bill.contract_number = _single(labelled, "Contract Number", bill)
    else:
        known = [c for c in ALL_CONTRACTS if re.search(rf"(?<![A-Z0-9]){re.escape(c)}(?![A-Z0-9])", text, re.I)]
        bill.contract_number = _single(known, "Contract Number", bill)
        if bill.contract_number:
            bill.notes.append("Contract number matched from document text (no explicit label)")

    subs = [m.group("v").upper() for ln in lines for m in SUBSCRIPTION_LABEL.finditer(ln)]
    subs = [v for v in subs if any(ch.isdigit() for ch in v)]
    bill.subscription_number = _single(subs, "Subscription Number", bill)

    periods = []
    for i, ln in enumerate(lines):
        for m in BILL_PERIOD_LABEL.finditer(ln):
            seg = ln[m.end():]
            r = DATE_RANGE.search(seg) or DATE_RANGE.search(next((x for x in lines[i + 1:] if x), ""))
            if r:
                periods.append((r.group("start").strip(), r.group("end").strip()))
    period = _single(periods, "Bill Period", bill)
    end_date = None
    if period:
        bill.bill_period = f"{period[0]} - {period[1]}"
        start_date, end_date = parse_period(period[0], period[1])
        if end_date is None:
            bill.issues.append(f"Bill Period dates could not be parsed: {bill.bill_period}")

    months = [m.group("v").strip() for ln in lines for m in BILL_MONTH_LABEL.finditer(ln)]
    if months:
        bill.bill_month = _single(months, "Bill Month", bill)
    elif end_date:
        bill.bill_month = end_date.strftime("%B %Y")
        bill.notes.append("Bill Month derived from Bill Period end date")
    elif not period:
        pass  # Bill Period issue already recorded
    else:
        bill.issues.append("Bill Month not found")

    totals = _amount_for_label(lines, TOTAL_LABEL)
    if not totals:  # label wrapped onto two lines in the PDF, e.g. "Total Charges for" / "Bill Period 1,704.29"
        joined = [f"{a} {b}" for a, b in zip(lines, lines[1:]) if a and not TOTAL_LABEL.search(a)]
        totals = _amount_for_label(joined, TOTAL_LABEL)
    bill.total_charges = _single(totals, "Total Charges for Bill Period", bill)
    bill.vat = _single(_resolve_vat_breakdown(_amount_for_label(lines, VAT_LABEL, VAT_REJECT), bill), "VAT", bill)

    for ln in lines:
        m = SUB_ROW.match(ln)
        if m:
            amounts = [parse_amount(a) for a in m.group("amts").split()]
            bill.subscription_rows.append((m.group("sub"), amounts))

    ccs = [m.group("v").upper() for ln in lines for m in COST_CENTER_LABEL.finditer(ln)]
    if ccs:
        bill.cost_center_in_document = list(dict.fromkeys(ccs))[0] if len(set(ccs)) == 1 else ",".join(dict.fromkeys(ccs))
    return bill
