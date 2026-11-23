from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryListView,
    CategoryDetailView,
    ProductViewSet,
    HomepageSectionListView,
    HomepageSectionDetailView,
    HeroSlideListView,
    HomeDataView,
    SiteConfigView,
)

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='catalog-products')

urlpatterns = [
    path('config/', SiteConfigView.as_view(), name='site_config'),
    path('home/', HomeDataView.as_view(), name='catalog_home_data'),
    path('hero-slides/', HeroSlideListView.as_view(), name='hero_slide_list'),
    path('categories/', CategoryListView.as_view(), name='category_list'),
    path('categories/<slug:slug>/', CategoryDetailView.as_view(), name='category_detail'),
    path('sections/', HomepageSectionListView.as_view(), name='section_list'),
    path('sections/<slug:slug>/', HomepageSectionDetailView.as_view(), name='section_detail'),
    path('', include(router.urls)),
]

