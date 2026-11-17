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
    Download GST Tax Invoice PDF for a customer order.
    GET /api/orders/<order_number>/invoice/
    Requires customer authentication and ownership of the order.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number, user=request.user)

        # Invoices can be downloaded once order is confirmed/paid or COD placed
        if order.payment_status not in ('Paid', 'Pending') and order.order_status == 'Cancelled':
            return Response(
                {'error': "Invoices are not available for cancelled orders."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice = get_or_create_invoice_for_order(order)
        pdf_bytes = invoice.pdf_file.read() if invoice.pdf_file else generate_invoice_pdf(order)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"tax_invoice_{order.order_number}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Invoice-Number'] = invoice.invoice_number
        return response
