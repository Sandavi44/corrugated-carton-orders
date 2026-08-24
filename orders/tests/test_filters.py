import datetime

from django.test import TestCase

from orders.filters import OrderFilter
from orders.models import BoxType, Customer, Order, PlyType


class DimensionFilterTests(TestCase):
    """Covers the exact bug a real user hit: typing one number into a
    dimension filter must match ONLY that exact value, not 'at least
    this much' — that's the difference between a search box and a
    database range query, and it matters for finding a specific order."""

    def setUp(self):
        customer = Customer.objects.create(name="Test Customer")
        box_type = BoxType.objects.create(name="RSC")
        ply_type = PlyType.objects.create(name="5 Ply")
        for length in (20, 30, 35, 40, 45):
            Order.objects.create(
                invoice_number=f"LEN-{length}", customer=customer,
                box_type=box_type, ply_type=ply_type,
                length_cm=length, width_cm=20, height_cm=15,
                date_issued=datetime.date(2026, 1, 1),
                issued_price=100, quantity=10,
            )
        self.qs = Order.objects.all()

    def test_single_min_value_is_exact_match(self):
        f = OrderFilter({"length_cm_0": "35"}, queryset=self.qs)
        results = list(f.qs)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].length_cm, 35)

    def test_single_max_value_is_also_exact_match(self):
        f = OrderFilter({"length_cm_1": "35"}, queryset=self.qs)
        results = list(f.qs)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].length_cm, 35)

    def test_both_values_given_is_a_real_range(self):
        f = OrderFilter({"length_cm_0": "30", "length_cm_1": "40"}, queryset=self.qs)
        lengths = sorted(o.length_cm for o in f.qs)
        self.assertEqual(lengths, [30, 35, 40])

    def test_no_value_returns_everything(self):
        f = OrderFilter({}, queryset=self.qs)
        self.assertEqual(f.qs.count(), 5)

    def test_exact_match_on_value_with_no_orders_returns_empty(self):
        f = OrderFilter({"length_cm_0": "999"}, queryset=self.qs)
        self.assertEqual(f.qs.count(), 0)


class CustomerAndBoxTypeFilterTests(TestCase):
    def setUp(self):
        self.customer_a = Customer.objects.create(name="Alpha Traders")
        self.customer_b = Customer.objects.create(name="Beta Corp")
        self.rsc = BoxType.objects.create(name="RSC")
        self.diecut = BoxType.objects.create(name="Die-cut")
        ply = PlyType.objects.create(name="3 Ply")
        Order.objects.create(
            invoice_number="A-1", customer=self.customer_a, box_type=self.rsc, ply_type=ply,
            length_cm=10, width_cm=10, height_cm=10, date_issued=datetime.date(2026, 1, 1),
            issued_price=10, quantity=1,
        )
        Order.objects.create(
            invoice_number="B-1", customer=self.customer_b, box_type=self.diecut, ply_type=ply,
            length_cm=10, width_cm=10, height_cm=10, date_issued=datetime.date(2026, 1, 1),
            issued_price=10, quantity=1,
        )

    def test_filter_by_partial_customer_name(self):
        f = OrderFilter({"customer_name": "alpha"}, queryset=Order.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertEqual(f.qs.first().invoice_number, "A-1")

    def test_filter_by_box_type_excludes_other_types(self):
        f = OrderFilter({"box_type": self.diecut.id}, queryset=Order.objects.all())
        self.assertEqual(f.qs.count(), 1)
        self.assertEqual(f.qs.first().invoice_number, "B-1")
