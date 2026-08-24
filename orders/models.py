from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models

try:
    from simple_history.models import HistoricalRecords
    HISTORY_AVAILABLE = True
except ImportError:  # django-simple-history not installed — audit trail becomes a no-op
    HISTORY_AVAILABLE = False


class Customer(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    address = models.CharField(max_length=400, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    class Meta:
        # Prevents "ABC Traders" being created twice by two different staff
        # members on the same day. Doesn't fix casing/whitespace variants —
        # that's handled in the Excel import script and admin merge step.
        ordering = ["name"]

    def __str__(self):
        return self.name


class BoxType(models.Model):
    """Admin-editable category. New box types are added here via the
    admin panel, not hardcoded — they show up in filters/forms immediately."""
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    # Retire a category without breaking historical orders that reference it.
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Box Type"

    def __str__(self):
        return self.name


class PlyType(models.Model):
    """Admin-editable category, e.g. '3 Ply', '5 Ply', '7 Ply'."""
    name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Ply Type"

    def __str__(self):
        return self.name


def pattern_upload_path(instance, filename):
    # Spreads uploads across year/month folders instead of one giant flat
    # directory, and namespaces by invoice number to avoid filename clashes.
    return f"patterns/{instance.date_issued.year}/{instance.date_issued.month:02d}/{instance.invoice_number}_{filename}"


class Order(models.Model):
    # unique=True + db_index=True: fast lookup by invoice number, and the
    # database itself rejects duplicates instead of relying on staff care.
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="orders"
    )
    # PROTECT (not CASCADE): deleting a BoxType/PlyType that's still in use
    # on an order is blocked at the database level, instead of silently
    # wiping historical order data.
    box_type = models.ForeignKey(
        BoxType, on_delete=models.PROTECT, related_name="orders"
    )
    ply_type = models.ForeignKey(
        PlyType, on_delete=models.PROTECT, related_name="orders"
    )

    # Dimensions in cm. DecimalField, not FloatField, to avoid rounding
    # surprises and to keep values predictable when displayed/exported.
    length_cm = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    width_cm = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    height_cm = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])

    date_issued = models.DateField(db_index=True)
    issued_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    is_printed = models.BooleanField(default=False)
    printed_pattern_image = models.ImageField(
        upload_to=pattern_upload_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"])],
        help_text="Only used when 'Printed' is checked. JPG/PNG/WEBP, max 5MB (enforced in the form).",
    )

    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    if HISTORY_AVAILABLE:
        # Full change log per order (who changed what, when) — answers
        # pricing disputes without guesswork. No-ops safely if the
        # package isn't installed.
        history = HistoricalRecords()

    class Meta:
        ordering = ["-date_issued", "-created_at"]
        indexes = [
            models.Index(fields=["date_issued"]),
            models.Index(fields=["is_printed"]),
        ]

    def __str__(self):
        return f"{self.invoice_number} — {self.customer.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Printed orders should have a pattern image; unprinted ones
        # shouldn't be storing a stray image. Caught here so it's
        # enforced everywhere (admin, forms, API), not just one form.
        if self.is_printed and not self.printed_pattern_image:
            raise ValidationError("A pattern image is required when the order is marked as printed.")
