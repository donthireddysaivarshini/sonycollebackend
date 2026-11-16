from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    GoogleAuthView,
    UserProfileView,
    SavedAddressViewSet,
)

router = DefaultRouter()
router.register(r'addresses', SavedAddressViewSet, basename='saved-address')

urlpatterns = [
    # Google OAuth token exchange
    path('google/', GoogleAuthView.as_view(), name='auth_google'),
    # SimpleJWT Token Refresh
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Customer Profile
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    # Saved Addresses CRUD
    path('', include(router.urls)),
]

