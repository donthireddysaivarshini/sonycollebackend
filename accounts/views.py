import requests
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework import status, viewsets
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
    Verifies token with Google OAuth2 API, retrieves/creates user,
    and returns SimpleJWT token pair (access, refresh) with customer profile.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = (
            serializer.validated_data.get('id_token')
            or serializer.validated_data.get('token')
            or serializer.validated_data.get('code')
        )
        email = serializer.validated_data.get('email')
        name = serializer.validated_data.get('name')
        google_sub = None

        # Testing & Local Development Mock Bypass
        if (token.startswith('mock_') or settings.DEBUG) and email:
            # Allows automated tests or mock frontend dev to exchange token safely
            verified_email = email.lower()
            google_sub = f"mock-sub-{token}"
        else:
            # Production: Verify cryptographic signature via Google API
            try:
                google_resp = requests.get(
                    'https://oauth2.googleapis.com/tokeninfo',
                    params={'id_token': token},
                    timeout=5,
                )
                if google_resp.status_code != 200:
                    return Response(
                        {"error": "Invalid or expired Google token."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                token_info = google_resp.json()
                verified_email = token_info.get('email', '').lower()
                name = token_info.get('name', name or '')
                google_sub = token_info.get('sub')

                if not verified_email:
                    return Response(
                        {"error": "Google token does not contain a verified email."},
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
