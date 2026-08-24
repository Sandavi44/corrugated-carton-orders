"""
Shared Excel import logic, used by both:
  - the management command (python manage.py import_orders file.xlsx)
  - the in-app "Import Excel" upload page (for staff who don't use the command line)

Keeping this in one place means both entry points get the same validation
and the same bug fixes, instead of two copies drifting apart over time.
"""
import pandas as pd
from django.db import transaction

from orders.models import BoxType, Customer, Order, PlyType

REQUIRED_COLUMNS = [
    "Invoice Number", "Customer Name", "Box Type", "Ply Type",
    "Date Issued", "Issued Price", "Quantity",
]


def clean_str(value, default=""):
    """NaN-safe string cleanup: strips surrounding whitespace."""
    if pd.isna(value):
        return default
    return str(value).strip()


def get_or_create_customer(name, address=""):
    """Matches customers case-insensitively ('ABC Traders' / 'abc traders'
    / 'ABC TRADERS' all resolve to the same record) without blindly
    .title()-casing the stored name, which would mangle names like
    'McDonald' or 'ABC Ltd' into 'Mcdonald' / 'Abc Ltd'. The first
    spelling seen for a given name is the one that's kept."""
    existing = Customer.objects.filter(name__iexact=name).first()
    if existing:
        return existing, False
    return Customer.objects.create(name=name, address=address), True


class DryRunRollback(Exception):
    """Raised to unwind the transaction after a dry-run parse/validate pass."""


def check_columns(df):
    """Returns a list of required columns missing from the sheet, so the
    caller can show a clear error instead of a confusing crash mid-import."""
    return [col for col in REQUIRED_COLUMNS if col not in df.columns]


def import_orders_from_excel(file_obj, dry_run=False):
    """
    file_obj: an open file, Django UploadedFile, or path string.
    Returns a stats dict: created, skipped, bad_dates, skipped_rows, missing_columns.
    Never raises on bad *data* — only on a genuinely unreadable file.
    """
    df = pd.read_excel(file_obj, dtype={"Invoice Number": str})

    missing_columns = check_columns(df)
    if missing_columns:
        return {
            "created": 0, "skipped": 0, "bad_dates": 0,
            "skipped_rows": [], "missing_columns": missing_columns,
        }

    # Dates are coerced explicitly: mixed/bad formats become NaT (reported
    # at the end) instead of silently corrupting the column.
    df["Date Issued"] = pd.to_datetime(df.get("Date Issued"), errors="coerce")

    stats = {"created": 0, "skipped": 0, "bad_dates": 0, "skipped_rows": [], "missing_columns": []}

    try:
        with transaction.atomic():
            _import_rows(df, stats)
            if dry_run:
                raise DryRunRollback()
    except DryRunRollback:
        pass

    return stats


def _import_rows(df, stats):
    for idx, row in df.iterrows():
        invoice_number = clean_str(row.get("Invoice Number"))
        if not invoice_number:
            stats["skipped"] += 1
            stats["skipped_rows"].append((idx, "missing invoice number"))
            continue

        if pd.isna(row.get("Date Issued")):
            stats["bad_dates"] += 1
            stats["skipped_rows"].append((idx, f"unparseable date for invoice {invoice_number}"))
            continue

        customer_name = clean_str(row.get("Customer Name"))
        if not customer_name:
            stats["skipped"] += 1
            stats["skipped_rows"].append((idx, f"missing customer name for invoice {invoice_number}"))
            continue

        customer, _ = get_or_create_customer(customer_name, clean_str(row.get("Address")))
        box_type, _ = BoxType.objects.get_or_create(
            name=clean_str(row.get("Box Type"), default="Unspecified")
        )
        ply_type, _ = PlyType.objects.get_or_create(
            name=clean_str(row.get("Ply Type"), default="Unspecified")
        )

        is_printed = clean_str(row.get("Printed")).lower() in ("yes", "y", "true", "1")

        order, was_created = Order.objects.get_or_create(
            invoice_number=invoice_number,
            defaults={
                "customer": customer,
                "box_type": box_type,
                "ply_type": ply_type,
                "length_cm": row.get("Length") or 0,
                "width_cm": row.get("Width") or 0,
                "height_cm": row.get("Height") or 0,
                "date_issued": row["Date Issued"].date(),
                "issued_price": row.get("Issued Price") or 0,
                "quantity": int(row.get("Quantity") or 1),
                "is_printed": is_printed,
            },
        )
        if was_created:
            stats["created"] += 1
        else:
            stats["skipped"] += 1
            stats["skipped_rows"].append((idx, f"invoice {invoice_number} already exists"))
