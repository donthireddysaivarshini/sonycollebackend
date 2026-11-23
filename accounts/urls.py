from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    GoogleAuthView,
    LoginView,
    RegisterView,
    UserProfileView,
    SavedAddressViewSet,
)

router = DefaultRouter()
router.register(r'addresses', SavedAddressViewSet, basename='saved-address')

urlpatterns = [
    # Google OAuth token exchange
    path('google/', GoogleAuthView.as_view(), name='auth_google'),
    # Email & Password Authentication
    path('login/', LoginView.as_view(), name='auth_login'),
    path('signup/', RegisterView.as_view(), name='auth_signup'),
    path('register/', RegisterView.as_view(), name='auth_register'),
    # SimpleJWT Token Refresh
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Customer Profile (supports both /profile/ and /user/ aliases)
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('user/', UserProfileView.as_view(), name='user_profile_alias'),
    # Saved Addresses CRUD
    path('', include(router.urls)),
]

