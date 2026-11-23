"""
Django settings for core project.
Sony Feeding Kurtis - Backend
Phase 1: Foundation & Custom User Model
"""

from pathlib import Path
import os
from datetime import timedelta
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if it exists
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    'SECRET_KEY',
    'django-insecure-sony-feeding-kurtis-dev-key-change-in-production-2026',
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
    if host.strip()
]

# Application definition
INSTALLED_APPS = [
    # Jazzmin must be registered BEFORE django.contrib.admin
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    # Local apps
    'accounts.apps.AccountsConfig',
    'catalog.apps.CatalogConfig',
    'cart.apps.CartConfig',
    'orders.apps.OrdersConfig',
    'payments.apps.PaymentsConfig',
    'reports.apps.ReportsConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database
# Default: SQLite for local development. Ready for PostgreSQL in production.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Custom User Model
# CRITICAL: Configured prior to initial database migrations
AUTH_USER_MODEL = 'accounts.CustomUser'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# SimpleJWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# Jazzmin Admin Panel Customization
JAZZMIN_SETTINGS = {
    'site_title': 'Sony Feeding Kurtis Admin',
    'site_header': 'Sony Collections',
    'site_brand': 'Sony Feeding Kurtis',
    'welcome_sign': 'Welcome to Sony Feeding Kurtis Administration',
    'copyright': 'Sony Feeding Kurtis / Sony Collections',
    'search_model': ['accounts.CustomUser', 'catalog.Product'],
    'topmenu_links': [
        {'name': 'Home', 'url': 'admin:index', 'permissions': ['auth.view_user']},
        {'name': 'Storefront', 'url': 'http://localhost:5173', 'new_window': True},
    ],
    'show_sidebar': True,
    'navigation_expanded': True,
    'icons': {
        'auth': 'fas fa-users-cog',
        'accounts.CustomUser': 'fas fa-user',
        'accounts.SavedAddress': 'fas fa-address-book',
        'catalog.Category': 'fas fa-tags',
        'catalog.Product': 'fas fa-tshirt',
        'catalog.ProductReview': 'fas fa-star',
        'catalog.HeroSlide': 'fas fa-images',
        'catalog.Color': 'fas fa-palette',
        'catalog.Size': 'fas fa-ruler',
        'catalog.HomepageSection': 'fas fa-th-large',
        'catalog.SiteConfig': 'fas fa-sliders-h',
        'cart.Cart': 'fas fa-shopping-cart',
        'cart.StockReservation': 'fas fa-clock',
        'orders.Order': 'fas fa-receipt',
        'orders.Coupon': 'fas fa-ticket-alt',
        'orders.FeedingOrder': 'fas fa-baby',
        'orders.NonFeedingOrder': 'fas fa-female',
        'orders.ExchangeRequest': 'fas fa-exchange-alt',
        'reports.Invoice': 'fas fa-file-invoice',
        'payments.PaymentTransaction': 'fas fa-credit-card',
    },
    'default_icon_parents': 'fas fa-chevron-circle-right',
    'default_icon_children': 'fas fa-circle',
}

JAZZMIN_UI_TWEAKS = {
    'navbar_small_text': False,
    'footer_small_text': False,
    'body_small_text': False,
    'brand_small_text': False,
    'brand_colour': 'navbar-purple',
    'accent': 'accent-primary',
    'navbar': 'navbar-dark',
    'no_navbar_border': False,
    'navbar_fixed': True,
    'layout_boxed': False,
    'footer_fixed': False,
    'sidebar_fixed': True,
    'sidebar': 'sidebar-dark-primary',
    'sidebar_nav_small_text': False,
    'sidebar_disable_expand': False,
    'sidebar_nav_child_indent': True,
    'sidebar_nav_compact_style': False,
    'sidebar_nav_legacy_style': False,
    'sidebar_nav_flat_style': False,
    'theme': 'default',
    'default_theme_mode': 'light',
    'button_classes': {
        'primary': 'btn-outline-primary',
        'secondary': 'btn-outline-secondary',
        'info': 'btn-info',
        'warning': 'btn-warning',
        'danger': 'btn-danger',
        'success': 'btn-success',
    },
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173',
    ).split(',')
    if origin.strip()
]
for local_origin in ('http://localhost:5173', 'http://127.0.0.1:5173'):
    if local_origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(local_origin)
CORS_ALLOW_CREDENTIALS = True

# Google OAuth 2.0 Credentials
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

# Razorpay Payment Gateway Configuration
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_placeholder_key')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'placeholder_secret')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', 'placeholder_webhook_secret')
COD_ENABLED = os.getenv('COD_ENABLED', 'False').lower() in ('true', '1')

