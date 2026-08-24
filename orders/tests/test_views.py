import datetime

from django.contrib.auth.models import User
from django.test import TestCase

from orders.models import BoxType, Customer, Order, PlyType


class AccessControlTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user("staffuser", password="testpass123", is_staff=True)
        self.regular_user = User.objects.create_user("regularuser", password="testpass123")
        customer = Customer.objects.create(name="Test Co")
        box_type = BoxType.objects.create(name="RSC")
        ply_type = PlyType.objects.create(name="5 Ply")
        self.order = Order.objects.create(
            invoice_number="INV-1", customer=customer, box_type=box_type, ply_type=ply_type,
            length_cm=30, width_cm=20, height_cm=15, date_issued=datetime.date(2026, 1, 1),
            issued_price=100, quantity=10,
        )

    def test_anonymous_user_redirected_from_search(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)

    def test_logged_in_user_can_view_search(self):
        self.client.login(username="regularuser", password="testpass123")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_access_edit(self):
        self.client.login(username="regularuser", password="testpass123")
        response = self.client.get(f"/{self.order.pk}/edit/")
        self.assertEqual(response.status_code, 302)  # redirected, not shown the form

    def test_regular_user_cannot_delete(self):
        self.client.login(username="regularuser", password="testpass123")
        response = self.client.post(f"/{self.order.pk}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())  # not deleted

    def test_staff_user_can_edit(self):
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(f"/{self.order.pk}/edit/")
        self.assertEqual(response.status_code, 200)

    def test_delete_requires_post_not_just_get(self):
        """A GET request (e.g. a stray click, a link preview fetch) must
        never delete data — only an explicit POST after confirmation."""
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.get(f"/{self.order.pk}/delete/")
        self.assertEqual(response.status_code, 200)  # shows confirmation page
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())  # still exists

    def test_staff_delete_post_actually_deletes(self):
        self.client.login(username="staffuser", password="testpass123")
        response = self.client.post(f"/{self.order.pk}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())

    def test_regular_user_does_not_see_edit_delete_buttons(self):
        self.client.login(username="regularuser", password="testpass123")
        response = self.client.get(f"/{self.order.pk}/")
        self.assertNotIn(b">Edit<", response.content)
        self.assertNotIn(b">Delete<", response.content)


class OrderCreateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("staffuser", password="testpass123", is_staff=True)
        self.customer = Customer.objects.create(name="Test Co")
        self.box_type = BoxType.objects.create(name="RSC")
        self.ply_type = PlyType.objects.create(name="5 Ply")
        self.client.login(username="staffuser", password="testpass123")

    def test_duplicate_invoice_number_shows_form_error_not_500(self):
        Order.objects.create(
            invoice_number="DUP-1", customer=self.customer, box_type=self.box_type,
            ply_type=self.ply_type, length_cm=10, width_cm=10, height_cm=10,
            date_issued=datetime.date(2026, 1, 1), issued_price=10, quantity=1,
        )
        response = self.client.post("/new/", {
            "invoice_number": "DUP-1", "customer": self.customer.id,
            "box_type": self.box_type.id, "ply_type": self.ply_type.id,
            "length_cm": 20, "width_cm": 20, "height_cm": 20,
            "date_issued": "2026-01-02", "issued_price": 50, "quantity": 5,
        })
        self.assertEqual(response.status_code, 200)  # re-renders form, doesn't crash
        self.assertIn(b"already exists", response.content)
