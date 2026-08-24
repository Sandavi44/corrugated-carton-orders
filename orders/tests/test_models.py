import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from orders.models import BoxType, Customer, Order, PlyType


class OrderModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Test Customer")
        self.box_type = BoxType.objects.create(name="RSC")
        self.ply_type = PlyType.objects.create(name="5 Ply")

    def make_order(self, **overrides):
        defaults = dict(
            invoice_number="INV-0001",
            customer=self.customer,
            box_type=self.box_type,
            ply_type=self.ply_type,
            length_cm=30, width_cm=20, height_cm=15,
            date_issued=datetime.date(2026, 1, 1),
            issued_price=100, quantity=10,
        )
        defaults.update(overrides)
        return Order.objects.create(**defaults)

    def test_duplicate_invoice_number_rejected(self):
        """The database itself must reject a second order with the same
        invoice number — this is what prevents two staff members
        accidentally overwriting each other's entries."""
        self.make_order(invoice_number="DUPLICATE")
        with self.assertRaises(IntegrityError):
            self.make_order(invoice_number="DUPLICATE")

    def test_deleting_box_type_in_use_is_blocked(self):
        """PROTECT, not CASCADE: deleting a category that's still
        referenced by real orders must fail loudly, not silently wipe
        historical data."""
        self.make_order()
        with self.assertRaises(ProtectedError):
            self.box_type.delete()
        # order must still exist afterward
        self.assertTrue(Order.objects.filter(invoice_number="INV-0001").exists())

    def test_deleting_ply_type_in_use_is_blocked(self):
        self.make_order()
        with self.assertRaises(ProtectedError):
            self.ply_type.delete()

    def test_unused_box_type_can_still_be_deleted(self):
        """PROTECT only blocks deletion when something actually depends
        on it — an unused category should delete normally."""
        unused = BoxType.objects.create(name="Never Used")
        unused.delete()  # should not raise
        self.assertFalse(BoxType.objects.filter(name="Never Used").exists())

    def test_printed_order_without_image_fails_validation(self):
        """clean() enforces the rule everywhere (admin, forms, API),
        not just in one form's ad-hoc check."""
        order = Order(
            invoice_number="INV-PRINTED", customer=self.customer,
            box_type=self.box_type, ply_type=self.ply_type,
            length_cm=30, width_cm=20, height_cm=15,
            date_issued=datetime.date(2026, 1, 1),
            issued_price=100, quantity=10, is_printed=True,
        )
        with self.assertRaises(ValidationError):
            order.clean()

    def test_unprinted_order_without_image_is_valid(self):
        order = Order(
            invoice_number="INV-UNPRINTED", customer=self.customer,
            box_type=self.box_type, ply_type=self.ply_type,
            length_cm=30, width_cm=20, height_cm=15,
            date_issued=datetime.date(2026, 1, 1),
            issued_price=100, quantity=10, is_printed=False,
        )
        order.clean()  # should not raise
