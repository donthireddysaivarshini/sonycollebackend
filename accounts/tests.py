from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SavedAddress

User = get_user_model()


class CustomUserModelTests(TestCase):
    """
    Test suite for CustomUser model and CustomUserManager.
    Verifies normalized email login, removal of username, superuser validation,
    and case-insensitive email uniqueness.
    """

    def setUp(self):
        self.client = APIClient()

    def test_create_user_successful(self):
        """User creation normalizes email to lowercase, hashes password, and has no username."""
        email = "TEST.USER@Example.COM"
        password = "SecurePassword123!"
        user = User.objects.create_user(email=email, password=password)

        self.assertEqual(user.email, "test.user@example.com")
        self.assertTrue(user.check_password(password))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNone(getattr(user, 'username', None))

    def test_create_user_without_email_raises_error(self):
        """Attempting to create a user without an email raises ValueError."""
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="password123")

    def test_create_superuser_successful(self):
        """Superuser creation sets is_staff=True and is_superuser=True."""
        email = "admin@sonyfeedingkurtis.com"
        password = "AdminPassword123!"
        admin_user = User.objects.create_superuser(email=email, password=password)

        self.assertEqual(admin_user.email, email)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_active)

    def test_create_superuser_invalid_staff_flag_raises_error(self):
        """Superuser creation with is_staff=False raises ValueError."""
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                email="bad_admin@example.com",
                password="password123",
                is_staff=False,
            )
        self.assertIn("Superuser must have is_staff=True.", str(context.exception))

    def test_create_superuser_invalid_superuser_flag_raises_error(self):
        """Superuser creation with is_superuser=False raises ValueError."""
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                email="bad_admin2@example.com",
                password="password123",
                is_superuser=False,
            )
        self.assertIn("Superuser must have is_superuser=True.", str(context.exception))

    def test_email_case_insensitive_uniqueness(self):
        """Creating users with identical email in different cases violates database uniqueness."""
        User.objects.create_user(email="customer@example.com", password="password1")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="CUSTOMER@EXAMPLE.COM", password="password2")

    def test_health_check_endpoint(self):
        """GET /api/health/ returns 200 OK and valid health JSON."""
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), "sony-feeding-kurtis-backend")
        self.assertEqual(data.get("version"), "1.0.0")
        self.assertEqual(data.get("environment"), "development")


class GoogleAuthAndJWTTests(TestCase):
    """
    Test suite for Google OAuth token exchange, JWT token issuance, and refresh.
    """

    def setUp(self):
        self.client = APIClient()

    def test_google_auth_new_user_creation(self):
        """Valid Google token creates a new user and returns JWT pair."""
        payload = {
            "token": "mock_google_token_12345",
            "email": "Ananya.Sharma@GMAIL.COM",
            "name": "Ananya Sharma",
        }
        response = self.client.post('/api/auth/google/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertTrue(data.get("is_new_user"))
        self.assertEqual(data["user"]["email"], "ananya.sharma@gmail.com")
        self.assertEqual(data["user"]["first_name"], "Ananya")
        self.assertEqual(data["user"]["last_name"], "Sharma")

        # Verify in database
        user = User.objects.get(email="ananya.sharma@gmail.com")
        self.assertEqual(user.first_name, "Ananya")
        self.assertEqual(user.google_sub, "mock-sub-mock_google_token_12345")

    def test_google_auth_existing_user(self):
        """Google auth with existing email logs in existing user without duplication."""
        existing_user = User.objects.create_user(
            email="existing.mom@gmail.com",
            first_name="Radha",
            last_name="Reddy",
        )
        payload = {
            "token": "mock_token_existing",
            "email": "existing.mom@gmail.com",
            "name": "Radha Reddy",
        }
        response = self.client.post('/api/auth/google/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertFalse(data.get("is_new_user"))
        self.assertEqual(data["user"]["id"], existing_user.id)
        self.assertEqual(User.objects.filter(email="existing.mom@gmail.com").count(), 1)

    def test_google_auth_empty_token_rejected(self):
        """Sending payload without token returns 400 Bad Request."""
        response = self.client.post('/api/auth/google/', {"email": "test@example.com"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_jwt_token_refresh(self):
        """Valid refresh token successfully issues a new access token."""
        user = User.objects.create_user(email="jwtuser@example.com")
        refresh = RefreshToken.for_user(user)

        response = self.client.post(
            '/api/auth/token/refresh/',
            {"refresh": str(refresh)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.json())

    def test_jwt_invalid_refresh_rejected(self):
        """Malformed refresh token returns 401 Unauthorized."""
        response = self.client.post(
            '/api/auth/token/refresh/',
            {"refresh": "invalid_jwt_refresh_token_string"},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CustomerProfileTests(TestCase):
    """
    Test suite for customer profile retrieval and updates.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="profile.user@example.com",
            first_name="Kavya",
            last_name="Patel",
            phone="9123456780",
        )
        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)

    def test_profile_get_authenticated(self):
        """Authenticated customer can retrieve profile details."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get('/api/auth/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["email"], "profile.user@example.com")
        self.assertEqual(data["first_name"], "Kavya")
        self.assertEqual(data["phone"], "9123456780")

    def test_profile_update_authenticated(self):
        """Authenticated customer can update phone and name."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.patch(
            '/api/auth/profile/',
            {"first_name": "Kavya S.", "phone": "9998887776"},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Kavya S.")
        self.assertEqual(self.user.phone, "9998887776")

    def test_profile_unauthenticated_rejected(self):
        """Unauthenticated requests are rejected with 401 Unauthorized."""
        response = self.client.get('/api/auth/profile/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SavedAddressTests(TestCase):
    """
    Test suite for customer SavedAddress model and API endpoints.
    Verifies auto-default, single-default exclusivity, promotion on delete,
    dual-field compatibility, and address limit enforcement.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="address.customer@example.com")
        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_first_saved_address_automatically_becomes_default(self):
        """The very first saved address is automatically designated as default."""
        address = SavedAddress.objects.create(
            user=self.user,
            recipient_name="Swathi Varma",
            phone="9876543210",
            address_line1="Flat 402, Sai Residency",
            city="Hyderabad",
            state="Telangana",
            pincode="500081",
            is_default=False,  # Even if False passed, first address forced to True
        )
        self.assertTrue(address.is_default)

    def test_single_default_exclusivity(self):
        """Setting a new default address unsets the default on previous addresses."""
        addr1 = SavedAddress.objects.create(
            user=self.user,
            recipient_name="Swathi Varma",
            phone="9876543210",
            address_line1="House 1",
            city="Hyderabad",
            state="Telangana",
            pincode="500081",
        )
        self.assertTrue(addr1.is_default)

        # Create second address with is_default=True
        addr2 = SavedAddress.objects.create(
            user=self.user,
            recipient_name="Swathi Varma",
            phone="9876543210",
            address_line1="House 2",
            city="Hyderabad",
            state="Telangana",
            pincode="500082",
            is_default=True,
        )
        addr1.refresh_from_db()
        addr2.refresh_from_db()

        self.assertFalse(addr1.is_default)
        self.assertTrue(addr2.is_default)

    def test_address_delete_promotes_replacement(self):
        """Deleting the default address automatically promotes the newest remaining address."""
        addr1 = SavedAddress.objects.create(
            user=self.user,
            recipient_name="Recipient 1",
            phone="9876543210",
            address_line1="Address 1",
            city="Hyderabad",
            state="Telangana",
            pincode="500081",
        )
        addr2 = SavedAddress.objects.create(
            user=self.user,
            recipient_name="Recipient 2",
            phone="9876543210",
            address_line1="Address 2",
            city="Hyderabad",
            state="Telangana",
            pincode="500082",
            is_default=True,
        )
        # Delete addr2 (the active default) via API
        response = self.client.delete(f'/api/auth/addresses/{addr2.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # addr1 should now be promoted to default
        addr1.refresh_from_db()
        self.assertTrue(addr1.is_default)

    def test_address_dual_field_compatibility_create(self):
        """API accepts frontend field names (houseFlat, streetArea, fullName) and returns them."""
        payload = {
            "fullName": "Priya Reddy",
            "phone": "9876543210",
            "houseFlat": "Villa 12, Green Meadows",
            "streetArea": "Madhapur",
            "landmark": "Near Metro",
            "city": "Hyderabad",
            "state": "Telangana",
            "pincode": "500081",
            "label": "Work",
        }
        response = self.client.post('/api/auth/addresses/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        # Both backend model fields and frontend alias fields are present
        self.assertEqual(data["recipient_name"], "Priya Reddy")
        self.assertEqual(data["fullName"], "Priya Reddy")
        self.assertEqual(data["address_line1"], "Villa 12, Green Meadows")
        self.assertEqual(data["houseFlat"], "Villa 12, Green Meadows")
        self.assertEqual(data["address_line2"], "Madhapur")
        self.assertEqual(data["streetArea"], "Madhapur")
        self.assertTrue(data["is_default"])

    def test_address_limit_enforcement(self):
        """Exceeding the maximum allowed limit of 3 saved addresses returns 400 Bad Request."""
        for i in range(3):
            SavedAddress.objects.create(
                user=self.user,
                recipient_name=f"Recipient {i}",
                phone="9876543210",
                address_line1=f"Flat {i}",
                city="Hyderabad",
                state="Telangana",
                pincode="500081",
            )
        # Attempt 4th address via API
        payload = {
            "fullName": "Excess Address",
            "phone": "9876543210",
            "houseFlat": "Flat 4",
            "city": "Hyderabad",
            "state": "Telangana",
            "pincode": "500081",
        }
        response = self.client.post('/api/auth/addresses/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("maximum allowed limit of 3", str(response.json()))

    def test_address_set_default_action(self):
        """Custom action POST /api/auth/addresses/<id>/set-default/ designates default."""
        addr1 = SavedAddress.objects.create(
            user=self.user,
            recipient_name="Recipient 1",
            phone="9876543210",
            address_line1="Flat 1",
            city="Hyderabad",
            state="Telangana",
            pincode="500081",
        )
        addr2 = SavedAddress.objects.create(
            user=self.user,
            recipient_name="Recipient 2",
            phone="9876543210",
            address_line1="Flat 2",
            city="Hyderabad",
            state="Telangana",
            pincode="500081",
            is_default=False,
        )
        self.assertTrue(addr1.is_default)
        self.assertFalse(addr2.is_default)

        # Call set-default on addr2
        response = self.client.post(f'/api/auth/addresses/{addr2.id}/set-default/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        addr1.refresh_from_db()
        addr2.refresh_from_db()
        self.assertFalse(addr1.is_default)
        self.assertTrue(addr2.is_default)

    def test_address_unpaginated_list(self):
        """Address list returns a direct JSON array, not wrapped in pagination."""
        SavedAddress.objects.create(
            user=self.user,
            recipient_name="Recipient 1",
            phone="9876543210",
            address_line1="Flat 1",
            city="Hyderabad",
            state="Telangana",
            pincode="500081",
        )
        response = self.client.get('/api/auth/addresses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
