import django_filters
from django import forms

from .models import BoxType, Order, PlyType


class MinMaxWidget(forms.MultiWidget):
    """Range widget with clearly labeled Min/Max inputs, instead of two
    identical-looking boxes where it's unclear which is which."""
    def __init__(self, attrs=None):
        widgets = [
            forms.NumberInput(attrs={"placeholder": "Exact", "step": "0.01"}),
            forms.NumberInput(attrs={"placeholder": "or Max", "step": "0.01"}),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return [value.start, value.stop]
        return [None, None]


class DateMinMaxWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        base_attrs = {**(attrs or {}), "type": "date"}
        widgets = [
            forms.DateInput(attrs={**base_attrs, "placeholder": "From"}),
            forms.DateInput(attrs={**base_attrs, "placeholder": "To"}),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return [value.start, value.stop]
        return [None, None]


class ExactOrRangeFilter(django_filters.RangeFilter):
    """Dimension filters people expect to work like a search box, not a
    database range query: type one number -> exact match on that number.
    Fill in BOTH Min and Max -> genuine range between them. Only behaves
    as an open-ended "at least X" / "at most X" range when both boxes
    are used; a single filled box is always treated as exact."""
    def filter(self, qs, value):
        if value is None:
            return qs
        start, stop = value.start, value.stop
        if start is not None and stop is not None:
            return super().filter(qs, value)  # real range: both bounds given
        if start is not None:
            return qs.filter(**{self.field_name: start})  # exact match
        if stop is not None:
            return qs.filter(**{self.field_name: stop})  # exact match
        return qs


class OrderFilter(django_filters.FilterSet):
    invoice_number = django_filters.CharFilter(lookup_expr="icontains")
    customer_name = django_filters.CharFilter(
        field_name="customer__name", lookup_expr="icontains", label="Customer name"
    )
    customer_address = django_filters.CharFilter(
        field_name="customer__address", lookup_expr="icontains", label="Customer address"
    )
    box_type = django_filters.ModelChoiceFilter(
        queryset=BoxType.objects.filter(is_active=True)
    )
    ply_type = django_filters.ModelChoiceFilter(
        queryset=PlyType.objects.filter(is_active=True)
    )
    date_issued = django_filters.DateFromToRangeFilter(
        widget=DateMinMaxWidget(), label="Date issued (from – to)"
    )
    length_cm = ExactOrRangeFilter(widget=MinMaxWidget(), label="Length cm")
    width_cm = ExactOrRangeFilter(widget=MinMaxWidget(), label="Width cm")
    height_cm = ExactOrRangeFilter(widget=MinMaxWidget(), label="Height cm")
    is_printed = django_filters.ChoiceFilter(
        choices=((True, "Printed"), (False, "Unprinted")),
        widget=forms.Select,
        empty_label="Any",
    )

    class Meta:
        model = Order
        fields = [
            "invoice_number", "customer_name", "customer_address",
            "box_type", "ply_type", "date_issued",
            "length_cm", "width_cm", "height_cm", "is_printed",
        ]
