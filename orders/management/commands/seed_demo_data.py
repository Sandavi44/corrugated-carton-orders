"""
Management command: seed_demo_data
Populates the database with fake customers, box types, ply types, and orders
for the portfolio staging demo. Safe to run multiple times (idempotent).
Only intended for use when DEMO_MODE=true.
"""
import os
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from orders.models import BoxType, Customer, Order, PlyType


DEMO_CUSTOMERS = [
    {"name": "Packaging Co. (Demo)", "address": "45 Industrial Zone, Colombo 15", "phone": "011-2345678"},
    {"name": "FreshBox Exports (Demo)", "address": "12 Export Park, Gampaha", "phone": "033-2987654"},
    {"name": "Ceylon Corrugated (Demo)", "address": "88 Factory Road, Kalutara", "phone": "034-2223456"},
    {"name": "Lanka Cartons (Demo)", "address": "21 Biyagama EPZ, Gampaha", "phone": "011-2398765"},
]

DEMO_BOX_TYPES = [
    {"name": "Regular Slotted Container", "description": "Standard RSC — most common box style"},
    {"name": "Half-Slotted Container", "description": "Open-top HSC for display and retail"},
    {"name": "Full Overlap Slotted", "description": "FOS — extra stacking strength"},
    {"name": "Die-Cut Box", "description": "Custom die-cut shape for specialty products"},
    {"name": "Tray", "description": "Shallow open tray for produce and bakery"},
]

DEMO_PLY_TYPES = [
    {"name": "3 Ply"},
    {"name": "5 Ply"},
    {"name": "7 Ply"},
]

DEMO_ORDERS = [
    # (customer_name, box_type_name, ply_type_name, L, W, H, date, price, qty, printed)
    ("Packaging Co. (Demo)",    "Regular Slotted Container", "3 Ply", "40.00", "30.00", "25.00", date(2026, 7, 12),  "96.55",  5000, False),
    ("FreshBox Exports (Demo)", "Half-Slotted Container",    "5 Ply", "50.00", "35.00", "30.00", date(2026, 7, 28), "184.15",  2000, False),
    ("Ceylon Corrugated (Demo)","Regular Slotted Container", "3 Ply", "25.00", "20.00", "15.00", date(2026, 8,  5),  "44.98", 10000, True),
    ("Packaging Co. (Demo)",    "Full Overlap Slotted",      "5 Ply", "60.00", "40.00", "35.00", date(2026, 8, 19), "241.96",  3000, False),
    ("FreshBox Exports (Demo)", "Regular Slotted Container", "3 Ply", "32.00", "22.00", "18.00", date(2026, 9,  2),  "49.75",  7500, False),
    ("Lanka Cartons (Demo)",    "Tray",                      "3 Ply", "45.00", "30.00",  "8.00", date(2026, 9, 10),  "28.40",  4000, True),
    ("Ceylon Corrugated (Demo)","Die-Cut Box",               "5 Ply", "35.00", "25.00", "20.00", date(2026, 9, 15), "138.60",  1500, True),
    ("Lanka Cartons (Demo)",    "Regular Slotted Container", "7 Ply", "55.00", "45.00", "40.00", date(2026, 9, 18), "312.00",   800, False),
]


class Command(BaseCommand):
    help = "Seed the database with fake demo data for the portfolio staging instance."

    def handle(self, *args, **options):
        if os.environ.get("DEMO_MODE", "").lower() != "true":
            self.stdout.write(self.style.WARNING(
                "DEMO_MODE is not set to 'true' — skipping seed to protect production data."
            ))
            return

        self.stdout.write("Seeding demo data...")

        # Demo user
        demo_user, created = User.objects.get_or_create(
            username="demo",
            defaults={"first_name": "Demo", "last_name": "User", "is_staff": False},
        )
        if created:
            self.stdout.write("  Created demo user.")

        # Customers
        customers = {}
        for c in DEMO_CUSTOMERS:
            obj, _ = Customer.objects.get_or_create(name=c["name"], defaults=c)
            customers[c["name"]] = obj
        self.stdout.write(f"  {len(customers)} customers ready.")

        # Box types
        box_types = {}
        for b in DEMO_BOX_TYPES:
            obj, _ = BoxType.objects.get_or_create(name=b["name"], defaults=b)
            box_types[b["name"]] = obj
        self.stdout.write(f"  {len(box_types)} box types ready.")

        # Ply types
        ply_types = {}
        for p in DEMO_PLY_TYPES:
            obj, _ = PlyType.objects.get_or_create(name=p["name"])
            ply_types[p["name"]] = obj
        self.stdout.write(f"  {len(ply_types)} ply types ready.")

        # Orders
        created_count = 0
        for idx, (cust, box, ply, l, w, h, dt, price, qty, printed) in enumerate(DEMO_ORDERS, start=1):
            invoice = f"DEMO-{dt.year}-{idx:04d}"
            if not Order.objects.filter(invoice_number=invoice).exists():
                Order.objects.create(
                    invoice_number=invoice,
                    customer=customers[cust],
                    box_type=box_types[box],
                    ply_type=ply_types[ply],
                    length_cm=Decimal(l),
                    width_cm=Decimal(w),
                    height_cm=Decimal(h),
                    date_issued=dt,
                    issued_price=Decimal(price),
                    quantity=qty,
                    is_printed=printed,
                    created_by=demo_user,
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"  {created_count} new orders created ({len(DEMO_ORDERS) - created_count} already existed)."
        ))
        self.stdout.write(self.style.SUCCESS("Demo seed complete."))
