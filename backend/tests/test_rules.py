from decimal import Decimal

from app import statuses as S
from app.parser import parse_bill
from app.rules import allocate_group_a, evaluate

BASE = """Contract Number: {c}
Subscription Number: 0501234567
Bill Period: 01/09/2026 - 30/09/2026
Previous Balance AED 500.00
Total Charges for Bill Period AED {t}
VAT (5%) AED {v}
Total Amount Payable AED 9,000.00
"""


def run(c="74745984", t="1,050.03", v="50.00", text=None):
    b = parse_bill(text or BASE.format(c=c, t=t, v=v))
    return b, evaluate(b)


def test_group_a_four_rows_sum_exactly():
    b, o = run()
    assert o.status == S.PROCESSED and o.group == "A"
    assert o.total_without_vat == Decimal("1000.03")
    assert len(o.allocations) == 4
    assert sum(a.amount for a in o.allocations) == Decimal("1000.03")
    assert o.rounding_adjustment == Decimal("-0.01")


def test_never_uses_amount_payable_or_previous_balance():
    text = BASE.format(c="72263692", t="0", v="5.00").replace("Total Charges for Bill Period AED 0\n", "")
    b, o = run(text=text)
    assert b.total_charges is None
    assert o.status == S.NEEDS_REVIEW


def test_vat_not_confused_with_registration_or_without_vat():
    text = BASE.format(c="72263692", t="525.00", v="25.00") + "VAT Registration Number: 100234567800003\nTotal Charges without VAT 500.00\n"
    b, o = run(text=text)
    assert b.vat == Decimal("25.00") and o.status == S.PROCESSED


def test_missing_vat_needs_review():
    b, o = run(text=BASE.format(c="72263692", t="525.00", v="").replace("VAT (5%) AED \n", ""))
    assert o.status == S.NEEDS_REVIEW and "VAT not found" in o.errors


def test_conflicting_totals_are_not_guessed():
    text = BASE.format(c="72263692", t="525.00", v="25.00") + "Total Charges for Bill Period AED 600.00\n"
    b, o = run(text=text)
    assert b.total_charges is None and o.status == S.NEEDS_REVIEW


def test_invalid_contract_ignored():
    _, o = run(c="12345678")
    assert o.status == S.IGNORED and o.group is None


def test_group_b_mapping():
    _, o = run(c="B603042", t="1260.50", v="60.02")
    assert (o.related_company, o.cost_center) == ("MD's Office", "1000FAMILYA")
    assert o.total_without_vat == Decimal("1200.48")


def test_group_b_cost_center_conflict():
    _, o = run(text=BASE.format(c="DBN0235456", t="100.00", v="5.00") + "Cost Center: 9999\n")
    assert o.status == S.NEEDS_REVIEW


def test_allocation_exact_share():
    share, allocs, adj = allocate_group_a(Decimal("100.00"))
    assert share == Decimal("25") and adj == 0 and all(a.amount == Decimal("25.00") for a in allocs)


def test_us_month_first_bill_period():
    b, o = run(c="72263692", t="525.00", v="25.00",
               text=BASE.format(c="72263692", t="525.00", v="25.00").replace("01/09/2026 - 30/09/2026", "08/01/2026 - 08/31/2026"))
    assert b.bill_month == "August 2026" and o.status == S.PROCESSED
