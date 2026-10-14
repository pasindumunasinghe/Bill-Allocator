"""Generate realistic sample telecom bills covering both groups and failure cases.

Usage: python tests/make_samples.py <output_dir>
"""
import sys
from pathlib import Path

import docx
import openpyxl
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def bill_lines(contract, subscription, period, total, vat, extra=None, omit=()):
    lines = [
        "Etisalat Business - Tax Invoice",
        "Invoice Date: 05/10/2026",
        "VAT Registration Number: 100234567800003",
        f"Contract Number: {contract}",
        f"Subscription Number: {subscription}",
        f"Bill Period: {period}",
        "",
        "Summary of Charges",
        "Previous Balance AED 4,210.00",
        "Payments Received AED -4,210.00",
        "Monthly Rental AED 1,000.00",
        "Usage Charges AED 650.00",
        f"Total Charges for Bill Period AED {total}",
        f"VAT (5%) AED {vat}",
        "Outstanding Balance AED 0.00",
        "Total Amount Payable AED 9,999.99",
    ]
    lines += extra or []
    return [ln for ln in lines if not any(ln.startswith(o) for o in omit)]


def pdf(path, lines):
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 18
    c.save()


def scanned_pdf(path):
    """A PDF page with only a drawn image-like shape and no text layer."""
    c = canvas.Canvas(str(path), pagesize=A4)
    c.rect(50, 500, 400, 250, fill=1)
    c.save()


def make(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    # Group A
    pdf(out / "GroupA_74745984_Sep2026.pdf",
        bill_lines("74745984", "0501234567", "01/09/2026 - 30/09/2026", "1,733.25", "82.54"))
    pdf(out / "GroupA_74745984_Aug2026_rounding.pdf",
        bill_lines("74745984", "0501234567", "01/08/2026 - 31/08/2026", "1,050.03", "50.00"))
    # Group B - several formats
    pdf(out / "GroupB_72263692.pdf", bill_lines("72263692", "0559876543", "01 Sep 2026 to 30 Sep 2026", "525.00", "25.00"))
    pdf(out / "GroupB_ES00014124.pdf", bill_lines("ES00014124", "0431112222", "01/09/2026 - 30/09/2026", "2,100.00", "100.00"))
    pdf(out / "GroupB_72272015.pdf", bill_lines("72272015", "0554443333", "01/09/2026 - 30/09/2026", "315.00", "15.00"))
    d = docx.Document()
    for ln in bill_lines("DBN0160965", "DU-778899", "01/09/2026 - 30/09/2026", "840.00", "40.00"):
        d.add_paragraph(ln)
    d.save(out / "GroupB_DBN0160965.docx")
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in [["Contract Number", "B603042"], ["Subscription Number", "0509990000"],
                ["Bill Period", "01/09/2026 - 30/09/2026"], ["Total Charges for Bill Period", 1260.50],
                ["VAT", 60.02], ["Total Amount Payable", 5000]]:
        ws.append(row)
    wb.save(out / "GroupB_B603042.xlsx")
    # Failure cases
    pdf(out / "Invalid_contract_99999999.pdf",
        bill_lines("99999999", "0500000000", "01/09/2026 - 30/09/2026", "100.00", "5.00"))
    pdf(out / "GroupB_74746314_missing_VAT.pdf",
        bill_lines("74746314", "0507770000", "01/09/2026 - 30/09/2026", "400.00", "0", omit=("VAT (5%)",)))
    pdf(out / "GroupB_DBN0235456_payable_only.pdf",
        bill_lines("DBN0235456", "0506660000", "01/09/2026 - 30/09/2026", "0", "10.00",
                   omit=("Total Charges for Bill Period",)))
    (out / "GroupB_ES00008395_corrupt.pdf").write_bytes(b"%PDF-1.4\nthis is not a valid pdf body")
    scanned_pdf(out / "GroupA_74745984_scanned.pdf")
    (out / "notes.txt").write_text("Unsupported file type")
    return out


if __name__ == "__main__":
    print(make(Path(sys.argv[1] if len(sys.argv) > 1 else "../samples")))
