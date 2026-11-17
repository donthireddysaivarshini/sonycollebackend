from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import SavedAddress
from catalog.models import Category, Color, Product, ProductVariant, Size
from cart.models import Cart, CartItem, StockReservation

User = get_user_model()


class CartBaseTestCase(TestCase):
    """
    Base test fixture creating test catalog products, variants, and users.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email='customer@example.com',
            first_name='Priya',
            last_name='Sharma',
            password='TestPassword123!',
        )
        self.client = APIClient()

        # Retrieve or create test category
        self.category, _ = Category.objects.get_or_create(
            slug='frocks',
            defaults={'name': 'Frocks', 'display_order': 1},
        )
        self.color, _ = Color.objects.get_or_create(
            name='Crimson Red',
            defaults={'hex_code': '#DC2626'},
        )
        self.size_m, _ = Size.objects.get_or_create(
            name='M',
            defaults={'order': 2},
        )
        self.size_l, _ = Size.objects.get_or_create(
            name='L',
            defaults={'order': 3},
        )

        # Create active test product
        self.product = Product.objects.create(
            title='Nayantara Rose Flared Maxi Kurti',
            slug='nayantara-rose-flared-maxi-kurti',
            sku_prefix='SFK-NAY',
            category=self.category,
            feeding_config='both',
            price=Decimal('1499.00'),
            mrp=Decimal('1999.00'),
            is_active=True,
        )

        # Create variant with stock=10
        self.variant = ProductVariant.objects.create(
            product=self.product,
            clothing_type='Feeding',
            color=self.color,
            size=self.size_m,
            sku='SFK-NAY-FD-RD-M',
            stock=10,
            reserved_stock=0,
        )

        # Create second variant with stock=2
        self.variant_limited = ProductVariant.objects.create(
            product=self.product,
            clothing_type='Non-Feeding',
            color=self.color,
            size=self.size_l,
            sku='SFK-NAY-NF-RD-L',
            stock=2,
            reserved_stock=0,
            price_override=Decimal('1599.00'),
        )


class CartModelTests(CartBaseTestCase):
    def test_cart_creation_guest_and_user(self):
        guest_cart = Cart.objects.create(session_key='session-abc-123')
        self.assertIsNone(guest_cart.user)
        self.assertEqual(guest_cart.items_count, 0)
        self.assertEqual(guest_cart.subtotal, Decimal('0.00'))

        user_cart = Cart.objects.create(user=self.user)
        self.assertEqual(user_cart.user, self.user)

    def test_cart_item_financial_properties(self):
        cart = Cart.objects.create(user=self.user)
        item1 = CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)
        item2 = CartItem.objects.create(cart=cart, variant=self.variant_limited, quantity=1)

        # Unit price authoritative from variant final_price
        self.assertEqual(item1.unit_price, Decimal('1499.00'))
        self.assertEqual(item1.line_total, Decimal('2998.00'))

        self.assertEqual(item2.unit_price, Decimal('1599.00'))
        self.assertEqual(item2.line_total, Decimal('1599.00'))

        # Cart totals
        self.assertEqual(cart.items_count, 3)
        self.assertEqual(cart.subtotal, Decimal('4597.00'))
        self.assertEqual(cart.grand_total, Decimal('4597.00'))

    def test_cart_item_unique_constraint(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)
        with self.assertRaises(IntegrityError):
            CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)

    def test_cart_clear(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)
        self.assertEqual(cart.items.count(), 1)
        cart.clear()
        self.assertEqual(cart.items.count(), 0)


class StockReservationModelTests(CartBaseTestCase):
    def test_create_reservation_and_available_stock(self):
        self.assertEqual(self.variant.available_stock, 10)
        reservation = StockReservation.create_reservation(
            variant=self.variant,
            quantity=3,
            user=self.user,
            ttl_minutes=15,
        )
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.reserved_stock, 3)
        self.assertEqual(self.variant.available_stock, 7)
        self.assertEqual(reservation.status, StockReservation.STATUS_ACTIVE)

    def test_create_reservation_exceeding_stock_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            StockReservation.create_reservation(
                variant=self.variant_limited,
                quantity=5,  # stock is only 2
                user=self.user,
            )
        self.variant_limited.refresh_from_db()
        self.assertEqual(self.variant_limited.reserved_stock, 0)

    def test_reservation_release(self):
        reservation = StockReservation.create_reservation(
            variant=self.variant,
            quantity=4,
            user=self.user,
        )
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.available_stock, 6)

        reservation.release()
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.reserved_stock, 0)
        self.assertEqual(self.variant.available_stock, 10)
        self.assertEqual(reservation.status, StockReservation.STATUS_RELEASED)

    def test_reservation_expire(self):
        reservation = StockReservation.create_reservation(
            variant=self.variant,
            quantity=2,
            user=self.user,
        )
        reservation.expire()
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.reserved_stock, 0)
        self.assertEqual(self.variant.available_stock, 10)
        self.assertEqual(reservation.status, StockReservation.STATUS_EXPIRED)

    def test_reservation_convert_to_sale(self):
        reservation = StockReservation.create_reservation(
            variant=self.variant,
            quantity=3,
            user=self.user,
        )
        reservation.convert_to_sale()
        self.variant.refresh_from_db()
        # Physical stock decremented from 10 to 7, reserved_stock decremented from 3 to 0
        self.assertEqual(self.variant.stock, 7)
        self.assertEqual(self.variant.reserved_stock, 0)
        self.assertEqual(self.variant.available_stock, 7)
        self.assertEqual(reservation.status, StockReservation.STATUS_CONVERTED)

    def test_lazy_and_periodic_expiration(self):
        # Create an expired reservation
        res = StockReservation.objects.create(
            variant=self.variant,
            quantity=3,
            expires_at=timezone.now() - timedelta(minutes=5),
            status=StockReservation.STATUS_ACTIVE,
        )
        # Manually bump reserved_stock as create_reservation would
        self.variant.reserved_stock = 3
        self.variant.save(update_fields=['reserved_stock'])

        # Run expiration
        count = StockReservation.expire_stale_reservations()
        self.assertEqual(count, 1)

        res.refresh_from_db()
        self.assertEqual(res.status, StockReservation.STATUS_EXPIRED)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.reserved_stock, 0)


class CartAPITests(CartBaseTestCase):
    def test_get_cart_guest_returns_session_key(self):
        response = self.client.get(reverse('cart:cart_detail'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('X-Session-Key', response.headers)
        self.assertEqual(response.data['items_count'], 0)
        self.assertEqual(response.data['subtotal'], '0.00')

    def test_get_cart_authenticated_user(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('cart:cart_detail'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['items_count'], 0)

    def test_add_item_to_cart_and_price_tampering_immunity(self):
        self.client.force_authenticate(user=self.user)
        # Malicious payload trying to inject price 1.00
        payload = {
            'variant_id': self.variant.id,
            'quantity': 2,
            'price': '1.00',
            'unit_price': '1.00',
        }
        response = self.client.post(reverse('cart:cart_item_create'), payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['items_count'], 2)
        # Must strictly equal 1499.00 * 2 = 2998.00
        self.assertEqual(response.data['subtotal'], '2998.00')
        self.assertEqual(response.data['items'][0]['unit_price'], '1499.00')

    def test_add_item_increments_existing_quantity(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('cart:cart_item_create'), {'variant_id': self.variant.id, 'quantity': 1})
        response = self.client.post(reverse('cart:cart_item_create'), {'variant_id': self.variant.id, 'quantity': 2})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['items_count'], 3)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['quantity'], 3)

    def test_add_item_exceeding_stock_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse('cart:cart_item_create'),
            {'variant_id': self.variant_limited.id, 'quantity': 5},  # only 2 available
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', response.data)

    def test_update_item_quantity(self):
        self.client.force_authenticate(user=self.user)
        add_res = self.client.post(reverse('cart:cart_item_create'), {'variant_id': self.variant.id, 'quantity': 1})
        item_id = add_res.data['items'][0]['id']

        # Update quantity to 4
        patch_res = self.client.patch(
            reverse('cart:cart_item_detail', kwargs={'item_id': item_id}),
            {'quantity': 4},
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['items_count'], 4)
        self.assertEqual(patch_res.data['subtotal'], '5996.00')

    def test_remove_item_from_cart(self):
        self.client.force_authenticate(user=self.user)
        add_res = self.client.post(reverse('cart:cart_item_create'), {'variant_id': self.variant.id, 'quantity': 2})
        item_id = add_res.data['items'][0]['id']

        del_res = self.client.delete(reverse('cart:cart_item_detail', kwargs={'item_id': item_id}))
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)
        self.assertEqual(del_res.data['items_count'], 0)

    def test_clear_cart(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('cart:cart_item_create'), {'variant_id': self.variant.id, 'quantity': 1})
        self.client.post(reverse('cart:cart_item_create'), {'variant_id': self.variant_limited.id, 'quantity': 1})

        clear_res = self.client.post(reverse('cart:cart_clear'))
        self.assertEqual(clear_res.status_code, status.HTTP_200_OK)
        self.assertEqual(clear_res.data['items_count'], 0)
        self.assertEqual(len(clear_res.data['items']), 0)

    def test_merge_guest_cart_into_user_cart(self):
        # 1. Create a guest cart with session key
        session_key = 'test-guest-session-uuid-99'
        client_guest = APIClient()
        client_guest.post(
            reverse('cart:cart_item_create'),
            {'variant_id': self.variant.id, 'quantity': 2},
            HTTP_X_SESSION_KEY=session_key,
        )

        # 2. Authenticated user already has 1 of the same item in their cart
        user_cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=user_cart, variant=self.variant, quantity=1)

        # 3. Call merge endpoint
        self.client.force_authenticate(user=self.user)
        merge_res = self.client.post(reverse('cart:cart_merge'), {'session_key': session_key})
        self.assertEqual(merge_res.status_code, status.HTTP_200_OK)
        # Quantity merged: 1 + 2 = 3
        self.assertEqual(merge_res.data['items_count'], 3)
        self.assertEqual(len(merge_res.data['items']), 1)
        self.assertEqual(merge_res.data['items'][0]['quantity'], 3)

        # Guest cart deleted
        self.assertFalse(Cart.objects.filter(session_key=session_key).exists())


class CartValidateAPITests(CartBaseTestCase):
    def test_validate_in_stock_success(self):
        payload = {
            'items': [
                {'variant_id': self.variant.id, 'quantity': 2},
                {'variant_id': self.variant_limited.id, 'quantity': 1},
            ]
        }
        response = self.client.post(reverse('cart:cart_validate'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_valid'])
        # 2 * 1499.00 + 1 * 1599.00 = 4597.00
        self.assertEqual(response.data['subtotal'], '4597.00')
        self.assertEqual(response.data['shipping_fee'], '0.00')
        self.assertEqual(response.data['total'], '4597.00')
        self.assertEqual(len(response.data['items']), 2)

    def test_validate_out_of_stock_failure(self):
        payload = {
            'items': [
                {'variant_id': self.variant_limited.id, 'quantity': 5},  # only 2 available
            ]
        }
        response = self.client.post(reverse('cart:cart_validate'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['is_valid'])
        self.assertEqual(len(response.data['errors']), 1)
        self.assertIn("Only 2 unit(s) available", response.data['errors'][0]['error'])


class CheckoutSummaryAPITests(CartBaseTestCase):
    def setUp(self):
        super().setUp()
        self.address = SavedAddress.objects.create(
            user=self.user,
            recipient_name='Priya Sharma',
            phone='9876543210',
            address_line1='Flat 402, Sai Balaji Residency',
            address_line2='Shanthi Nagar',
            landmark='Near Care Hospital',
            city='Hyderabad',
            state='Telangana',
            pincode='500028',
            is_default=True,
        )

    def test_checkout_summary_with_saved_address(self):
        self.client.force_authenticate(user=self.user)
        # Add item to user cart
        self.client.post(reverse('cart:cart_item_create'), {'variant_id': self.variant.id, 'quantity': 2})

        payload = {'address_id': self.address.id}
        response = self.client.post(reverse('cart:cart_checkout_summary'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subtotal'], '2998.00')
        self.assertEqual(response.data['grand_total'], '2998.00')
        self.assertEqual(response.data['items_count'], 2)
        self.assertEqual(response.data['delivery_address']['pincode'], '500028')

    def test_checkout_summary_with_inline_address(self):
        payload = {
            'items': [{'variant_id': self.variant.id, 'quantity': 1}],
            'address': {
                'fullName': 'Aarti Reddy',
                'phone': '9123456780',
                'houseFlat': 'Plot 12, Road No 5',
                'streetArea': 'Jubilee Hills',
                'city': 'Hyderabad',
                'state': 'Telangana',
                'pincode': '500033',
            },
        }
        response = self.client.post(reverse('cart:cart_checkout_summary'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subtotal'], '1499.00')
        self.assertEqual(response.data['delivery_address']['city'], 'Hyderabad')

    def test_checkout_summary_empty_cart_rejection(self):
        self.client.force_authenticate(user=self.user)
        payload = {'address_id': self.address.id}
        response = self.client.post(reverse('cart:cart_checkout_summary'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cart is empty", response.data['error'].lower())


class ExpireReservationsCommandTest(CartBaseTestCase):
    def test_command_releases_stale_holds(self):
        # Create an expired reservation
        StockReservation.objects.create(
            variant=self.variant,
            quantity=2,
            expires_at=timezone.now() - timedelta(minutes=10),
            status=StockReservation.STATUS_ACTIVE,
        )
        self.variant.reserved_stock = 2
        self.variant.save(update_fields=['reserved_stock'])

        call_command('expire_reservations')

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.reserved_stock, 0)

