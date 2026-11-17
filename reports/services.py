import io
from decimal import Decimal

from django.core.files.base import ContentFile
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from catalog.models import SiteConfig
from .models import Invoice, generate_invoice_number


def generate_invoice_pdf(order) -> bytes:
    """
    Generates a clean, professional GST tax invoice PDF in memory using ReportLab.
    Includes business details from SiteConfig, customer coordinates,
    line items with Feeding indicators, and financial breakdown.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#BE185D'),  # brand rose-pink
    )
    subtitle_style = ParagraphStyle(
        'InvoiceSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#4B5563'),
    )
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#111827'),
    )
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#111827'),
    )
    cell_normal = ParagraphStyle(
        'CellNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#374151'),
    )
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        alignment=1,  # Center
        textColor=colors.HexColor('#9CA3AF'),
    )

    site_config = SiteConfig.get_solo()
    gstin = site_config.gstin or 'URP (Unregistered Person / Pending Registration)'
    registered_address = site_config.registered_address or 'Sony Collections, Hyderabad, Telangana, India'

    # 1. Header: Company Info and Invoice Meta
    header_data = [
        [
            Paragraph(
                f"<b>SONY FEEDING KURTIS</b><br/>"
                f"<font size=8 color='#4B5563'>{registered_address}</font><br/>"
                f"<font size=8 color='#4B5563'><b>GSTIN:</b> {gstin}</font>",
                cell_normal,
            ),
            Paragraph(
                f"<font size=16 color='#BE185D'><b>TAX INVOICE</b></font><br/>"
                f"<font size=8.5><b>Invoice No:</b> INV-{order.order_number}<br/>"
                f"<b>Order No:</b> {order.order_number}<br/>"
                f"<b>Date:</b> {order.created_at.strftime('%d-%b-%Y')}<br/>"
                f"<b>Payment:</b> {order.payment_method.upper()} ({order.payment_status})</font>",
                cell_normal,
            ),
        ]
    ]

    header_table = Table(header_data, colWidths=[310, 213])
    header_table.setStyle(
        TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ])
    )
    story.append(header_table)
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E5E7EB'), spaceAfter=12))

    # 2. Billing & Shipping Coordinates
    addr_line2 = f", {order.apartment}" if order.apartment else ""
    landmark_line = f"<br/>Landmark: {order.landmark}" if order.landmark else ""
    coords_data = [
        [
            Paragraph("<b>BILLED & SHIPPED TO:</b>", cell_bold),
            Paragraph("<b>DISPATCH / TRACKING DETAILS:</b>", cell_bold),
        ],
        [
            Paragraph(
                f"<b>{order.full_name}</b><br/>"
                f"Phone: {order.phone}<br/>"
                f"Email: {order.email}<br/>"
                f"{order.shipping_address}{addr_line2}{landmark_line}<br/>"
                f"{order.city}, {order.state} - {order.zip_code}",
                cell_normal,
            ),
            Paragraph(
                f"<b>Status:</b> {order.order_status}<br/>"
                f"<b>Carrier:</b> {order.carrier_name or 'Standard Courier'}<br/>"
                f"<b>Tracking No:</b> {order.tracking_number or 'Assigned upon dispatch'}",
                cell_normal,
            ),
        ],
    ]
    coords_table = Table(coords_data, colWidths=[310, 213])
    coords_table.setStyle(
        TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ])
    )
    story.append(coords_table)
    story.append(Spacer(1, 14))

    # 3. Line Items Table
    items_header = [
        Paragraph("<b>#</b>", cell_bold),
        Paragraph("<b>Item Description</b>", cell_bold),
        Paragraph("<b>Type</b>", cell_bold),
        Paragraph("<b>SKU</b>", cell_bold),
        Paragraph("<b>Qty</b>", cell_bold),
        Paragraph("<b>Unit Price</b>", cell_bold),
        Paragraph("<b>Total</b>", cell_bold),
    ]

    items_table_data = [items_header]

    for idx, item in enumerate(order.items.all(), start=1):
        # Pink marker for Feeding garments
        type_str = f"<font color='#EC4899'><b>{item.clothing_type}</b></font>" if item.clothing_type == 'Feeding' else item.clothing_type
        desc = f"<b>{item.product_name}</b><br/><font size=7.5 color='#6B7280'>Color: {item.color} | Size: {item.size}</font>"
        items_table_data.append([
            Paragraph(str(idx), cell_normal),
            Paragraph(desc, cell_normal),
            Paragraph(type_str, cell_normal),
            Paragraph(item.product_sku, cell_normal),
            Paragraph(str(item.quantity), cell_normal),
            Paragraph(f"INR {item.unit_price:.2f}", cell_normal),
            Paragraph(f"INR {item.line_total:.2f}", cell_normal),
        ])

    items_table = Table(items_table_data, colWidths=[24, 209, 70, 75, 30, 55, 60])
    items_table.setStyle(
        TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ])
    )
    story.append(items_table)
    story.append(Spacer(1, 12))

    # 4. Financial Calculation Summary Table
    tax_info = "Included in price"
    if site_config.tax_percentage:
        tax_pct = site_config.tax_percentage
        tax_val = (order.subtotal * (Decimal(tax_pct) / Decimal('100'))).quantize(Decimal('0.01'))
        tax_info = f"INR {tax_val:.2f} ({tax_pct}%)"

    summary_data = [
        ["", "Subtotal:", f"INR {order.subtotal:.2f}"],
        ["", "Discount:", f"- INR {order.discount:.2f}"],
        ["", "Delivery Shipping:", f"INR {order.shipping_fee:.2f}"],
        ["", "GST Tax:", tax_info],
        ["", "Grand Total (INR):", f"INR {order.total_amount:.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[303, 120, 100])
    summary_table.setStyle(
        TableStyle([
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (1, 4), (-1, 4), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1, 4), (-1, 4), colors.HexColor('#BE185D')),
            ('FONTSIZE', (1, 4), (-1, 4), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ])
    )
    story.append(summary_table)
    story.append(Spacer(1, 24))

    # 5. Declarations & Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E5E7EB'), spaceAfter=8))
    story.append(Paragraph(
        "Declaration: This is a computer-generated tax invoice and requires no physical signature.<br/>"
        "All disputes are subject to the exclusive jurisdiction of the courts in Hyderabad, Telangana.<br/>"
        "Thank you for choosing Sony Feeding Kurtis! For customer support, email info@sonyfeedingkurtis.com",
        footer_style,
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def get_or_create_invoice_for_order(order) -> Invoice:
    """
    Deterministic retrieval or creation of legal Invoice for an order.
    Saves generated PDF directly to the model's FileField.
    """
    invoice = Invoice.objects.filter(order=order).first()
    if invoice:
        return invoice

    site_config = SiteConfig.get_solo()
    tax_amount = Decimal('0.00')
    if site_config.tax_percentage:
        rate = Decimal(site_config.tax_percentage) / Decimal('100')
        tax_amount = (order.subtotal * rate).quantize(Decimal('0.01'))

    pdf_bytes = generate_invoice_pdf(order)

    invoice = Invoice(
        invoice_number=generate_invoice_number(order.order_number),
        order=order,
        gst_number=site_config.gstin,
        subtotal=order.subtotal,
        tax_amount=tax_amount,
        grand_total=order.total_amount,
    )
    invoice.pdf_file.save(f"invoice_{order.order_number}.pdf", ContentFile(pdf_bytes), save=False)
    invoice.save()
    return invoice


def export_orders_to_excel(queryset) -> bytes:
    """
    Exports a queryset of Orders to a formatted .xlsx Excel workbook.
    Includes separate Feeding garment breakdown, item summaries, and GST columns.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Orders Master Report"

    # Styling definitions
    header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='BE185D', end_color='BE185D', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    thin_border = Border(
        left=Side(style='thin', color='E5E7EB'),
        right=Side(style='thin', color='E5E7EB'),
        top=Side(style='thin', color='E5E7EB'),
        bottom=Side(style='thin', color='E5E7EB'),
    )

    headers = [
        'Order Number',
        'Order Date',
        'Customer Name',
        'Phone',
        'Email',
        'Delivery Address',
        'City',
        'State',
        'Pincode',
        'Has Feeding Wear',
        'Feeding Garments Count',
        'Non-Feeding Count',
        'Total Items Count',
        'Items Detail',
        'Subtotal (INR)',
        'Shipping Fee (INR)',
        'Discount (INR)',
        'Grand Total (INR)',
        'Payment Method',
        'Payment Status',
        'Fulfilment Status',
        'Tracking Number',
        'Carrier',
    ]

    ws.append(headers)

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # Populate data rows
    for order in queryset.prefetch_related('items'):
        feeding_count = sum(item.quantity for item in order.items.all() if item.clothing_type == 'Feeding')
        non_feeding_count = sum(item.quantity for item in order.items.all() if item.clothing_type in ('Non-Feeding', 'Standard'))
        items_summary = "; ".join(
            f"{i.quantity}x {i.product_name} ({i.clothing_type}-{i.size})"
            for i in order.items.all()
        )

        row = [
            order.order_number,
            order.created_at.strftime('%Y-%m-%d %H:%M'),
            order.full_name,
            order.phone,
            order.email,
            f"{order.shipping_address} {order.apartment}".strip(),
            order.city,
            order.state,
            order.zip_code,
            'YES' if order.has_feeding_items else 'NO',
            feeding_count,
            non_feeding_count,
            order.items_count,
            items_summary,
            float(order.subtotal),
            float(order.shipping_fee),
            float(order.discount),
            float(order.total_amount),
            order.payment_method.upper(),
            order.payment_status,
            order.order_status,
            order.tracking_number or '',
            order.carrier_name or '',
        ]
        ws.append(row)

    # Format data cells and adjust column widths
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(headers)):
        for cell in row:
            cell.border = thin_border
            cell.alignment = Alignment(vertical='center')

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    buffer.close()
    return excel_bytes
