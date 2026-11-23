from django.db.models import Q
from rest_framework import generics, viewsets
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Category, Product, HomepageSection, HeroSlide, SiteConfig
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    HomepageSectionSerializer,
    HeroSlideSerializer,
)


class CategoryListView(generics.ListAPIView):
    """
    Public listing of active categories ordered by display_order.
    """

    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(is_active=True).order_by('display_order', 'name')


class CategoryDetailView(generics.RetrieveAPIView):
    """
    Retrieve single category by its slug.
    """

    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Category.objects.filter(is_active=True)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public product catalogue viewset.
    Supports filtering by category, clothing_type, handstock, new arrival,
    best seller, search keyword, and custom sorting.
    Strictly filters is_active=True.
    """

    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    lookup_field = 'slug'
    pagination_class = None  # Small-to-medium catalogue; supports unpaginated or direct consumption

    def get_queryset(self):
        queryset = (
            Product.objects.filter(is_active=True)
            .select_related('category')
            .prefetch_related('images', 'variants__color', 'variants__size')
            .order_by('-created_at')
        )

        category_slug = self.request.query_params.get('category')
        if category_slug:
            # Handle aliases if needed (e.g. dresses -> partywear-dresses)
            category_aliases = {
                'dresses': 'partywear-dresses',
                'kids-wear': 'kids-collections',
                'kidswear': 'kids-collections',
                'co-ords': 'co-ord-sets',
                '3pc-sets': '3-piece-dresses',
            }
            resolved_category = category_aliases.get(category_slug, category_slug)
            queryset = queryset.filter(category__slug=resolved_category)

        clothing_type = self.request.query_params.get('clothing_type') or self.request.query_params.get('clothingType')
        if clothing_type:
            clothing_type_normalized = clothing_type.strip()
            if clothing_type_normalized.lower() in ('feeding', 'feeding-only'):
                queryset = queryset.filter(variants__clothing_type='Feeding')
            elif clothing_type_normalized.lower() in ('non-feeding', 'non_feeding'):
                queryset = queryset.filter(variants__clothing_type='Non-Feeding')
            elif clothing_type_normalized.lower() == 'standard':
                queryset = queryset.filter(variants__clothing_type='Standard')

        if self.request.query_params.get('handstock') in ('true', '1', 'True'):
            queryset = queryset.filter(is_handstock=True)

        if self.request.query_params.get('is_new_arrival') in ('true', '1', 'True'):
            queryset = queryset.filter(is_new_arrival=True)

        if self.request.query_params.get('is_best_seller') in ('true', '1', 'True'):
            queryset = queryset.filter(is_best_seller=True)

        section_param = self.request.query_params.get('section')
        if section_param:
            sec_lower = section_param.strip().lower()
            if sec_lower in ('feeding-collection', 'feeding'):
                queryset = queryset.filter(is_feeding_collection=True)
            elif sec_lower in ('handstock', 'handstocks'):
                queryset = queryset.filter(is_handstock=True)
            elif sec_lower in ('sarees', 'saree'):
                queryset = queryset.filter(is_sarees_collection=True)
            elif sec_lower in ('kids-wear', 'kidswear', 'kids-collections'):
                queryset = queryset.filter(is_kidswear_collection=True)
            elif sec_lower in ('new-arrivals', 'new'):
                queryset = queryset.filter(is_new_arrival=True)
            elif sec_lower in ('best-sellers', 'bestseller'):
                queryset = queryset.filter(is_best_seller=True)

        search_query = self.request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(fabric__icontains=search_query)
                | Q(sku_prefix__icontains=search_query)
                | Q(variants__sku__icontains=search_query)
            )

        sort_by = self.request.query_params.get('sortBy') or self.request.query_params.get('sort_by')
        if sort_by == 'price-low':
            queryset = queryset.order_by('price')
        elif sort_by == 'price-high':
            queryset = queryset.order_by('-price')
        elif sort_by in ('popular', 'bestseller'):
            queryset = queryset.order_by('-review_count', '-rating')
        elif sort_by == 'newest':
            queryset = queryset.order_by('-created_at')

        return queryset.distinct()


class HomepageSectionListView(generics.ListAPIView):
    """
    Public listing of active homepage sections with nested active products.
    Ordered by merchandising sequence.
    """

    permission_classes = [AllowAny]
    serializer_class = HomepageSectionSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            HomepageSection.objects.filter(is_active=True)
            .prefetch_related('items__product')
            .order_by('display_order', 'title')
        )


class HomepageSectionDetailView(generics.RetrieveAPIView):
    """
    Retrieve single active homepage section by its slug.
    """

    permission_classes = [AllowAny]
    serializer_class = HomepageSectionSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return HomepageSection.objects.filter(is_active=True).prefetch_related('items__product')


class HeroSlideListView(generics.ListAPIView):
    """
    Public listing of active hero banner slides ordered by display_order.
    """

    permission_classes = [AllowAny]
    serializer_class = HeroSlideSerializer
    pagination_class = None

    def get_queryset(self):
        return HeroSlide.objects.filter(is_active=True).order_by('display_order', 'id')


class HomeDataView(APIView):
    """
    Consolidated endpoint returning all homepage data in one request:
    hero slides, categories, and all 6 curated home sections.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        active_products = (
            Product.objects.filter(is_active=True)
            .select_related('category')
            .prefetch_related('images', 'variants__color', 'variants__size')
        )
        hero_slides = HeroSlide.objects.filter(is_active=True).order_by('display_order', 'id')
        categories = Category.objects.filter(is_active=True).order_by('display_order', 'name')

        sections_qs = HomepageSection.objects.filter(is_active=True).order_by('display_order')
        sections_meta = {
            s.slug: {
                'id': s.id,
                'title': s.title,
                'slug': s.slug,
                'subtitle': s.subtitle,
                'badge_label': s.badge_label,
                'view_all_link': s.view_all_link,
                'direction': s.direction,
                'display_order': s.display_order,
            }
            for s in sections_qs
        }

        config = SiteConfig.get_solo()
        site_config_data = {
            'shipping_fee': float(config.shipping_fee or 99.0),
            'free_shipping_threshold': float(config.free_shipping_threshold or 1499.0),
            'shipping_notice': config.shipping_notice or "Free shipping across India on orders above ₹1499",
            'exchange_window_days': config.exchange_window_days or 7,
            'max_saved_addresses': config.max_saved_addresses or 3,
            'cod_enabled': False,
            'tax_percentage': float(config.tax_percentage or 5.0),
            'is_tax_inclusive': bool(config.is_tax_inclusive),
        }

        return Response({
            'site_config': site_config_data,
            'hero_slides': HeroSlideSerializer(hero_slides, many=True, context={'request': request}).data,
            'categories': CategorySerializer(categories, many=True, context={'request': request}).data,
            'sections_meta': sections_meta,
            'sections': {
                'feeding_collection': ProductSerializer(
                    active_products.filter(is_feeding_collection=True)[:12],
                    many=True,
                    context={'request': request},
                ).data,
                'handstock': ProductSerializer(
                    active_products.filter(is_handstock=True)[:12],
                    many=True,
                    context={'request': request},
                ).data,
                'sarees': ProductSerializer(
                    active_products.filter(is_sarees_collection=True)[:12],
                    many=True,
                    context={'request': request},
                ).data,
                'kids_wear': ProductSerializer(
                    active_products.filter(is_kidswear_collection=True)[:12],
                    many=True,
                    context={'request': request},
                ).data,
                'new_arrivals': ProductSerializer(
                    active_products.filter(is_new_arrival=True)[:12],
                    many=True,
                    context={'request': request},
                ).data,
                'best_sellers': ProductSerializer(
                    active_products.filter(is_best_seller=True)[:12],
                    many=True,
                    context={'request': request},
                ).data,
            },
        })


class SiteConfigView(APIView):
    """
    Public store configuration endpoint providing dynamic shipping fees,
    free shipping thresholds, policies, and address limits.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        config = SiteConfig.get_solo()
        return Response({
            'shipping_fee': float(config.shipping_fee or 99.0),
            'free_shipping_threshold': float(config.free_shipping_threshold or 1499.0),
            'shipping_notice': config.shipping_notice or "Free shipping across India on orders above ₹1499",
            'exchange_window_days': config.exchange_window_days or 7,
            'max_saved_addresses': config.max_saved_addresses or 3,
            'cod_enabled': False,
            'tax_percentage': float(config.tax_percentage or 5.0),
            'is_tax_inclusive': bool(config.is_tax_inclusive),
        })



