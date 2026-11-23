from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from .services import generate_invoice_pdf, get_or_create_invoice_for_order


class OrderInvoiceDownloadView(APIView):
    """
    Download Order Invoice PDF for an order.
    GET /api/orders/<order_number>/invoice/
    Allows customer ownership or store staff access.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, order_number):
        if request.user.is_staff:
            order = get_object_or_404(Order, order_number=order_number)
        else:
            order = get_object_or_404(Order, order_number=order_number, user=request.user)

        # Invoices can be downloaded once order is confirmed/paid or COD placed
        if order.payment_status not in ('Paid', 'Pending') and order.order_status == 'Cancelled':
            return Response(
                {'error': "Invoices are not available for cancelled orders."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = get_or_create_invoice_for_order(order)
        # Always generate fresh PDF with latest formatting, images and currency symbols
        pdf_bytes = generate_invoice_pdf(order)
        if invoice:
            try:
                invoice.pdf_file.save(f"invoice_{order.order_number}.pdf", ContentFile(pdf_bytes), save=True)
            except Exception:
                pass

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"order_invoice_{order.order_number}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Invoice-Number'] = invoice.invoice_number if invoice else f"INV-{order.order_number}"
        return response
