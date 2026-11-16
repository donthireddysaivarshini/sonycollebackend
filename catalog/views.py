from django.db.models import Q
from rest_framework import generics, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


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

        search_query = self.request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
                | Q(fabric__icontains=search_query)
                | Q(sku_prefix__icontains=search_query)
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
