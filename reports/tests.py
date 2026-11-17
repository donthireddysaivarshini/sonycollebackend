import io
from decimal import Decimal

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from openpyxl import load_workbook
from rest_framework import status
from rest_framework.test import APIClient

from catalog.models import Category, Color, Product, ProductVariant, SiteConfig, Size
from orders.admin import OrderAdmin
from orders.models import Order, OrderItem
from reports.admin import InvoiceAdmin
from reports.models import Invoice
from reports.services import (
    export_orders_to_excel,
    generate_invoice_pdf,
    get_or_create_invoice_for_order,
)

User = get_user_model()


class ReportsBaseTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='ananya.sharma@example.com',
            first_name='Ananya',
            last_name='Sharma',
            password='TestPassword123!',
        )
        self.other_user = User.objects.create_user(
            email='kavitha.patel@example.com',
            first_name='Kavitha',
            last_name='Patel',
            password='TestPassword123!',
        )

        # Setup catalog fixtures
        self.category = Category.objects.create(name='Kurtis', slug='kurtis')
        self.color = Color.objects.create(name='Royal Indigo', hex_code='#1E3A8A')
        self.size_m = Size.objects.create(name='M', order=2)
        self.size_l = Size.objects.create(name='L', order=3)

        self.product = Product.objects.create(
            title='Nayantara Indigo Kurti',
            slug='nayantara-indigo-kurti',
            category=self.category,
            feeding_config='both',
            price=Decimal('1499.00'),
            mrp=Decimal('2499.00'),
        )
        self.variant_feeding = ProductVariant.objects.create(
            product=self.product,
            clothing_type='Feeding',
            color=self.color,
            size=self.size_m,
            sku='NYN-IND-F-M',
            stock=10,
            reserved_stock=0,
        )
        self.variant_non_feeding = ProductVariant.objects.create(
            product=self.product,
            clothing_type='Non-Feeding',
            color=self.color,
            size=self.size_l,
            sku='NYN-IND-NF-L',
            stock=8,
            reserved_stock=0,
        )

        # Setup SiteConfig
        self.config = SiteConfig.get_solo()
        self.config.gstin = '36AABCS1429B1Z1'
        self.config.registered_address = 'Sony Collections, Kukatpally, Hyderabad, Telangana - 500072'
        self.config.tax_percentage = Decimal('5.00')
        self.config.save()

        # Setup a sample paid order
        self.order = Order.objects.create(
            user=self.user,
            first_name='Ananya',
            last_name='Sharma',
            phone='9876501234',
            email='ananya.sharma@example.com',
            shipping_address='Flat 301, Lakeview Residency',
            apartment='Road No. 4, KPHB',
            city='Hyderabad',
            state='Telangana',
            zip_code='500072',
            subtotal=Decimal('2998.00'),
            shipping_fee=Decimal('0.00'),
            discount=Decimal('0.00'),
            total_amount=Decimal('2998.00'),
            payment_method='razorpay',
            payment_status='Paid',
            order_status='Processing',
            razorpay_payment_id='pay_test_invoice_999',
        )

        self.item1 = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            variant=self.variant_feeding,
            product_name='Nayantara Indigo Kurti',
            product_sku=self.variant_feeding.sku,
            clothing_type='Feeding',
            color='Royal Indigo',
            size='M',
            unit_price=Decimal('1499.00'),
            quantity=1,
            line_total=Decimal('1499.00'),
        )

        self.item2 = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            variant=self.variant_non_feeding,
            product_name='Nayantara Indigo Kurti',
            product_sku=self.variant_non_feeding.sku,
            clothing_type='Non-Feeding',
            color='Royal Indigo',
            size='L',
            unit_price=Decimal('1499.00'),
            quantity=1,
            line_total=Decimal('1499.00'),
        )


class InvoicePDFGenerationTests(ReportsBaseTestCase):
    def test_generate_invoice_pdf_creates_valid_stream(self):
        pdf_bytes = generate_invoice_pdf(self.order)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 1000)
        # PDF magic bytes header
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_get_or_create_invoice_for_order_creates_model_record(self):
        invoice = get_or_create_invoice_for_order(self.order)
        self.assertIsNotNone(invoice.id)
        self.assertEqual(invoice.invoice_number, f"INV-{self.order.order_number}")
        self.assertEqual(invoice.gst_number, '36AABCS1429B1Z1')
        self.assertEqual(invoice.subtotal, Decimal('2998.00'))
        self.assertEqual(invoice.grand_total, Decimal('2998.00'))
        # 5% of 2998 = 149.90
        self.assertEqual(invoice.tax_amount, Decimal('149.90'))
        self.assertTrue(bool(invoice.pdf_file))

        # Idempotency: second call returns existing record without duplicate
        invoice2 = get_or_create_invoice_for_order(self.order)
        self.assertEqual(invoice.id, invoice2.id)
        self.assertEqual(Invoice.objects.filter(order=self.order).count(), 1)


class CustomerInvoiceDownloadAPITests(ReportsBaseTestCase):
    def test_authenticated_owner_can_download_invoice(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_invoice', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn(self.order.order_number, response['Content-Disposition'])
        self.assertEqual(response['X-Invoice-Number'], f"INV-{self.order.order_number}")
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_unauthenticated_request_rejected(self):
        url = reverse('orders:order_invoice', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_customer_cannot_download_invoice(self):
        self.client.force_authenticate(user=self.other_user)
        url = reverse('orders:order_invoice', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancelled_order_invoice_rejected(self):
        self.order.order_status = 'Cancelled'
        self.order.payment_status = 'Failed'
        self.order.save(update_fields=['order_status', 'payment_status'])

        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_invoice', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not available for cancelled orders", response.data['error'])


class ExcelOrderExportTests(ReportsBaseTestCase):
    def test_export_orders_to_excel_structure_and_data(self):
        excel_bytes = export_orders_to_excel(Order.objects.filter(id=self.order.id))
        self.assertIsInstance(excel_bytes, bytes)
        self.assertTrue(len(excel_bytes) > 2000)

        # Load into openpyxl from memory buffer
        wb = load_workbook(filename=io.BytesIO(excel_bytes))
        self.assertIn("Orders Master Report", wb.sheetnames)
        ws = wb["Orders Master Report"]

        # Check headers
        headers = [cell.value for cell in ws[1]]
        self.assertIn('Order Number', headers)
        self.assertIn('Has Feeding Wear', headers)
        self.assertIn('Feeding Garments Count', headers)
        self.assertIn('Non-Feeding Count', headers)
        self.assertIn('Grand Total (INR)', headers)

        # Check data row
        row2 = [cell.value for cell in ws[2]]
        self.assertEqual(row2[0], self.order.order_number)
        self.assertEqual(row2[2], 'Ananya Sharma')
        self.assertEqual(row2[9], 'YES')  # Has feeding items
        self.assertEqual(row2[10], 1)     # Feeding count = 1
        self.assertEqual(row2[11], 1)     # Non-feeding count = 1
        self.assertEqual(row2[12], 2)     # Total items = 2
        self.assertEqual(row2[17], 2998.0) # Grand Total


class AdminInvoiceAndOrderExportActionTests(ReportsBaseTestCase):
    def test_order_admin_export_excel_action(self):
        admin_instance = OrderAdmin(Order, site)
        request = RequestFactory().get('/admin/orders/order/')
        request.user = self.user

        response = admin_instance.export_orders_to_excel_action(
            request,
            Order.objects.filter(id=self.order.id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.xlsx', response['Content-Disposition'])
        self.assertTrue(len(response.content) > 1000)

    def test_invoice_admin_permissions_and_display(self):
        invoice = get_or_create_invoice_for_order(self.order)
        admin_instance = InvoiceAdmin(Invoice, site)
        request = RequestFactory().get('/admin/reports/invoice/')

        self.assertFalse(admin_instance.has_add_permission(request))
        self.assertEqual(admin_instance.order_link(invoice), self.order.order_number)
        self.assertEqual(admin_instance.customer_name(invoice), 'Ananya Sharma')
        self.assertEqual(admin_instance.grand_total_display(invoice), '₹2998.00')
        self.assertIn('Download PDF', admin_instance.download_pdf_link(invoice))
