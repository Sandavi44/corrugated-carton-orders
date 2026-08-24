from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .excel_import import import_orders_from_excel
from .filters import OrderFilter
from .forms import ExcelUploadForm, OrderForm
from .models import Order
from .pdf_export import build_orders_pdf
from .quickbooks_import import import_from_quickbooks_export, looks_like_quickbooks_export


@login_required
def order_search(request):
    # select_related avoids the N+1 problem: without it, Django fires a
    # separate query per row for customer/box_type/ply_type when the
    # template renders order.customer.name etc.
    base_qs = Order.objects.select_related("customer", "box_type", "ply_type")
    order_filter = OrderFilter(request.GET or None, queryset=base_qs)

    # Pagination — required from day one, not added later once the order
    # table has grown large enough to make the page slow.
    paginator = Paginator(order_filter.qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "orders/search.html", {
        "filter": order_filter,
        "page_obj": page_obj,
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("customer", "box_type", "ply_type"), pk=pk
    )
    return render(request, "orders/order_detail.html", {"order": order})


@login_required
def order_create(request):
    if request.method == "POST":
        form = OrderForm(request.POST, request.FILES)
        if form.is_valid():
            order = form.save(commit=False)
            order.created_by = request.user
            try:
                order.save()
            except IntegrityError:
                # unique=True on invoice_number rejects this at the DB
                # level (e.g. two staff submitting the same number at
                # once) — caught here so the user sees a clear message
                # instead of a raw server error.
                form.add_error("invoice_number", "This invoice number already exists.")
            else:
                return redirect("order_detail", pk=order.pk)
    else:
        form = OrderForm()

    return render(request, "orders/order_form.html", {"form": form, "is_edit": False})


@user_passes_test(lambda u: u.is_staff)
def order_edit(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == "POST":
        form = OrderForm(request.POST, request.FILES, instance=order)
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                form.add_error("invoice_number", "This invoice number already exists.")
            else:
                return redirect("order_detail", pk=order.pk)
    else:
        form = OrderForm(instance=order)

    return render(request, "orders/order_form.html", {"form": form, "is_edit": True})


@user_passes_test(lambda u: u.is_staff)
def order_delete(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == "POST":
        order.delete()
        return redirect("order_search")
    # GET shows a confirmation page — deleting is never a single click.
    return render(request, "orders/order_confirm_delete.html", {"order": order})


@user_passes_test(lambda u: u.is_staff)
def excel_import_view(request):
    """
    In-app "Import Excel" page — lets an admin/staff member upload the
    factory's spreadsheet directly through the browser instead of using
    the command line. Restricted to staff accounts since importing writes
    a lot of data at once.
    """
    stats = None
    used_quickbooks_parser = False
    if request.method == "POST":
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data["excel_file"]
            dry_run = form.cleaned_data["dry_run"]
            try:
                if looks_like_quickbooks_export(uploaded_file):
                    used_quickbooks_parser = True
                    stats = import_from_quickbooks_export(uploaded_file, dry_run=dry_run)
                else:
                    stats = import_orders_from_excel(uploaded_file, dry_run=dry_run)
            except Exception as exc:
                # Catches genuinely unreadable files (corrupt file, wrong
                # format) — bad *data* inside a valid file is handled row
                # by row inside the import functions, not here.
                form.add_error(
                    "excel_file",
                    f"Couldn't read this file: {exc}. Make sure it's a valid .xlsx file.",
                )
    else:
        form = ExcelUploadForm()

    return render(request, "orders/excel_import.html", {
        "form": form, "stats": stats, "used_quickbooks_parser": used_quickbooks_parser,
    })


MAX_PDF_ROWS = 1000  # keeps export fast and the PDF file size sane


@login_required
def order_export_pdf(request):
    """
    Exports the *currently filtered* search results as a PDF — reuses the
    same OrderFilter as the search page, so what you see on screen is
    exactly what you get in the PDF.
    """
    base_qs = Order.objects.select_related("customer", "box_type", "ply_type")
    order_filter = OrderFilter(request.GET or None, queryset=base_qs)
    orders = list(order_filter.qs[:MAX_PDF_ROWS])
    total_matching = order_filter.qs.count()

    pdf_bytes = build_orders_pdf(orders, truncated=total_matching > MAX_PDF_ROWS, total_matching=total_matching)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="orders_export.pdf"'
    return response
