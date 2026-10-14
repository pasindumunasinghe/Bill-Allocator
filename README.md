# Telecom Bill Processing System

Upload telecom bills (PDF, DOCX, XLSX, XLS), extract bill fields, apply the Group A / Group B contract rules, validate, and download Excel reports.

| Layer | Tech | Location |
|---|---|---|
| UI | React 18 + Vite | `frontend/` |
| API | Python FastAPI | `backend/app/main.py` |
| Extraction | pdfplumber (text PDFs), Tesseract OCR fallback (scanned pages), python-docx, openpyxl, xlrd | `backend/app/extraction.py` |
| Field parsing | strict label-based regex | `backend/app/parser.py` |
| Business rules & validation | `decimal.Decimal` | `backend/app/rules.py`, `backend/app/config.py` |
| Excel generation | openpyxl | `backend/app/excel.py` |
| Storage | PostgreSQL (SQLite fallback for local dev/tests) | `backend/app/db.py` |

Document processing and Excel generation run on the server. The UI only talks to the API through `frontend/src/api.js`. Excel files are generated with openpyxl on the server, not ExcelJS/SheetJS in the browser, so the files always match the validated records stored in the database.

## Running it

### Option A: Docker (PostgreSQL + API with OCR)
```bash
POSTGRES_PASSWORD=choose-a-password docker compose up -d --build
cd frontend && npm install && npm run dev      # http://localhost:5173
```

### Option B: Local
Requirements: Python 3.11+, Node 18+, and optionally PostgreSQL 14+ and Tesseract.
```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg2://telecom:password@localhost:5432/telecom_bills   # omit to use local SQLite
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev        # proxies /api to http://localhost:8000
```
Tables are created automatically on startup.

**OCR (scanned PDFs):** install Tesseract (`apt install tesseract-ocr` / `brew install tesseract`). The sidebar shows whether OCR is available. Without it, scanned pages are reported as a File Read Failure with the reason. A page is never skipped silently.

### Environment variables (backend)
| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./telecom_bills.db` | SQLAlchemy URL; use PostgreSQL in production |
| `UPLOAD_DIR` | `./uploads` | where uploaded originals are kept |
| `MAX_UPLOAD_MB` | `25` | per-file size limit |
| `CORS_ORIGINS` | `http://localhost:5173` | comma-separated allowed UI origins |

There are no external APIs and no API keys. OCR runs locally. If you later add a cloud OCR service (e.g. AWS Textract or Azure Document Intelligence), call it **only from the backend**, read the key from an environment variable or secret manager, and never put it in `frontend/` or in `VITE_*` variables. Those values are bundled into the browser.

## Workflow
1. **Upload Bills**: select or drag in several files. Each file is stored and queued. Unsupported types are flagged straight away.
2. **Process Bills**: queued files are sent to the server one at a time (`POST /api/files/{id}/process`). The progress bar follows real server results. Each file is read (retried once), parsed, classified, calculated and validated on its own.
3. **Download Reports**: available after every queued file has been processed. Group A → `74745984_Allocation.xlsx`, Group B → `Telecom_Bill_Summary.xlsx`. These are always separate files.
4. **Clear Queue**: removes files that have not been processed yet. Processed outcomes stay in history.

## Extraction rules
- **Total Charges** comes only from the value labelled `Total Charges for Bill Period`. Amount Payable, Previous Balance, Payments and Outstanding are never used.
- **VAT** comes from its own label (`VAT`, `VAT (5%)`, `VAT Amount`, `Total VAT`). Lines such as `VAT Registration Number`, `… without VAT` and `incl. VAT` are rejected.
- A missing label, or a label that appears with conflicting values, sets the field to empty and the bill to **Needs Review**. Nothing is guessed.
- **Contract number** comes from the `Contract Number` label. If there is no label, the parser looks for exactly one known contract printed in the document. Contracts outside both lists are **Ignored - Contract Not In Scope**.
- **Bill Month** comes from a `Bill Month` label if present. Otherwise it is taken from the extracted Bill Period end date, and the record notes that.
- **Group B company and cost center** come from the fixed mapping. If the bill prints a different cost center, the bill is flagged for review.
- **Unreadable files** (corrupt, or image-only without OCR): if the filename contains a valid contract, the failure is routed to that group's report so it is not dropped. The UI marks this "from filename".

## Statuses
`Processed Successfully`, `File Read Failure`, `Needs Review`, `Validation Failed`, `Ignored - Contract Not In Scope`, `Unsupported Format`.

The Group A **Validation** sheet may only contain `Processed Successfully` or `File Read Failure`, so any Group A outcome other than success appears there as `File Read Failure`. The exact reason is shown on the app's Failed Records page. The Group B **Failed Records** sheet shows the status plus the reason.

## Calculations and rounding
- All amounts use `Decimal`, parsed exactly as printed. Source values are never rounded.
- `Total Without VAT = Total Charges for Bill Period − VAT`
- **Group A:** `Allocation Per Company = Total Without VAT / 4`. The Calculation Summary shows the exact share to 4 dp. Allocation rows are rounded half-up to 2 dp, and any remainder (at most ±0.03) goes to the **last company (OCP Manufacturing, 1100500100)**, so the four rows always add up exactly to Total Without VAT. Any adjustment is shown as its own line in the Calculation Summary.
- **Group B:** Cost Center Summary = sum of Total Charges without VAT, grouped by cost center.

Checks run before a record counts as processed: valid contract, required fields present, numeric amounts, VAT ≤ total, total-without-VAT equals charges − VAT, exactly four distinct Group A companies whose amounts sum exactly, and the correct Group B mapping. Export is blocked (HTTP 409) while files are still queued.

## Tests
```bash
cd backend
python tests/make_samples.py ../samples     # regenerate the sample bills
python -m pytest -q
```
Sample bills in `samples/` (upload them all at once to test a mixed-group batch):

| File | Expected outcome |
|---|---|
| `GroupA_74745984_Sep2026.pdf` | Processed; 1,650.71 → 412.68 ×3 + 412.67 |
| `GroupA_74745984_Aug2026_rounding.pdf` | Processed; 1,000.03 → 250.01 ×3 + 250.00 (adjustment −0.01) |
| `GroupA_74745984_scanned.pdf` | File Read Failure without OCR (image-only page) |
| `GroupB_72263692.pdf`, `GroupB_72272015.pdf` | Processed; both cost center 1100700610 → summary 800.00 |
| `GroupB_ES00014124.pdf` | Processed |
| `GroupB_DBN0160965.docx` | Processed (DOCX) |
| `GroupB_B603042.xlsx` | Processed (XLSX); also contains "Total Amount Payable", which is ignored |
| `GroupB_74746314_missing_VAT.pdf` | Needs Review: VAT not found |
| `GroupB_DBN0235456_payable_only.pdf` | Needs Review: only Amount Payable present, Total Charges not found |
| `GroupB_ES00008395_corrupt.pdf` | File Read Failure after retry; listed in Group B Failed Records |
| `Invalid_contract_99999999.pdf` | Ignored (not in either list) |
| `notes.txt` | Unsupported Format |

## API
`POST /api/batches` · `GET /api/batches` · `GET /api/batches/{id}` · `POST /api/batches/{id}/files` (multipart `files`) · `POST /api/files/{id}/process` · `POST /api/batches/{id}/process` · `DELETE /api/batches/{id}/queue` · `GET /api/batches/{id}/reports` · `GET /api/batches/{id}/reports/group-a` · `GET /api/batches/{id}/reports/group-b` · `GET /api/health`

## Limitations
- The parser expects the field labels used on standard telecom invoices (listed above). A layout with very different labels is flagged for review rather than guessed. Add label variants in `parser.py`.
- OCR accuracy depends on scan quality. OCR-read pages carry a "verify values" note.
- Legacy `.doc` and image files (`.jpg`, `.png`) are not accepted.
- There is no authentication yet. Put the app behind your SSO or reverse proxy before exposing it.
