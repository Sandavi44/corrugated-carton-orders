from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, User
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import BoxType, Customer, Order, PlyType

admin.site.site_header = "Chelsy Packaging (Pvt) Ltd"
admin.site.site_title = "Chelsy Packaging Admin"
admin.site.index_title = "Order Management"

# This app doesn't use Django's Groups/permissions system — access is
# controlled by a single "Staff status" checkbox on each user (see
# UserAdmin below). Groups would just be an empty, confusing menu item
# with no effect on anything, so it's removed rather than left dangling.
admin.site.unregister(Group)

admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "is_staff", "is_superuser", "is_active", "last_login")

    # This app only checks is_staff / is_superuser — it never uses Django's
    # Groups or granular per-permission system, so those two pickers are
    # removed from the form entirely rather than left sitting there unused
    # and confusing. Only the three checkboxes that actually do something
    # for this app remain.
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("What these checkboxes actually do here", {
            "description": mark_safe(
                "<b>Staff status</b> — required to log in at all. Lets someone view/search "
                "orders, add/edit/delete orders, and import Excel files.<br><br>"
                "<b>Superuser status</b> — full access, including this Users page, adding new "
                "Box Types/Ply Types, and everything Staff status allows. Give this only to "
                "people who should be able to manage other people's accounts.<br><br>"
                "<b>Active</b> — unticking this blocks login without deleting the account "
                "(use this instead of Delete when someone leaves — keeps their name on old orders)."
            ),
            "fields": (),
        }),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "is_staff", "is_superuser"),
        }),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "phone")
    search_fields = ("name", "address")  # required for autocomplete_fields on Order to work


@admin.register(BoxType)
class BoxTypeAdmin(admin.ModelAdmin):
    # This is the screen your factory admin uses to "add a new category" —
    # no code changes, no redeploy. New rows here show up in search filters
    # and the order form immediately.
    list_display = ("name", "description", "is_active")
    list_editable = ("is_active",)
    search_fields = ("name",)


@admin.register(PlyType)
class PlyTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_editable = ("is_active",)
    search_fields = ("name",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number", "customer", "box_type", "ply_type",
        "date_issued", "issued_price", "quantity", "is_printed", "pattern_thumb",
    )
    list_filter = ("box_type", "ply_type", "is_printed", "date_issued")
    search_fields = ("invoice_number", "customer__name", "customer__address")
    autocomplete_fields = ("customer",)
    date_hierarchy = "date_issued"
    # select_related on the changelist avoids the N+1 query problem when
    # Django renders customer/box_type/ply_type for every row.
    list_select_related = ("customer", "box_type", "ply_type")
    readonly_fields = ("pattern_preview_large", "created_by", "created_at", "updated_at")

    # Grouped sections instead of one long flat list of fields — this is
    # also where staff can edit any imported order (including ones brought
    # in via Excel/QuickBooks import) and attach a pattern image after
    # the fact, since import doesn't carry images.
    fieldsets = (
        ("Order Identity", {
            "fields": ("invoice_number", "customer", "date_issued")
        }),
        ("Box Specification", {
            "fields": ("box_type", "ply_type", ("length_cm", "width_cm", "height_cm"))
        }),
        ("Pricing & Quantity", {
            "fields": ("issued_price", "quantity")
        }),
        ("Printing", {
            "fields": ("is_printed", "printed_pattern_image", "pattern_preview_large"),
            "description": "Attach or replace the pattern image here — works the same "
                            "whether this order was entered manually or came from an import.",
        }),
        ("Record Info", {
            "fields": ("created_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Pattern")
    def pattern_thumb(self, obj):
        if obj.printed_pattern_image:
            return format_html(
                '<img src="{}" style="height:32px;border-radius:3px;">',
                obj.printed_pattern_image.url,
            )
        return "—"

    @admin.display(description="Current pattern image")
    def pattern_preview_large(self, obj):
        if obj.printed_pattern_image:
            return format_html(
                '<img src="{}" style="max-height:200px;border:1px solid #ddd;border-radius:4px;">',
                obj.printed_pattern_image.url,
            )
        return "No image uploaded yet."
