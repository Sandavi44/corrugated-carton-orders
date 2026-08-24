import io

import openpyxl
from django.test import TestCase

from orders.models import BoxType, Customer, Order, PlyType
from orders.quickbooks_import import (
    extract_box_type, extract_dimensions_cm, extract_is_printed, extract_ply,
    import_from_quickbooks_export, is_non_box_line, looks_like_quickbooks_export,
)


class DimensionExtractionTests(TestCase):
    """Each of these is a real format found in an actual factory export —
    not invented edge cases. Getting any of these wrong means silently
    wrong data in the system."""

    def test_feet_notation_converts_correctly(self):
        # This one was an actual bug: units on each number were being
        # discarded, giving 1x10cm instead of the correct ~30x305cm.
        self.assertEqual(extract_dimensions_cm("01 Ft x 10Ft"), (30.48, 304.8, 0))

    def test_inches_notation(self):
        self.assertEqual(extract_dimensions_cm("3 X 3 X 9 Inches"), (7.62, 7.62, 22.86))

    def test_mm_three_dimensions(self):
        self.assertEqual(extract_dimensions_cm("1005x205x330 mm"), (100.5, 20.5, 33.0))

    def test_cm_with_decimal(self):
        self.assertEqual(extract_dimensions_cm("10x9.5x58 cm"), (10.0, 9.5, 58.0))

    def test_round_board_notation(self):
        # This factory's own notation for round/board items: "x(R)"
        self.assertEqual(extract_dimensions_cm("150x(R) 35mm"), (15.0, 3.5, 0))

    def test_two_dimension_partition_defaults_height_to_zero(self):
        self.assertEqual(extract_dimensions_cm("Partition 2x3"), (2.0, 3.0, 0))

    def test_no_dimensions_found_returns_none(self):
        self.assertIsNone(extract_dimensions_cm("Transport"))

    def test_falls_back_to_second_text_if_first_has_no_dimensions(self):
        result = extract_dimensions_cm("", "40x30x20 cm B/L 03Ply Carton")
        self.assertEqual(result, (40.0, 30.0, 20.0))


class BoxTypePlyPrintedExtractionTests(TestCase):
    def test_die_cut_detected(self):
        self.assertEqual(extract_box_type("3 X 3 X 9 Inches B/L 03Ply Die Cut Carton"), "Die-cut")

    def test_unrecognized_text_falls_back_to_generic_carton(self):
        self.assertEqual(extract_box_type("some random product description"), "Carton")

    def test_ply_extracted_and_normalized(self):
        self.assertEqual(extract_ply("B/L 03Ply Carton"), "3 Ply")
        self.assertEqual(extract_ply("B/L 15Ply Crease Board"), "15 Ply")

    def test_no_ply_mentioned_falls_back_to_unspecified(self):
        self.assertEqual(extract_ply("Transport"), "Unspecified")

    def test_unprinted_detected(self):
        self.assertFalse(extract_is_printed("40x30x20 cm B/L 03Ply Unprinted Carton"))

    def test_printed_detected(self):
        self.assertTrue(extract_is_printed("40x30x20 cm One Colour Printed Carton"))

    def test_no_signal_defaults_to_unprinted(self):
        self.assertFalse(extract_is_printed("40x30x20 cm B/L 03Ply Carton"))

    def test_service_charges_identified_as_non_box(self):
        self.assertTrue(is_non_box_line("Transport", "Transport"))
        self.assertTrue(is_non_box_line("Printing Cost", "Finish Goods:Printing Cost"))
        self.assertTrue(is_non_box_line("Die Cost", "Finish Goods:Die cost"))

    def test_real_box_line_not_flagged_as_service_charge(self):
        self.assertFalse(is_non_box_line("40x30x20 cm B/L 03Ply Carton", "Finish Goods:Glued Carton"))


def _build_quickbooks_workbook(rows):
    """Builds a minimal in-memory .xlsx matching the real QuickBooks
    export column layout, so the parser can be tested without needing an
    actual exported file on disk."""
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = ["A", "B", "C", "D", "E", "Type", "Date", "Num", "Memo",
               "P.O.#", "Name", "Billed Date", "Item", "Item Description",
               "Qty", "U/M", "Sales Price", "Amount", "Balance"]
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _detail_row(type_="Invoice", date="2026-01-15", num="1001", memo="30x20x15 cm B/L 03Ply Carton",
                 name="Test Customer", item="Finish Goods:Box", item_desc="30x20x15 cm",
                 qty=10, price=100):
    import datetime as dt
    date_val = dt.datetime.strptime(date, "%Y-%m-%d") if date else None
    return [None, None, None, None, None, type_, date_val, num, memo,
            None, name, None, item, item_desc, qty, "PCS", price, qty * price if price else None, None]


class QuickBooksImportIntegrationTests(TestCase):
    """End-to-end tests through the actual import function, not just the
    helper functions in isolation — this is what catches wiring bugs."""

    def test_format_detection_recognizes_quickbooks_export(self):
        wb_file = _build_quickbooks_workbook([_detail_row()])
        self.assertTrue(looks_like_quickbooks_export(wb_file))

    def test_basic_import_creates_order_with_correct_fields(self):
        wb_file = _build_quickbooks_workbook([
            _detail_row(num="2001", name="Alpha Traders", memo="30x20x15 cm B/L 03Ply Unprinted Carton", price=50, qty=10),
        ])
        stats = import_from_quickbooks_export(wb_file, dry_run=False)
        self.assertEqual(stats["created"], 1)
        order = Order.objects.get(invoice_number="2001")
        self.assertEqual(order.customer.name, "Alpha Traders")
        self.assertEqual((order.length_cm, order.width_cm, order.height_cm), (30, 20, 15))
        self.assertEqual(order.ply_type.name, "3 Ply")
        self.assertFalse(order.is_printed)
        self.assertEqual(order.issued_price, 50)
        self.assertEqual(order.quantity, 10)

    def test_dry_run_creates_nothing(self):
        wb_file = _build_quickbooks_workbook([_detail_row(num="3001")])
        import_from_quickbooks_export(wb_file, dry_run=True)
        self.assertEqual(Order.objects.count(), 0)

    def test_service_charge_line_is_skipped_not_imported(self):
        wb_file = _build_quickbooks_workbook([
            _detail_row(num="4001", item="Transport", item_desc="Transport", memo="Transport"),
        ])
        stats = import_from_quickbooks_export(wb_file, dry_run=False)
        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["non_box_skipped"], 1)
        self.assertEqual(Order.objects.count(), 0)

    def test_single_quickbooks_invoice_split_across_lines_gets_suffixed(self):
        """One QuickBooks invoice number covering multiple box types must
        become multiple Order rows with distinguishable numbers, since our
        schema is one-box-type-per-order — but a single-line invoice must
        NOT get a suffix it doesn't need."""
        wb_file = _build_quickbooks_workbook([
            _detail_row(num="5001", memo="30x20x15 cm B/L 03Ply Carton", item_desc="30x20x15 cm"),
            _detail_row(num="5001", memo="40x30x20 cm B/L 05Ply Carton", item_desc="40x30x20 cm"),
            _detail_row(num="5002", memo="10x10x10 cm B/L 03Ply Carton", item_desc="10x10x10 cm"),
        ])
        stats = import_from_quickbooks_export(wb_file, dry_run=False)
        self.assertEqual(stats["created"], 3)
        self.assertTrue(Order.objects.filter(invoice_number="5001-1").exists())
        self.assertTrue(Order.objects.filter(invoice_number="5001-2").exists())
        # single-line invoice keeps its original number, no suffix
        self.assertTrue(Order.objects.filter(invoice_number="5002").exists())
        self.assertFalse(Order.objects.filter(invoice_number="5002-1").exists())

    def test_reimporting_same_file_does_not_duplicate(self):
        wb_file1 = _build_quickbooks_workbook([_detail_row(num="6001")])
        import_from_quickbooks_export(wb_file1, dry_run=False)
        wb_file2 = _build_quickbooks_workbook([_detail_row(num="6001")])
        import_from_quickbooks_export(wb_file2, dry_run=False)
        self.assertEqual(Order.objects.filter(invoice_number="6001").count(), 1)

    def test_new_box_type_in_import_is_auto_created(self):
        """Admin-managed categories must accept new values found in an
        import, not just ones pre-configured through the admin panel."""
        self.assertFalse(BoxType.objects.filter(name="Ceiling Panel").exists())
        wb_file = _build_quickbooks_workbook([
            _detail_row(num="7001", memo="100x50 mm B/L 03Ply Ceiling Panel", item_desc="100x50 mm"),
        ])
        import_from_quickbooks_export(wb_file, dry_run=False)
        self.assertTrue(BoxType.objects.filter(name="Ceiling Panel").exists())

    def test_row_missing_dimensions_is_skipped_with_reason_not_guessed(self):
        wb_file = _build_quickbooks_workbook([
            _detail_row(num="8001", memo="no dimensions here", item_desc="no dimensions here"),
        ])
        stats = import_from_quickbooks_export(wb_file, dry_run=False)
        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["no_dimension_skipped"], 1)

    def test_customer_name_casing_does_not_create_duplicates(self):
        wb_file = _build_quickbooks_workbook([
            _detail_row(num="9001", name="Alpha Traders"),
            _detail_row(num="9002", name="alpha traders"),
        ])
        import_from_quickbooks_export(wb_file, dry_run=False)
        self.assertEqual(Customer.objects.count(), 1)
