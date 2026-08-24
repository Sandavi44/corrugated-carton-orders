import io

import pandas as pd
from django.test import TestCase

from orders.excel_import import import_orders_from_excel
from orders.models import Customer, Order


def _build_flat_workbook(rows):
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return buf


class StandardExcelImportTests(TestCase):
    def test_basic_import(self):
        wb_file = _build_flat_workbook([{
            "Invoice Number": "CP-1", "Customer Name": "Alpha Traders", "Address": "1 Main St",
            "Box Type": "RSC", "Ply Type": "5 Ply", "Length": 30, "Width": 20, "Height": 15,
            "Date Issued": "2026-01-01", "Issued Price": 100, "Quantity": 10, "Printed": "No",
        }])
        stats = import_orders_from_excel(wb_file, dry_run=False)
        self.assertEqual(stats["created"], 1)
        order = Order.objects.get(invoice_number="CP-1")
        self.assertEqual(order.customer.name, "Alpha Traders")

    def test_invoice_number_with_leading_zero_preserved(self):
        wb_file = _build_flat_workbook([{
            "Invoice Number": "0042", "Customer Name": "Beta Corp", "Address": "",
            "Box Type": "RSC", "Ply Type": "5 Ply", "Length": 30, "Width": 20, "Height": 15,
            "Date Issued": "2026-01-01", "Issued Price": 100, "Quantity": 10, "Printed": "No",
        }])
        import_orders_from_excel(wb_file, dry_run=False)
        self.assertTrue(Order.objects.filter(invoice_number="0042").exists())

    def test_duplicate_customer_names_with_different_casing_merge(self):
        wb_file = _build_flat_workbook([
            {"Invoice Number": "A1", "Customer Name": "ABC Traders", "Address": "",
             "Box Type": "RSC", "Ply Type": "5 Ply", "Length": 30, "Width": 20, "Height": 15,
             "Date Issued": "2026-01-01", "Issued Price": 100, "Quantity": 10, "Printed": "No"},
            {"Invoice Number": "A2", "Customer Name": "abc traders", "Address": "",
             "Box Type": "RSC", "Ply Type": "5 Ply", "Length": 30, "Width": 20, "Height": 15,
             "Date Issued": "2026-01-02", "Issued Price": 100, "Quantity": 10, "Printed": "No"},
        ])
        import_orders_from_excel(wb_file, dry_run=False)
        self.assertEqual(Customer.objects.count(), 1)

    def test_row_missing_invoice_number_is_skipped(self):
        wb_file = _build_flat_workbook([{
            "Invoice Number": None, "Customer Name": "Gamma Ltd", "Address": "",
            "Box Type": "RSC", "Ply Type": "5 Ply", "Length": 30, "Width": 20, "Height": 15,
            "Date Issued": "2026-01-01", "Issued Price": 100, "Quantity": 10, "Printed": "No",
        }])
        stats = import_orders_from_excel(wb_file, dry_run=False)
        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["skipped"], 1)

    def test_reimport_preserves_manual_edits(self):
        """Existing orders — even manually corrected ones — must never be
        overwritten by a later import; only genuinely new rows get added."""
        wb_file1 = _build_flat_workbook([{
            "Invoice Number": "P-1", "Customer Name": "Delta Inc", "Address": "",
            "Box Type": "RSC", "Ply Type": "5 Ply", "Length": 30, "Width": 20, "Height": 15,
            "Date Issued": "2026-01-01", "Issued Price": 100, "Quantity": 10, "Printed": "No",
        }])
        import_orders_from_excel(wb_file1, dry_run=False)

        order = Order.objects.get(invoice_number="P-1")
        order.issued_price = 999  # manual correction
        order.save()

        wb_file2 = _build_flat_workbook([
            {"Invoice Number": "P-1", "Customer Name": "Delta Inc", "Address": "",
             "Box Type": "RSC", "Ply Type": "5 Ply", "Length": 30, "Width": 20, "Height": 15,
             "Date Issued": "2026-01-01", "Issued Price": 100, "Quantity": 10, "Printed": "No"},
            {"Invoice Number": "P-2", "Customer Name": "Epsilon LLC", "Address": "",
             "Box Type": "RSC", "Ply Type": "5 Ply", "Length": 30, "Width": 20, "Height": 15,
             "Date Issued": "2026-02-01", "Issued Price": 200, "Quantity": 5, "Printed": "No"},
        ])
        stats = import_orders_from_excel(wb_file2, dry_run=False)

        order.refresh_from_db()
        self.assertEqual(order.issued_price, 999)  # untouched
        self.assertTrue(Order.objects.filter(invoice_number="P-2").exists())  # new one added
        self.assertEqual(stats["created"], 1)  # only P-2 counted as newly created
