from django import forms

from .models import Order

MAX_IMAGE_SIZE_MB = 5
MAX_EXCEL_SIZE_MB = 15


class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(
        label="Excel file (.xlsx)",
        help_text="Expected columns: Invoice Number, Customer Name, Address, "
                   "Box Type, Ply Type, Length, Width, Height, Date Issued, "
                   "Issued Price, Quantity, Printed.",
    )
    dry_run = forms.BooleanField(
        label="Preview only (don't save yet)",
        required=False,
        initial=True,
        help_text="Recommended for the first run on a new file — shows you "
                   "exactly what would happen without changing the database.",
    )

    def clean_excel_file(self):
        f = self.cleaned_data["excel_file"]
        if not f.name.lower().endswith((".xlsx", ".xls")):
            raise forms.ValidationError("Please upload an Excel file (.xlsx or .xls).")
        if f.size > MAX_EXCEL_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(f"File is too large — max {MAX_EXCEL_SIZE_MB}MB.")
        return f


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            "invoice_number", "customer", "box_type", "ply_type",
            "length_cm", "width_cm", "height_cm",
            "date_issued", "issued_price", "quantity",
            "is_printed", "printed_pattern_image",
        ]
        widgets = {
            "date_issued": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_printed_pattern_image(self):
        image = self.cleaned_data.get("printed_pattern_image")
        if image and image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(
                f"Image is too large — max {MAX_IMAGE_SIZE_MB}MB."
            )
        return image

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_printed") and not cleaned.get("printed_pattern_image"):
            self.add_error(
                "printed_pattern_image",
                "Please upload the pattern image, or uncheck 'Printed'.",
            )
        return cleaned
