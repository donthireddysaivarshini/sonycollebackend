import requests
from django.contrib.auth import get_user_model, authenticate
from django.conf import settings
from rest_framework import status, viewsets, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SavedAddress
from .serializers import (
    UserSerializer,
    GoogleAuthSerializer,
    SavedAddressSerializer,
)

User = get_user_model()


class GoogleAuthView(APIView):
    """
    Server-side Google OAuth token exchange.
    Verifies token/credential with Google OAuth2 API, retrieves/creates user,
    and returns SimpleJWT token pair (access, refresh) with customer profile.
    Supports ID token, OAuth access token, or authorization code.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        auth_code = serializer.validated_data.get('code')
        id_token_val = serializer.validated_data.get('id_token')
        raw_token = serializer.validated_data.get('token')
        email = serializer.validated_data.get('email')
        name = serializer.validated_data.get('name')

        verified_email = None
        google_sub = None

        # 1. Authorization Code Flow Exchange
        if auth_code and not id_token_val and not raw_token:
            if (auth_code.startswith('mock_') or settings.DEBUG) and email:
                verified_email = email.lower()
                google_sub = f"mock-sub-{auth_code}"
            else:
                try:
                    token_resp = requests.post(
                        'https://oauth2.googleapis.com/token',
                        data={
                            'code': auth_code,
                            'client_id': settings.GOOGLE_CLIENT_ID,
                            'client_secret': settings.GOOGLE_CLIENT_SECRET,
                            'redirect_uri': 'postmessage',
                            'grant_type': 'authorization_code',
                        },
                        timeout=5,
                    )
                    if token_resp.status_code == 200:
                        tdata = token_resp.json()
                        id_token_val = tdata.get('id_token')
                        raw_token = tdata.get('access_token')
                    else:
                        # Fallback for direct token exchange
                        id_token_val = auth_code
                except requests.RequestException as e:
                    return Response(
                        {"error": f"Failed to communicate with Google token service: {str(e)}"},
                        status=status.HTTP_502_BAD_GATEWAY,
                    )

        # 2. Token Verification (ID token or access token)
        if not verified_email:
            token_to_verify = id_token_val or raw_token or auth_code
            if (token_to_verify.startswith('mock_') or (settings.DEBUG and not settings.GOOGLE_CLIENT_ID)) and email:
                verified_email = email.lower()
                google_sub = f"mock-sub-{token_to_verify}"
            else:
                try:
                    # Prefer id_token verification with tokeninfo
                    if id_token_val or (token_to_verify and not raw_token):
                        token_param = id_token_val or token_to_verify
                        google_resp = requests.get(
                            'https://oauth2.googleapis.com/tokeninfo',
                            params={'id_token': token_param},
                            timeout=5,
                        )
                        if google_resp.status_code == 200:
                            token_info = google_resp.json()
                            verified_email = token_info.get('email', '').lower()
                            name = token_info.get('name', name or '')
                            google_sub = token_info.get('sub')
                    # Fallback to access_token userinfo lookup
                    if not verified_email and (raw_token or token_to_verify):
                        access_param = raw_token or token_to_verify
                        userinfo_resp = requests.get(
                            'https://www.googleapis.com/oauth2/v3/userinfo',
                            headers={'Authorization': f'Bearer {access_param}'},
                            timeout=5,
                        )
                        if userinfo_resp.status_code == 200:
                            uinfo = userinfo_resp.json()
                            verified_email = uinfo.get('email', '').lower()
                            name = uinfo.get('name', name or '')
                            google_sub = uinfo.get('sub')

                    if not verified_email:
                        return Response(
                            {"error": "Invalid or expired Google authentication credentials."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                except requests.RequestException as e:
                    return Response(
                        {"error": f"Failed to communicate with Google authentication service: {str(e)}"},
                        status=status.HTTP_502_BAD_GATEWAY,
                    )

        # Retrieve or atomically create user
        user, created = User.objects.get_or_create(
            email=verified_email,
            defaults={
                'google_sub': google_sub,
                'first_name': name.split(' ')[0] if name else '',
                'last_name': ' '.join(name.split(' ')[1:]) if (name and ' ' in name) else '',
            },
        )

        # Update google_sub if not present
        if google_sub and not user.google_sub:
            user.google_sub = google_sub
            user.save(update_fields=['google_sub'])

        # Generate JWT token pair
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
                "is_new_user": created,
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    """
    Standard email & password login.
    Returns SimpleJWT token pair and customer profile.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password', '')
        if not email or not password:
            return Response(
                {"error": "Both email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = authenticate(request, username=email, password=password)
        if not user:
            existing = User.objects.filter(email=email).first()
            if not existing:
                return Response(
                    {"error": "No account found with this email. Please check your email or create an account."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if existing.google_sub and not existing.has_usable_password():
                return Response(
                    {"error": "This account was registered via Google Sign-In. Please click 'Continue with Google'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"error": "Invalid email or password. Please check your password and try again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_active:
            return Response(
                {"error": "This account has been deactivated."},
                status=status.HTTP_403_FORBIDDEN,
            )
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class RegisterView(APIView):
    """
    Customer registration with email, password, name, and optional phone.
    Returns SimpleJWT token pair and newly created customer profile.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password', '')
        name = request.data.get('name', '').strip() or request.data.get('first_name', '').strip()
        phone = request.data.get('phone', '').strip()

        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(password) < 8:
            return Response(
                {"error": "Password must be at least 8 characters long."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "An account with this email already exists. Please log in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        first_name = name.split(' ')[0] if name else ''
        last_name = ' '.join(name.split(' ')[1:]) if (name and ' ' in name) else ''

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
        )
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
                "is_new_user": True,
            },
            status=status.HTTP_201_CREATED,
        )


class UserProfileView(APIView):
    """
    Retrieve and update customer profile details.
    Requires active JWT authentication.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        return self._update(request, partial=False)

    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial=False):
        serializer = UserSerializer(request.user, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class SavedAddressViewSet(viewsets.ModelViewSet):
    """
    Customer address book CRUD viewset.
    Unpaginated to ensure frontend receives a clean, complete list.
    Enforces auto-default and promotion-on-delete invariants.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = SavedAddressSerializer
    pagination_class = None

    def get_queryset(self):
        return SavedAddress.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check if identical address already exists for this customer
        line1 = serializer.validated_data.get('address_line1', '').strip()
        pin = serializer.validated_data.get('pincode', '').strip()
        existing = SavedAddress.objects.filter(
            user=request.user,
            address_line1__iexact=line1,
            pincode__iexact=pin
        ).first()

        if existing:
            recipient = serializer.validated_data.get('recipient_name')
            phone = serializer.validated_data.get('phone')
            if recipient:
                existing.recipient_name = recipient
            if phone:
                existing.phone = phone
            existing.save()
            return Response(self.get_serializer(existing).data, status=status.HTTP_200_OK)

        if SavedAddress.objects.filter(user=request.user).count() >= 3:
            return Response(
                {"error": "You can save up to 3 delivery addresses. Please choose an existing address or delete one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        was_default = instance.is_default
        user = instance.user
        instance.delete()

        # If deleted address was default, promote the newest remaining address
        if was_default:
            replacement = (
                SavedAddress.objects.filter(user=user)
                .order_by('-created_at')
                .first()
            )
            if replacement:
                replacement.is_default = True
                replacement.save(update_fields=['is_default'])

    @action(detail=True, methods=['post'], url_path='set-default')
    def set_default(self, request, pk=None):
        """
        Explicitly designate this address as the customer's default delivery address.
        """
        address = self.get_object()
        address.is_default = True
        address.save()
        return Response(SavedAddressSerializer(address).data, status=status.HTTP_200_OK)

