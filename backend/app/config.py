"""Contract lists and fixed business mappings. Single source of truth."""
import os

GROUP_A = "A"
GROUP_B = "B"

GROUP_A_CONTRACT = "74745984"

# Group A: dimension -> company. Each successful bill is split equally across these four.
GROUP_A_ALLOCATIONS = [
    ("1100190000", "OCP Innovation Company"),
    ("1100700660", "OCP Product Company"),
    ("1100130020", "OCP Admin Company"),
    ("1100500100", "OCP Manufacturing Company"),
]

# Group B: contract -> (related company, cost center)
GROUP_B_MAPPING = {
    "72263692": ("OCP Product Company", "1100700610"),
    "72272015": ("OCP Product Company", "1100700610"),
    "74746314": ("Admin company", "1100130020"),
    "B603042": ("MD's Office", "1000FAMILYA"),
    "DBN0103018": ("OCP Product Company", "1100700300"),
    "DBN0160965": ("Innovation Company", "1100190000"),
    "DBN0235456": ("MD's Office", "1000"),
    "ES00008395": ("OCP Product Company", "1100700610"),
    "ES00014124": ("OCP Manufacturing Company", "1100500901"),
}

ALL_CONTRACTS = {GROUP_A_CONTRACT: GROUP_A, **{c: GROUP_B for c in GROUP_B_MAPPING}}

GROUP_A_FILENAME = f"{GROUP_A_CONTRACT}_Allocation.xlsx"
GROUP_B_FILENAME = "Telecom_Bill_Summary.xlsx"

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls"}

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./telecom_bills.db")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "25"))
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]


def classify(contract: str | None) -> str | None:
    if not contract:
        return None
    return ALL_CONTRACTS.get(contract.strip().upper())
