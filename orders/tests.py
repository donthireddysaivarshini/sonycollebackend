from decimal import Decimal
from unittest.mock import patch

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import SavedAddress
from catalog.models import Category, Color, Product, ProductVariant, SiteConfig, Size
from cart.models import Cart, CartItem, StockReservation
from orders.admin import (
    ExchangeRequestAdmin,
    FeedingOrderAdmin,
    NonFeedingOrderAdmin,
    OrderAdmin,
    OrderItemInline,
    ReturnRequestAdmin,
)
from orders.models import (
    ExchangeRequest,
    FeedingOrder,
    NonFeedingOrder,
    Order,
    OrderItem,
    ReturnRequest,
    generate_order_number,
)

User = get_user_model()


class OrdersBaseTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='priya.reddy@example.com',
            first_name='Priya',
            last_name='Reddy',
            password='TestPassword123!',
        )
        self.other_user = User.objects.create_user(
            email='anita.kumar@example.com',
            first_name='Anita',
            last_name='Kumar',
            password='TestPassword123!',
        )

        self.category, _ = Category.objects.get_or_create(
            slug='kurti-dupatta',
            defaults={'name': 'Kurti + Dupatta', 'display_order': 3},
        )
        self.color, _ = Color.objects.get_or_create(
            name='Magenta Rose',
            defaults={'hex_code': '#BE185D'},
        )
        self.size_m, _ = Size.objects.get_or_create(
            name='M',
            defaults={'order': 2},
        )
        self.size_l, _ = Size.objects.get_or_create(
            name='L',
            defaults={'order': 3},
        )

        self.product = Product.objects.create(
            title='Nayantara Magenta Kurti Set',
            slug='nayantara-magenta-kurti-set',
            sku_prefix='SFK-KUR-01',
            category=self.category,
            feeding_config='both',
            price=Decimal('1399.00'),
            mrp=Decimal('2499.00'),
            is_active=True,
        )

        self.variant_feeding = ProductVariant.objects.create(
            product=self.product,
            clothing_type='Feeding',
            color=self.color,
            size=self.size_m,
            sku='SFK-KUR-01-FD-MG-M',
            stock=12,
            reserved_stock=0,
        )

        self.variant_non_feeding = ProductVariant.objects.create(
            product=self.product,
            clothing_type='Non-Feeding',
            color=self.color,
            size=self.size_l,
            sku='SFK-KUR-01-NF-MG-L',
            stock=8,
            reserved_stock=0,
        )

        self.saved_address = SavedAddress.objects.create(
            user=self.user,
            recipient_name='Priya Reddy',
            phone='9876543210',
            address_line1='Flat 402, Sai Balaji Residency',
            address_line2='Shanthi Nagar',
            landmark='Near Care Hospital',
            city='Hyderabad',
            state='Telangana',
            pincode='500028',
            is_default=True,
        )


class OrderNumberGeneratorTests(OrdersBaseTestCase):
    def test_order_number_format_and_uniqueness(self):
        num1 = generate_order_number()
        num2 = generate_order_number()

        # Check prefix
        self.assertTrue(num1.startswith("SFK-"))
        self.assertTrue(num2.startswith("SFK-"))

        # Check year-month format
        yymm = timezone.now().strftime("%y%m")
        self.assertIn(f"SFK-{yymm}-", num1)
        self.assertIn(f"SFK-{yymm}-", num2)

        # Total length: SFK (3) + '-' (1) + YYMM (4) + '-' (1) + XXXX (4) = 13
        self.assertEqual(len(num1), 13)
        self.assertEqual(len(num2), 13)

        # Unique non-sequential check
        self.assertNotEqual(num1, num2)


class ImmutableSnapshotTests(OrdersBaseTestCase):
    def test_order_snapshots_remain_immutable_on_catalog_price_change(self):
        order = Order.objects.create(
            user=self.user,
            first_name='Priya',
            last_name='Reddy',
            phone='9876543210',
            email='priya.reddy@example.com',
            shipping_address='Flat 402, Sai Balaji Residency',
            apartment='Shanthi Nagar',
            city='Hyderabad',
            state='Telangana',
            zip_code='500028',
            subtotal=Decimal('1399.00'),
            total_amount=Decimal('1399.00'),
        )

        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            variant=self.variant_feeding,
            product_name=self.product.title,
            product_sku=self.variant_feeding.sku,
            clothing_type=self.variant_feeding.clothing_type,
            color=self.variant_feeding.color.name,
            size=self.variant_feeding.size.name,
            unit_price=self.variant_feeding.final_price,
            quantity=1,
            line_total=self.variant_feeding.final_price,
        )

        # Verify initial snapshot
        self.assertEqual(item.unit_price, Decimal('1399.00'))
        self.assertEqual(item.product_name, 'Nayantara Magenta Kurti Set')

        # Now mutate parent catalog Product and Variant
        self.product.price = Decimal('1999.00')
        self.product.title = 'Nayantara Brand New Title'
        self.product.save()

        self.variant_feeding.price_override = Decimal('2299.00')
        self.variant_feeding.save()

        # Reload order item from database
        item.refresh_from_db()

        # Immutable snapshot values MUST NOT change
        self.assertEqual(item.unit_price, Decimal('1399.00'))
        self.assertEqual(item.product_name, 'Nayantara Magenta Kurti Set')
        self.assertEqual(item.line_total, Decimal('1399.00'))


class ProxyModelSegmentationTests(OrdersBaseTestCase):
    def setUp(self):
        super().setUp()

        # 1. Feeding-only Order
        self.order_feeding = Order.objects.create(
            user=self.user,
            first_name='Priya',
            phone='9876543210',
            email='priya@example.com',
            shipping_address='Street 1',
            city='Hyderabad',
            state='Telangana',
            zip_code='500001',
            subtotal=Decimal('1399.00'),
            total_amount=Decimal('1399.00'),
        )
        OrderItem.objects.create(
            order=self.order_feeding,
            product=self.product,
            variant=self.variant_feeding,
            product_name=self.product.title,
            product_sku=self.variant_feeding.sku,
            clothing_type='Feeding',
            color='Magenta',
            size='M',
            unit_price=Decimal('1399.00'),
            quantity=1,
            line_total=Decimal('1399.00'),
        )

        # 2. Non-Feeding-only Order
        self.order_non_feeding = Order.objects.create(
            user=self.user,
            first_name='Priya',
            phone='9876543210',
            email='priya@example.com',
            shipping_address='Street 2',
            city='Hyderabad',
            state='Telangana',
            zip_code='500001',
            subtotal=Decimal('1399.00'),
            total_amount=Decimal('1399.00'),
        )
        OrderItem.objects.create(
            order=self.order_non_feeding,
            product=self.product,
            variant=self.variant_non_feeding,
            product_name=self.product.title,
            product_sku=self.variant_non_feeding.sku,
            clothing_type='Non-Feeding',
            color='Magenta',
            size='L',
            unit_price=Decimal('1399.00'),
            quantity=1,
            line_total=Decimal('1399.00'),
        )

        # 3. Mixed Order containing BOTH Feeding and Non-Feeding items
        self.order_mixed = Order.objects.create(
            user=self.user,
            first_name='Priya',
            phone='9876543210',
            email='priya@example.com',
            shipping_address='Street 3',
            city='Hyderabad',
            state='Telangana',
            zip_code='500001',
            subtotal=Decimal('2798.00'),
            total_amount=Decimal('2798.00'),
        )
        OrderItem.objects.create(
            order=self.order_mixed,
            product=self.product,
            variant=self.variant_feeding,
            product_name=self.product.title,
            product_sku=self.variant_feeding.sku,
            clothing_type='Feeding',
            color='Magenta',
            size='M',
            unit_price=Decimal('1399.00'),
            quantity=1,
            line_total=Decimal('1399.00'),
        )
        OrderItem.objects.create(
            order=self.order_mixed,
            product=self.product,
            variant=self.variant_non_feeding,
            product_name=self.product.title,
            product_sku=self.variant_non_feeding.sku,
            clothing_type='Non-Feeding',
            color='Magenta',
            size='L',
            unit_price=Decimal('1399.00'),
            quantity=1,
            line_total=Decimal('1399.00'),
        )

    def test_queryset_segmentation_without_database_duplication(self):
        # Database has exactly 3 orders
        self.assertEqual(Order.objects.count(), 3)

        # Feeding orders queryset contains order_feeding and order_mixed (2 orders)
        feeding_orders = FeedingOrder.objects.all()
        self.assertEqual(feeding_orders.count(), 2)
        self.assertIn(self.order_feeding, feeding_orders)
        self.assertIn(self.order_mixed, feeding_orders)
        self.assertNotIn(self.order_non_feeding, feeding_orders)

        # Non-feeding orders queryset contains order_non_feeding and order_mixed (2 orders)
        non_feeding_orders = NonFeedingOrder.objects.all()
        self.assertEqual(non_feeding_orders.count(), 2)
        self.assertIn(self.order_non_feeding, non_feeding_orders)
        self.assertIn(self.order_mixed, non_feeding_orders)
        self.assertNotIn(self.order_feeding, non_feeding_orders)

    def test_admin_change_form_retains_all_items_with_badges(self):
        inline = OrderItemInline(Order, site)
        feeding_item = self.order_mixed.items.filter(clothing_type='Feeding').first()
        non_feeding_item = self.order_mixed.items.filter(clothing_type='Non-Feeding').first()

        # Both items are visible in order_mixed
        self.assertEqual(self.order_mixed.items.count(), 2)

        # Badge verification
        feeding_badge = inline.clothing_type_badge(feeding_item)
        self.assertIn('#EC4899', feeding_badge)
        self.assertIn('Feeding', feeding_badge)

        non_feeding_badge = inline.clothing_type_badge(non_feeding_item)
        self.assertIn('#3B82F6', non_feeding_badge)
        self.assertIn('Non-Feeding', non_feeding_badge)


class OrderAPITests(OrdersBaseTestCase):
    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            user=self.user,
            first_name='Priya',
            last_name='Reddy',
            phone='9876543210',
            email='priya.reddy@example.com',
            shipping_address='Flat 402, Sai Balaji Residency',
            apartment='Shanthi Nagar',
            city='Hyderabad',
            state='Telangana',
            zip_code='500028',
            subtotal=Decimal('1399.00'),
            total_amount=Decimal('1399.00'),
            order_status='Ordered',
            payment_status='Paid',
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            variant=self.variant_feeding,
            product_name='Nayantara Magenta Kurti Set',
            product_sku=self.variant_feeding.sku,
            clothing_type='Feeding',
            color='Magenta Rose',
            size='M',
            unit_price=Decimal('1399.00'),
            quantity=1,
            line_total=Decimal('1399.00'),
        )

    def test_list_orders_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('orders:order_list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['order_number'], self.order.order_number)
        self.assertEqual(response.data[0]['total_amount'], '1399.00')
        self.assertEqual(len(response.data[0]['items']), 1)
        self.assertEqual(response.data[0]['items'][0]['clothing_type'], 'Feeding')

    def test_list_orders_unauthenticated_rejected(self):
        response = self.client.get(reverse('orders:order_list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_order_detail_owner_success(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_detail', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['order_number'], self.order.order_number)
        self.assertTrue(response.data['is_cancellable'])

    def test_get_order_detail_other_user_forbidden(self):
        self.client.force_authenticate(user=self.other_user)
        url = reverse('orders:order_detail', kwargs={'order_number': self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_order_success(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_cancel', kwargs={'order_number': self.order.order_number})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['order_status'], 'Cancelled')

        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'Cancelled')

    def test_cancel_order_after_shipped_rejected(self):
        self.order.order_status = 'Shipped'
        self.order.save(update_fields=['order_status'])

        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_cancel', kwargs={'order_number': self.order.order_number})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already shipped", response.data['error'])

    def test_order_creation_from_cart(self):
        # Setup cart with item
        self.client.force_authenticate(user=self.user)
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant_feeding, quantity=2)

        payload = {'address_id': self.saved_address.id, 'payment_method': 'cod'}
        response = self.client.post(reverse('orders:order_create'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['subtotal'], '2798.00')
        self.assertEqual(response.data['total_amount'], '2798.00')
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['quantity'], 2)

        # Cart is cleared after order creation
        self.assertEqual(cart.items.count(), 0)


class ConcurrencyAndInventoryRaceConditionTests(OrdersBaseTestCase):
    """
    Inventory protection tests verifying atomic stock reservation
    and zero overselling under race conditions.
    """

    def test_concurrent_checkout_of_last_unit_rejects_second_buyer(self):
        # Set physical stock to exactly 1 unit
        self.variant_feeding.stock = 1
        self.variant_feeding.reserved_stock = 0
        self.variant_feeding.save(update_fields=['stock', 'reserved_stock'])

        user2 = User.objects.create_user(
            email='concurrent.buyer@example.com',
            first_name='Concurrent',
            last_name='Buyer',
            password='TestPassword123!',
        )
        saved_address2 = SavedAddress.objects.create(
            user=user2,
            recipient_name='Concurrent Buyer',
            phone='9876543219',
            address_line1='Street 2',
            city='Hyderabad',
            state='Telangana',
            pincode='500002',
            is_default=True,
        )

        client1 = APIClient()
        client1.force_authenticate(user=self.user)
        payload1 = {
            'items': [{'variant_id': self.variant_feeding.id, 'quantity': 1}],
            'address_id': self.saved_address.id,
            'payment_method': 'razorpay',
        }

        client2 = APIClient()
        client2.force_authenticate(user=user2)
        payload2 = {
            'items': [{'variant_id': self.variant_feeding.id, 'quantity': 1}],
            'address_id': saved_address2.id,
            'payment_method': 'razorpay',
        }

        # First buyer acquires the last physical unit
        res1 = client1.post(reverse('orders:order_checkout'), payload1, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertIn('order_number', res1.data)

        # Second buyer attempts to checkout the exact same variant
        res2 = client2.post(reverse('orders:order_checkout'), payload2, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', res2.data)
        self.assertIn('available for selected variant', str(res2.data['error']))

        # Verify database inventory invariants: exactly 1 unit reserved, 0 available. Zero overselling!
        self.variant_feeding.refresh_from_db()
        self.assertEqual(self.variant_feeding.stock, 1)
        self.assertEqual(self.variant_feeding.reserved_stock, 1)
        self.assertEqual(self.variant_feeding.available_stock, 0)

        # Direct attempt to reserve more stock via StockReservation also fails atomically
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            StockReservation.create_reservation(variant=self.variant_feeding, quantity=1, user=user2)


class OrderCancellationInventoryRestorationTests(OrdersBaseTestCase):
    @patch('payments.razorpay_client.dispatch_razorpay_refund', return_value={'id': 'rfnd_test_cancel', 'status': 'processed'})
    def test_paid_order_cancellation_restores_physical_stock_and_triggers_refund(self, mock_refund):
        # Create paid order with 2 units
        self.variant_feeding.stock = 8  # was 10, 2 were purchased
        self.variant_feeding.reserved_stock = 0
        self.variant_feeding.save(update_fields=['stock', 'reserved_stock'])

        order = Order.objects.create(
            user=self.user,
            first_name='Priya',
            phone='9876543210',
            email='priya@example.com',
            shipping_address='Flat 402',
            city='Hyderabad',
            state='Telangana',
            zip_code='500028',
            subtotal=Decimal('2798.00'),
            total_amount=Decimal('2798.00'),
            order_status='Ordered',
            payment_status='Paid',
            razorpay_payment_id='pay_cancel_restore_99',
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            variant=self.variant_feeding,
            product_name=self.product.title,
            product_sku=self.variant_feeding.sku,
            clothing_type='Feeding',
            color='Magenta',
            size='M',
            unit_price=Decimal('1399.00'),
            quantity=2,
            line_total=Decimal('2798.00'),
        )

        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_cancel', kwargs={'order_number': order.order_number})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['order_status'], 'Cancelled')
        self.assertEqual(response.data['payment_status'], 'Refunded')

        # Physical stock incremented atomically back to 10 (8 + 2)
        self.variant_feeding.refresh_from_db()
        self.assertEqual(self.variant_feeding.stock, 10)

        # Refund record created
        from payments.models import RefundRecord
        refund = RefundRecord.objects.filter(order=order).first()
        self.assertIsNotNone(refund)
        self.assertEqual(refund.amount, Decimal('2798.00'))
        self.assertEqual(refund.status, RefundRecord.STATUS_PROCESSED)

    def test_admin_fulfillment_actions_and_tracking_assignment(self):
        from django.contrib.messages.storage.fallback import FallbackStorage

        order = Order.objects.create(
            user=self.user,
            first_name='Priya',
            phone='9876543210',
            email='priya@example.com',
            shipping_address='Flat 402',
            city='Hyderabad',
            state='Telangana',
            zip_code='500028',
            subtotal=Decimal('1399.00'),
            total_amount=Decimal('1399.00'),
            order_status='Ordered',
            payment_status='Paid',
        )

        admin_instance = OrderAdmin(Order, site)
        request = RequestFactory().get('/admin/orders/order/')
        request.user = self.user
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        # 1. Transition to Processing
        admin_instance.mark_as_processing(request, Order.objects.filter(id=order.id))
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'Processing')

        # 2. Assign tracking and transition to Shipped
        order.tracking_number = 'BLUEDART-987654'
        order.carrier_name = 'BlueDart Express'
        order.save(update_fields=['tracking_number', 'carrier_name'])

        admin_instance.mark_as_shipped(request, Order.objects.filter(id=order.id))
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'Shipped')

        # 3. Transition to Delivered
        admin_instance.mark_as_delivered(request, Order.objects.filter(id=order.id))
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'Delivered')


class ReturnAndExchangeWorkflowTests(OrdersBaseTestCase):
    def setUp(self):
        super().setUp()
        from datetime import timedelta

        # Delivered Order with 1 item
        self.delivered_order = Order.objects.create(
            user=self.user,
            first_name='Priya',
            phone='9876543210',
            email='priya@example.com',
            shipping_address='Flat 402',
            city='Hyderabad',
            state='Telangana',
            zip_code='500028',
            subtotal=Decimal('1399.00'),
            total_amount=Decimal('1399.00'),
            order_status='Delivered',
            payment_status='Paid',
            razorpay_payment_id='pay_delivered_return_123',
        )
        self.order_item = OrderItem.objects.create(
            order=self.delivered_order,
            product=self.product,
            variant=self.variant_feeding,
            product_name=self.product.title,
            product_sku=self.variant_feeding.sku,
            clothing_type='Feeding',
            color='Magenta',
            size='M',
            unit_price=Decimal('1399.00'),
            quantity=1,
            line_total=Decimal('1399.00'),
        )

        # Replacement variant for exchanges (e.g. Size L)
        self.replacement_variant = self.variant_non_feeding
        self.replacement_variant.stock = 5
        self.replacement_variant.reserved_stock = 0
        self.replacement_variant.save(update_fields=['stock', 'reserved_stock'])

        # Reset SiteConfig
        self.config = SiteConfig.get_solo()
        self.config.return_window_days = 7
        self.config.exchange_window_days = 7
        self.config.save()

    def test_return_rejected_if_order_not_delivered(self):
        self.delivered_order.order_status = 'Shipped'
        self.delivered_order.save(update_fields=['order_status'])

        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_returns', kwargs={'order_number': self.delivered_order.order_number})
        payload = {'item_id': self.order_item.id, 'reason': 'defective'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("only be requested for orders that have been delivered", response.data['error'])

    def test_return_rejected_if_window_expired(self):
        from datetime import timedelta
        # Simulate delivery 10 days ago (window is 7 days)
        past_time = timezone.now() - timedelta(days=10)
        Order.objects.filter(id=self.delivered_order.id).update(updated_at=past_time)

        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_returns', kwargs={'order_number': self.delivered_order.order_number})
        payload = {'item_id': self.order_item.id, 'reason': 'defective'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", response.data['error'])

    def test_return_success_and_duplicate_rejection(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_returns', kwargs={'order_number': self.delivered_order.order_number})
        payload = {
            'item_id': self.order_item.id,
            'reason': 'defective',
            'customer_notes': 'Stitching damaged near zipper',
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'Requested')
        self.assertEqual(response.data['product_name'], self.product.title)

        # Duplicate submission for the same item must be rejected
        dup_res = self.client.post(url, payload, format='json')
        self.assertEqual(dup_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("active return request already exists", dup_res.data['error'])

    def test_exchange_requires_proof_file(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_exchanges', kwargs={'order_number': self.delivered_order.order_number})
        payload = {
            'item_id': self.order_item.id,
            'reason': 'damaged',
        }
        response = self.client.post(url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("photo or unboxing video", response.data['error'])

    def test_exchange_success_with_proof(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_authenticate(user=self.user)
        url = reverse('orders:order_exchanges', kwargs={'order_number': self.delivered_order.order_number})
        proof = SimpleUploadedFile("damage.jpg", b"image_data_here", content_type="image/jpeg")
        payload = {
            'item_id': self.order_item.id,
            'reason': 'damaged',
            'customer_notes': 'Garment seam torn upon opening',
            'proof_file': proof,
        }
        response = self.client.post(url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'Requested')
        self.assertIsNotNone(response.data['proof_file_url'])

    @patch('payments.razorpay_client.dispatch_razorpay_refund', return_value={'id': 'rfnd_test_return', 'status': 'processed'})
    def test_admin_return_approval_and_item_receipt_with_stock_restoration(self, mock_refund):
        from django.contrib.messages.storage.fallback import FallbackStorage

        # Initial physical stock before return
        self.variant_feeding.stock = 10
        self.variant_feeding.save(update_fields=['stock'])

        return_req = ReturnRequest.objects.create(
            order=self.delivered_order,
            item=self.order_item,
            user=self.user,
            reason='quality',
            status=ReturnRequest.STATUS_REQUESTED,
        )

        admin_instance = ReturnRequestAdmin(ReturnRequest, site)
        request = RequestFactory().get('/admin/orders/returnrequest/')
        request.user = self.user
        setattr(request, 'session', 'session')
        setattr(request, '_messages', FallbackStorage(request))

        # 1. Admin approves return
        admin_instance.approve_returns(request, ReturnRequest.objects.filter(id=return_req.id))
        return_req.refresh_from_db()
        self.assertEqual(return_req.status, ReturnRequest.STATUS_APPROVED)

        # 2. Item received in warehouse: restores stock & triggers refund
        admin_instance.mark_item_received_and_refund(request, ReturnRequest.objects.filter(id=return_req.id))
        return_req.refresh_from_db()
        self.assertEqual(return_req.status, ReturnRequest.STATUS_REFUNDED)

        # Physical stock incremented by 1 (10 + 1 = 11)
        self.variant_feeding.refresh_from_db()
        self.assertEqual(self.variant_feeding.stock, 11)

        # Refund record created
        from payments.models import RefundRecord
        refund = RefundRecord.objects.filter(order=self.delivered_order).first()
        self.assertIsNotNone(refund)
        self.assertEqual(refund.amount, Decimal('1399.00'))
        self.assertEqual(refund.status, RefundRecord.STATUS_PROCESSED)

    def test_admin_exchange_approval_and_voucher_generation(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.core.files.uploadedfile import SimpleUploadedFile

        proof = SimpleUploadedFile("damage_admin.jpg", b"image_data_here", content_type="image/jpeg")
        exchange_req = ExchangeRequest.objects.create(
            order=self.delivered_order,
            item=self.order_item,
            user=self.user,
            reason='damaged',
            proof_file=proof,
            status=ExchangeRequest.STATUS_REQUESTED,
        )

        admin_instance = ExchangeRequestAdmin(ExchangeRequest, site)
        request = RequestFactory().get('/admin/orders/exchangerequest/')
        request.user = self.user
        setattr(request, 'session', 'session')
        setattr(request, '_messages', FallbackStorage(request))

        # Admin approves exchange: generates single-use exchange coupon
        admin_instance.approve_exchanges(request, ExchangeRequest.objects.filter(id=exchange_req.id))
        exchange_req.refresh_from_db()
        self.assertEqual(exchange_req.status, ExchangeRequest.STATUS_APPROVED)
        self.assertTrue(exchange_req.exchange_code.startswith('EXC-'))

        from orders.models import Coupon
        voucher = Coupon.objects.get(code=exchange_req.exchange_code)
        self.assertEqual(voucher.value, self.order_item.line_total)
        self.assertTrue(voucher.is_exchange_code)
        self.assertEqual(voucher.usage_limit, 1)


class CouponAndExchangeValidationTests(OrdersBaseTestCase):
    def setUp(self):
        super().setUp()
        from datetime import timedelta
        from orders.models import Coupon
        now = timezone.now()
        self.coupon_pct = Coupon.objects.create(
            code='TEST10',
            discount_type='percentage',
            value=Decimal('10.00'),
            min_order_value=Decimal('1000.00'),
            valid_from=now - timedelta(days=1),
            valid_to=now + timedelta(days=30),
            active=True,
            usage_limit=100,
        )
        self.exchange_code = Coupon.objects.create(
            code='EXCH500',
            discount_type='fixed',
            value=Decimal('500.00'),
            min_order_value=Decimal('500.00'),
            valid_from=now - timedelta(days=1),
            valid_to=now + timedelta(days=30),
            active=True,
            is_exchange_code=True,
            usage_limit=5,
        )

    def test_coupon_validate_api_success(self):
        url = reverse('orders:coupon_validate')
        res = self.client.post(url, {'code': 'test10', 'order_total': 1800}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['valid'])
        self.assertEqual(res.data['code'], 'TEST10')
        self.assertEqual(res.data['discount'], 180.0)

    def test_coupon_validate_min_order_restriction(self):
        url = reverse('orders:coupon_validate')
        res = self.client.post(url, {'code': 'TEST10', 'order_total': 500}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Minimum order value', str(res.data['error']))

    def test_coupon_applied_during_checkout(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            'items': [{'variant_id': self.variant_feeding.id, 'quantity': 1}],
            'address_id': self.saved_address.id,
            'payment_method': 'razorpay',
            'coupon_code': 'TEST10',
        }
        res = self.client.post(reverse('orders:order_checkout'), payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(order_number=res.data['order_number'])
        self.assertEqual(order.coupon_code, 'TEST10')
        # subtotal is 1399.00 -> 10% is 139.90 -> shipping is 99.00 -> total is 1358.10
        self.assertEqual(order.discount, Decimal('139.90'))
        self.assertEqual(order.shipping_fee, Decimal('99.00'))
        self.assertEqual(order.total_amount, Decimal('1358.10'))
        self.coupon_pct.refresh_from_db()
        self.assertEqual(self.coupon_pct.uses_count, 1)




