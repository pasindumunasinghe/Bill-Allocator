"""Contract classification, decimal-safe calculations and pre-export validation."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from . import statuses as S
from .config import ALL_CONTRACTS, GROUP_A, GROUP_A_ALLOCATIONS, GROUP_B, GROUP_B_MAPPING, classify
from .parser import ParsedBill

CENT = Decimal("0.01")


def money(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Allocation:
    dimension: str
    company: str
    amount: Decimal


@dataclass
class Outcome:
    status: str
    group: str | None
    contract: str | None
    errors: list[str] = field(default_factory=list)
    total_without_vat: Decimal | None = None
    allocation_per_company: Decimal | None = None  # exact (unrounded) share
    rounding_adjustment: Decimal = Decimal("0")
    allocations: list[Allocation] = field(default_factory=list)
    related_company: str | None = None
    cost_center: str | None = None


def contract_from_filename(name: str) -> str | None:
    """Used only to route a failed/unreadable file to the right group's failure report."""
    hits = [c for c in ALL_CONTRACTS if re.search(rf"(?<![A-Z0-9]){re.escape(c)}(?![A-Z0-9])", name, re.I)]
    return hits[0] if len(hits) == 1 else None


def allocate_group_a(total_without_vat: Decimal) -> tuple[Decimal, list[Allocation], Decimal]:
    """Split equally across 4 companies at 2dp. Any rounding remainder (max ±0.03)
    is applied to the LAST company so the allocations always sum exactly to the total."""
    exact_share = total_without_vat / Decimal(len(GROUP_A_ALLOCATIONS))
    rounded = money(exact_share)
    amounts = [rounded] * len(GROUP_A_ALLOCATIONS)
    adjustment = money(total_without_vat) - sum(amounts)
    amounts[-1] += adjustment
    allocs = [Allocation(dim, comp, amt) for (dim, comp), amt in zip(GROUP_A_ALLOCATIONS, amounts)]
    return exact_share, allocs, adjustment


def evaluate(bill: ParsedBill) -> Outcome:
    contract = bill.contract_number
    group = classify(contract)
    if contract and group is None:
        return Outcome(S.IGNORED, None, contract, [f"Contract {contract} is not in Group A or Group B"])
    out = Outcome(S.PROCESSED, group, contract)

    if group == GROUP_B:
        out.related_company, out.cost_center = GROUP_B_MAPPING[contract]
        doc_cc = bill.cost_center_in_document
        if doc_cc and doc_cc != out.cost_center:
            out.errors.append(f"Cost center in document ({doc_cc}) differs from contract mapping ({out.cost_center})")

    out.errors = list(bill.issues) + out.errors
    if out.errors:
        out.status = S.NEEDS_REVIEW
        return out

    out.total_without_vat = bill.total_charges - bill.vat
    if group == GROUP_A:
        out.allocation_per_company, out.allocations, out.rounding_adjustment = allocate_group_a(out.total_without_vat)

    problems = validate(bill, out)
    if problems:
        out.status = S.VALIDATION_FAILED
        out.errors = problems
    return out


def validate(bill: ParsedBill, out: Outcome) -> list[str]:
    p: list[str] = []
    if out.contract not in ALL_CONTRACTS:
        p.append("Contract is not valid")
    for name, val in [("Contract Number", bill.contract_number), ("Subscription Number", bill.subscription_number),
                      ("Bill Period", bill.bill_period), ("Bill Month", bill.bill_month)]:
        if not val:
            p.append(f"{name} missing")
    if not isinstance(bill.total_charges, Decimal) or not isinstance(bill.vat, Decimal):
        p.append("Total charges and VAT must be numeric")
        return p
    if bill.vat < 0:
        p.append("VAT is negative")
    if bill.vat > bill.total_charges and bill.total_charges >= 0:
        p.append("VAT exceeds Total Charges for Bill Period")
    if out.total_without_vat != bill.total_charges - bill.vat:
        p.append("Total without VAT does not equal charges minus VAT")
    if out.group == GROUP_A:
        if len(out.allocations) != 4 or len({a.company for a in out.allocations}) != 4:
            p.append("Group A allocation must contain exactly four companies")
        if sum(a.amount for a in out.allocations) != money(out.total_without_vat):
            p.append("Group A allocations do not sum to total without VAT")
        if abs(out.rounding_adjustment) > Decimal("0.03"):
            p.append("Rounding adjustment exceeds documented tolerance (0.03)")
    if out.group == GROUP_B:
        if (out.related_company, out.cost_center) != GROUP_B_MAPPING.get(out.contract):
            p.append("Group B company / cost center does not match mapping")
    return p
