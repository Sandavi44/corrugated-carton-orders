"""
Builds the PDF for order search-result exports. Kept in its own module so
the layout logic doesn't clutter views.py and can be unit-tested on its own.
"""
import io

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

COLUMN_HEADERS = [
    "Invoice #", "Customer", "Box Type", "Ply", "Dimensions (cm)",
    "Date Issued", "Price", "Qty", "Printed",
]


def build_orders_pdf(orders, truncated=False, total_matching=None):
    """
    orders: iterable of Order instances (already select_related'd by the caller).
    Returns raw PDF bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Chelsy Packaging (Pvt) Ltd — Order Export", styles["Title"]))
    generated_line = f"Generated {timezone.now().strftime('%Y-%m-%d %H:%M')} — {len(orders)} order(s)"
    if truncated:
        generated_line += (
            f" shown (of {total_matching} matching — export is capped; "
            f"narrow your filters to export the rest)"
        )
    elements.append(Paragraph(generated_line, styles["Normal"]))
    elements.append(Spacer(1, 8 * mm))

    data = [COLUMN_HEADERS]
    for o in orders:
        data.append([
            o.invoice_number,
            o.customer.name,
            o.box_type.name,
            o.ply_type.name,
            f"{o.length_cm}×{o.width_cm}×{o.height_cm}",
            o.date_issued.strftime("%Y-%m-%d"),
            f"{o.issued_price}",
            str(o.quantity),
            "Printed" if o.is_printed else "Unprinted",
        ])

    if len(data) == 1:
        elements.append(Paragraph("No orders match the current filters.", styles["Normal"]))
    else:
        table = Table(data, repeatRows=1)  # repeatRows: header repeats on every page
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
