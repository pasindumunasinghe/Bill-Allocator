"""Sample inputs for usage-based allocation: Dialog + SLT bill PDFs, usage workbook, master and map.

Usage: python tests/make_usage_samples.py <output_dir>
"""
import sys
from pathlib import Path

import openpyxl
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _pdf(path, lines):
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for ln in lines:
        c.drawString(30, y, ln)
        y -= 16
    c.save()


def _xlsx(path, sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets:
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    wb.save(path)


def make(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    _pdf(out / "Dialog_B698359_Jun.pdf", [
        "CONTRACT NUMBER B698359", "BILL PERIOD 01/06/2026 - 30/06/2026",
        "Previous Due Amount 4,185,528.86", "Charges for Bill Period",
        "Government Taxes & Levies 63,228.86", "VAT 106,347.96",
        "Total Charges for Bill Period 697,216.82", "Total Amount Payable 3,486,036.46",
        "Summary Contract Number : B698359", "Subscription Charges",
        "117780953 1,440.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 1,440.00",
        "994620243 255,000.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 255,000.00",
        "Total Voice / VPN Charges 60,000.00",
    ])
    _pdf(out / "SLT_0033118626_Jun.pdf", [
        "Account No 003 311 8626 Orel Corporation (Pvt) Ltd", "01/06/2026 -", "Bill Period", "30/06/2026",
        "Balance BF Payment Received Arrears Total Payable",
        "Sub Total Rental and Other Charges 134450.00", "CESS 2742.78", "Recovery in lieu of SSCL 3512.14",
        "VAT-18% 25326.89", "Total charges for the period 166031.81", "Total Payments Received 498095.43",
    ])
    _pdf(out / "Other_bill.pdf", ["CONTRACT NUMBER X1", "Total 10.00"])
    _xlsx(out / "usage.xlsx", [
        ("Sheet1", [["Firewall report"], [], ["Source User", "Usage (MB)"],
                    ["OREL\\kamal", 2048], ["OREL\\kamal", 1024], ["OREL\\nimal.p", 1024], ["OREL\\shared", 512],
                    ["OREL\\ghost", 1024], ["Total", 99999], ["Others", 500]]),
        ("Sheet2", [["Source User", "Usage (GB)"], ["OREL\\kamal", 1], ["OREL\\sunil_k", 4], ["others", 7]]),
        ("Sheet3", [["username", "total_usage in GB"], ["Nimal.P@orel.com", 2], ["nimal.p@orel.com", 50],
                    ["sunil-k", 1], ["others", 3]]),
    ])
    _xlsx(out / "Emp.xlsx", [("Employees", [
        ["Emp No", "Emp Name", "Email", "Company", "Dimension"],
        [100, "Kamal Perera", "kamal@orel.com", "OCP Product Company", "1100700610"],
        [101, "Nimal Peiris", "nimal.p@orel.com", "OCP Admin Company", "1100130020"],
        ["All Company", "Shared Account", "shared@orel.com", "All", ""],
    ])])
    _xlsx(out / "map.xlsx", [("map", [
        ["Username", "Emp No", "Company", "Emp Name", "Dimension"],
        ["sunilk", 102, "OCP Manufacturing Company", "Sunil K", "1100500100"],
    ])])
    return out


if __name__ == "__main__":
    print(make(Path(sys.argv[1] if len(sys.argv) > 1 else "../samples/usage")))
