from decimal import Decimal

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import SavedAddress
from catalog.models import Category, Color, Product, ProductVariant, Size
from cart.models import Cart, CartItem
from orders.admin import FeedingOrderAdmin, NonFeedingOrderAdmin, OrderAdmin, OrderItemInline
from orders.models import FeedingOrder, NonFeedingOrder, Order, OrderItem, generate_order_number

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

