# Carton Factory Orders — Order Management System

Working Django project implementing the order search/filter system, with the
bug fixes from the review already built in (see "Fixes included" below).

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser   # your admin login
python manage.py runserver
```

Visit:
- `http://127.0.0.1:8000/` — order search (requires login)
- `http://127.0.0.1:8000/admin/` — admin panel (add Box Types, Ply Types, Customers, Orders)
- `http://127.0.0.1:8000/new/` — new order entry form

## Exporting search results to PDF

Click **Export to PDF** on the search page — it exports exactly the orders currently matching your filters (same filter logic as the on-screen results), as a landscape table PDF with invoice number, customer, box type, ply, dimensions, date, price, quantity, and printed status. Capped at 1000 rows per export to keep file size and generation time reasonable — narrow your filters (e.g. by date range) if you have more matching orders than that.

## First-time setup in the admin panel

1. Log in at `/admin/` with your superuser account.
2. Add at least one **Box Type** (e.g. RSC, Die-cut, Top-Bottom, Gift Box) and one **Ply Type** (3/5/7 Ply) — the order form and search filters read from these tables.
3. To let an admin add a new category later: **Admin panel → Box Types (or Ply Types) → Add** — it appears in search filters and the order form immediately, no code changes.

## Importing existing data

The app automatically detects the file format and uses the right parser — you never need to choose:

**Standard flat spreadsheet** (columns: Invoice Number, Customer Name, Address, Box Type, Ply Type, Length, Width, Height, Date Issued, Issued Price, Quantity, Printed) — handled by the parser described above.

**QuickBooks "Sales by Item Detail" export** — a completely different, nested report format (category/dimension group headers, subtotal rows, only "Invoice" type rows carry real data). The app recognizes this automatically and uses a dedicated parser (`orders/quickbooks_import.py`) that:
- Extracts box dimensions from free text in multiple formats (e.g. `3 X 3 X 9 Inches`, `1005x205x330 mm`, `01 Ft x 10Ft`, and this factory's round/board notation like `150x(R) 35mm`), converting everything to cm
- Extracts ply count and printed/unprinted status from the Memo text
- Skips non-box service charges (transport, printing cost, die cost, block making) rather than importing them as fake "orders"
- Splits a single QuickBooks invoice into multiple order rows when it covered several box types (common — one invoice number can span many line items), numbering them `1004-1`, `1004-2`, etc. so they stay traceable to the original invoice
- Uses QuickBooks' "Sales Price" (per-unit price) as the issued price — if you'd rather use the total line amount instead, let me know and it's a one-line change

Either way: **upload through the Import Excel page**, tick "Preview only" first to see exactly what would happen, then untick it to actually save. Rows that can't be confidently parsed are skipped and listed with the reason — nothing is guessed silently into the database.

## Fixes included in this scaffold

| Issue | Fix |
|---|---|
| Deleting a Box/Ply Type could wipe historical orders | `on_delete=models.PROTECT` — deletion is blocked while orders reference it |
| Money stored as float (rounding errors) | `DecimalField` for price and dimensions |
| Invoice numbers mangled on Excel import (`"0042"` → `42`) | Explicit `dtype=str` on read |
| Duplicate customers from name casing/whitespace | Names normalized (`.strip().title()`) before matching |
| Mixed/bad dates silently corrupting data | `pd.to_datetime(..., errors="coerce")` + explicit report of unparseable rows |
| Slow search on large tables | `db_index=True` on invoice_number/date_issued |
| N+1 queries in list/detail views | `select_related()` on all Order queries |
| No pagination | Built in from the start (25/page) |
| Unrestricted file uploads | `FileExtensionValidator` + 5MB size check in the form |
| Race condition on duplicate invoice submission | `IntegrityError` caught, shown as a clean form error |
| `DEBUG=True` / hardcoded secret key in production | Both read from environment variables (see `.env.example`) |
| No audit trail on edits | `django-simple-history` tracks every change per order |
| Anonymous users could view order data | All views wrapped in `@login_required` |
| Excel import only usable via command line | In-app upload page at `/import/` (staff-only), same logic as the CLI command, with dry-run preview and on-screen error reporting |
| No way to edit or remove a mistaken order from the app itself | Edit (`/<id>/edit/`) and Delete (`/<id>/delete/`) pages, staff-only, delete requires a confirmation step |
| Generic unstyled look, and CDN dependency for fonts/Bootstrap | Custom kraft/corrugated-board visual theme; Bootstrap and all fonts are self-hosted in `orders/static/` — the app renders correctly even with no internet access |

## Editing and deleting orders

On any order's detail page, staff/admin accounts see **Edit** and **Delete** buttons (regular accounts don't see them at all). Deleting always asks for confirmation first — there's no single click that removes an order.

**Attaching a pattern image after the fact:** imported orders (from Excel/QuickBooks) never come with images — attach one afterward either through **Edit** on the order's detail page, or through the **admin panel** (`/admin/orders/order/<id>/change/`), which now shows a live preview of the current image under a dedicated "Printing" section. Both work identically.

## Searching by dimensions — exact match vs range

Type a number into just the first (left) box for Length/Width/Height and it matches that **exact** dimension. Fill in both boxes and it becomes a genuine range between them. Leave both blank to ignore that filter. This applies to Length, Width, and Height independently — you can mix exact-match on one dimension with a range on another.

## Re-importing updated data

Importing a file never touches or overwrites orders already in the system — even ones you've since corrected by hand. Only invoice numbers/line-items genuinely new to that import get added. This means if your accounting export grows over time (new invoices added, old ones unchanged), you can safely re-upload the full updated file each time rather than needing to isolate just the new rows yourself.

## Users & permissions, explained

This app only uses three settings per user (no Django Groups, no granular permission pickers — those were removed since they had no effect and just added confusion):

- **Active** — unticking blocks login without deleting the account. Use this when someone leaves, instead of deleting them, so their name stays attached to past orders.
- **Staff status** — required to log in at all. Lets someone search/add/edit/delete orders and import Excel files.
- **Superuser status** — everything Staff status allows, plus managing other users and this admin's more sensitive areas.

The same explanation is shown directly on each user's edit page in `/admin/`, and the admin homepage now opens with a plain-language orientation panel instead of dropping you straight into raw Django admin menus.

**Adding new columns/fields** (something new to track per order, beyond what's here) is a quick code + migration change on my end, not a self-service admin action — just ask and it's usually a few minutes' work, after which it shows up in the admin, the search filters, and the order form automatically.

## Sample data to try it out with

`sample_mock_orders.xlsx` (included alongside this project) is a realistic 28-row sample sheet — different customers, box types, ply types, and dates, including two box types not pre-set-up in the admin panel, so you can see the "admin adds a category, import adapts automatically" behavior for yourself. Try uploading it through **Import Excel** with "Preview only" checked first, then for real.



By default (no env vars set), uploaded pattern images go to a local `/media` folder — fine for development, but **most hosting platforms wipe this on every redeploy**, so don't rely on it once real images matter.

**To go live for free:** create a free [Cloudinary](https://cloudinary.com) account, copy your `CLOUDINARY_URL` from the dashboard, and set it as an environment variable (see `.env.example`). That's the only step — nothing in the code changes. 25GB free storage/bandwidth covers a good while of pattern images.

**When you outgrow Cloudinary:** set `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` instead (works for both AWS S3 and DigitalOcean Spaces — add `AWS_S3_ENDPOINT_URL` for Spaces). Unset `CLOUDINARY_URL` and the app switches over automatically. Existing images already in Cloudinary won't auto-move — that's a one-time migration script if/when you switch, not something to worry about now.

## Running the automated tests

```bash
python manage.py test orders
```

53 tests covering the trickiest parts of this project: the QuickBooks import parser (dimension format edge cases, invoice-splitting, service-charge exclusion), the standard Excel import (re-import safety, customer name matching), the exact-vs-range search filter behavior, model-level data integrity (PROTECT, unique constraints), and access control (who can edit/delete what). Run this after making any change to confirm nothing broke.

## Deploying this online

See `DEPLOY.md` for a full step-by-step guide to putting this live on Render's free tier — a real clickable URL, not just something running on your own computer.

## Before deploying to production

- Set real values in `.env` (see `.env.example`) — **do not** commit `.env`.
- Switch `DEFAULT_FILE_STORAGE` to Cloudinary or S3 — local `/media` storage does not survive redeploys on most hosts.
- Switch the database from SQLite to PostgreSQL.
- Set up automatic daily database backups.
