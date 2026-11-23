from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from rest_framework.test import APIClient
from rest_framework import status

from .models import (
    Category,
    Color,
    Size,
    Product,
    ProductImage,
    ProductVariant,
    HomepageSection,
    HomepageSectionItem,
)


class CategoryModelAndApiTests(TestCase):
    """
    Test suite for Category model and API endpoints.
    Verifies that all 8 canonical categories seeded by migrations are active and ordered.
    """

    def setUp(self):
        self.client = APIClient()

    def test_category_list_api_returns_all_eight_seeded_categories(self):
        """GET /api/catalog/categories/ returns all 8 canonical categories ordered by display_order."""
        response = self.client.get('/api/catalog/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data), 8)
        expected_slugs = [
            'frocks',
            'co-ord-sets',
            'kurti-dupatta',
            '3-piece-dresses',
            'partywear-dresses',
            'sarees',
            'lehengas',
            'kids-collections',
        ]
        actual_slugs = [c["slug"] for c in data]
        self.assertEqual(actual_slugs, expected_slugs)

    def test_category_detail_api(self):
        """GET /api/catalog/categories/<slug>/ returns single active category."""
        response = self.client.get('/api/catalog/categories/frocks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["name"], "Frocks")
        self.assertEqual(data["slug"], "frocks")

    def test_inactive_category_excluded_from_public_api(self):
        """Inactive categories are not returned in category list."""
        Category.objects.create(
            name="Deactivated Season",
            slug="deactivated-season",
            display_order=99,
            is_active=False,
        )
        response = self.client.get('/api/catalog/categories/')
        slugs = [c["slug"] for c in response.json()]
        self.assertNotIn("deactivated-season", slugs)


class FeedingConfigValidationTests(TestCase):
    """
    Test suite enforcing the 3-way feeding configuration business rule.
    Validates that variant clothing_type strictly obeys parent feeding_config.
    """

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(
            slug="partywear-dresses",
            defaults={"name": "Partywear Dresses"},
        )
        self.color, _ = Color.objects.get_or_create(name="Emerald Green", defaults={"hex_code": "#059669"})
        self.size_m, _ = Size.objects.get_or_create(name="M", defaults={"order": 2})
        self.size_l, _ = Size.objects.get_or_create(name="L", defaults={"order": 3})

    def test_feeding_config_both(self):
        """Product with feeding_config='both' allows Feeding and Non-Feeding, rejects Standard."""
        product = Product.objects.create(
            title="Nayantara Floral Dress",
            slug="nayantara-floral-dress",
            sku_prefix="SFK-NAY",
            category=self.category,
            feeding_config="both",
            price=Decimal("1299.00"),
        )
        # Feeding variant succeeds
        v1 = ProductVariant.objects.create(
            product=product,
            clothing_type="Feeding",
            color=self.color,
            size=self.size_m,
            sku="SFK-NAY-F-GRN-M",
            stock=10,
        )
        self.assertEqual(v1.clothing_type, "Feeding")

        # Non-Feeding variant succeeds
        v2 = ProductVariant.objects.create(
            product=product,
            clothing_type="Non-Feeding",
            color=self.color,
            size=self.size_l,
            sku="SFK-NAY-NF-GRN-L",
            stock=10,
        )
        self.assertEqual(v2.clothing_type, "Non-Feeding")

        # Standard variant on a 'both' product MUST raise ValidationError
        with self.assertRaises(ValidationError):
            ProductVariant.objects.create(
                product=product,
                clothing_type="Standard",
                color=self.color,
                size=self.size_m,
                sku="SFK-NAY-STD-GRN-M",
                stock=5,
            )

    def test_feeding_config_feeding_only(self):
        """Product with feeding_config='feeding-only' allows Feeding, rejects Non-Feeding and Standard."""
        product = Product.objects.create(
            title="Dedicated Nursing Gown",
            slug="dedicated-nursing-gown",
            sku_prefix="SFK-NUR",
            category=self.category,
            feeding_config="feeding-only",
            price=Decimal("1499.00"),
        )
        # Feeding succeeds
        v = ProductVariant.objects.create(
            product=product,
            clothing_type="Feeding",
            color=self.color,
            size=self.size_m,
            sku="SFK-NUR-F-GRN-M",
            stock=15,
        )
        self.assertEqual(v.clothing_type, "Feeding")

        # Non-Feeding raises ValidationError
        with self.assertRaises(ValidationError):
            ProductVariant.objects.create(
                product=product,
                clothing_type="Non-Feeding",
                color=self.color,
                size=self.size_l,
                sku="SFK-NUR-NF-GRN-L",
                stock=5,
            )

        # Standard raises ValidationError
        with self.assertRaises(ValidationError):
            ProductVariant.objects.create(
                product=product,
                clothing_type="Standard",
                color=self.color,
                size=self.size_m,
                sku="SFK-NUR-STD-GRN-M",
                stock=5,
            )

    def test_feeding_config_none(self):
        """Product with feeding_config='none' allows Standard, rejects Feeding and Non-Feeding."""
        saree_cat, _ = Category.objects.get_or_create(slug="sarees", defaults={"name": "Sarees"})
        product = Product.objects.create(
            title="Kanchivaram Pure Silk Saree",
            slug="kanchivaram-pure-silk-saree",
            sku_prefix="SFK-SAR",
            category=saree_cat,
            feeding_config="none",
            price=Decimal("2999.00"),
        )
        # Standard succeeds
        v = ProductVariant.objects.create(
            product=product,
            clothing_type="Standard",
            color=self.color,
            size=self.size_m,
            sku="SFK-SAR-STD-GRN-FS",
            stock=8,
        )
        self.assertEqual(v.clothing_type, "Standard")

        # Feeding raises ValidationError
        with self.assertRaises(ValidationError):
            ProductVariant.objects.create(
                product=product,
                clothing_type="Feeding",
                color=self.color,
                size=self.size_m,
                sku="SFK-SAR-F-GRN-M",
                stock=5,
            )


class ProductVariantUniquenessTests(TestCase):
    """
    Test suite verifying non-null variant uniqueness on database level.
    """

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(slug="kurti-dupatta", defaults={"name": "Kurti + Dupatta"})
        self.color, _ = Color.objects.get_or_create(name="Royal Blue", defaults={"hex_code": "#1d4ed8"})
        self.size, _ = Size.objects.get_or_create(name="XL", defaults={"order": 4})
        self.product = Product.objects.create(
            title="Classic Silk Kurti",
            slug="classic-silk-kurti",
            sku_prefix="SFK-CLS",
            category=self.category,
            feeding_config="none",
            price=Decimal("999.00"),
        )

    def test_duplicate_variant_combination_prevented(self):
        """Creating duplicate variant with same product, clothing_type, color, and size raises error."""
        ProductVariant.objects.create(
            product=self.product,
            clothing_type="Standard",
            color=self.color,
            size=self.size,
            sku="SFK-CLS-STD-BLU-XL",
            stock=5,
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            ProductVariant.objects.create(
                product=self.product,
                clothing_type="Standard",
                color=self.color,
                size=self.size,
                sku="SFK-CLS-STD-BLU-XL-DUP",
                stock=10,
            )


class AvailableStockAndPricingTests(TestCase):
    """
    Test suite for inventory calculation and price computation.
    """

    def setUp(self):
        self.category, _ = Category.objects.get_or_create(slug="frocks", defaults={"name": "Frocks"})
        self.color, _ = Color.objects.get_or_create(name="Ruby Red", defaults={"hex_code": "#dc2626"})
        self.size, _ = Size.objects.get_or_create(name="S", defaults={"order": 1})
        self.product = Product.objects.create(
            title="Flared Cotton Frock",
            slug="flared-cotton-frock",
            sku_prefix="SFK-FLR",
            category=self.category,
            feeding_config="both",
            price=Decimal("1199.00"),
            mrp=Decimal("1999.00"),
        )

    def test_available_stock_property(self):
        """available_stock equals stock minus reserved_stock, floored at 0."""
        variant = ProductVariant.objects.create(
            product=self.product,
            clothing_type="Feeding",
            color=self.color,
            size=self.size,
            sku="SFK-FLR-F-RED-S",
            stock=10,
            reserved_stock=3,
        )
        self.assertEqual(variant.available_stock, 7)

        # Over-reserved safety guard
        variant.reserved_stock = 15
        self.assertEqual(variant.available_stock, 0)

    def test_pricing_and_discount_calculation(self):
        """Product discount_percentage calculated from mrp and price."""
        self.assertEqual(self.product.discount_percentage, 40)

        # Final price defaults to product.price
        variant = ProductVariant.objects.create(
            product=self.product,
            clothing_type="Feeding",
            color=self.color,
            size=self.size,
            sku="SFK-FLR-F-RED-S2",
            stock=5,
        )
        self.assertEqual(variant.final_price, Decimal("1199.00"))

        # Price override takes precedence
        variant.price_override = Decimal("1299.00")
        self.assertEqual(variant.final_price, Decimal("1299.00"))


class ProductApiContractTests(TestCase):
    """
    Test suite for Product API matching the DjangoProductResponse DTO structure.
    """

    def setUp(self):
        self.client = APIClient()
        self.category, _ = Category.objects.get_or_create(slug="co-ord-sets", defaults={"name": "Co-ord Sets"})
        self.color, _ = Color.objects.get_or_create(name="Teal", defaults={"hex_code": "#0d9488"})
        self.size, _ = Size.objects.get_or_create(name="M", defaults={"order": 2})

        self.active_product = Product.objects.create(
            title="Botanical Co-ord Set",
            slug="botanical-co-ord-set",
            sku_prefix="SFK-BOT",
            category=self.category,
            feeding_config="both",
            price=Decimal("1599.00"),
            mrp=Decimal("2499.00"),
            description="Contemporary two-piece set.",
            fabric="Pure Cotton",
            care_instructions="Hand wash separately.",
            is_new_arrival=True,
            is_best_seller=False,
            is_handstock=True,
            is_active=True,
        )
        ProductImage.objects.create(
            product=self.active_product,
            image="co-ords/botanical.jpg",
            order=1,
            is_primary=True,
        )
        ProductVariant.objects.create(
            product=self.active_product,
            clothing_type="Feeding",
            color=self.color,
            size=self.size,
            sku="SFK-BOT-F-TEA-M",
            stock=12,
        )

        self.inactive_product = Product.objects.create(
            title="Archived Co-ord Set",
            slug="archived-co-ord-set",
            sku_prefix="SFK-ARC",
            category=self.category,
            feeding_config="both",
            price=Decimal("1000.00"),
            is_active=False,
        )

    def test_product_list_api_contract_matches_dto(self):
        """GET /api/catalog/products/ returns products matching DjangoProductResponse."""
        response = self.client.get('/api/catalog/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data), 1)  # Inactive product excluded
        prod = data[0]

        # Verify exact DTO fields
        self.assertEqual(prod["title"], "Botanical Co-ord Set")
        self.assertEqual(prod["slug"], "botanical-co-ord-set")
        self.assertEqual(prod["sku"], "SFK-BOT")
        self.assertEqual(prod["category"]["slug"], "co-ord-sets")
        self.assertEqual(prod["price"], "1599.00")
        self.assertEqual(prod["original_price"], "2499.00")
        self.assertEqual(prod["discount_percentage"], 36)
        self.assertTrue(prod["is_new_arrival"])
        self.assertTrue(prod["is_handstock"])

        # Verify nested images
        self.assertEqual(len(prod["images"]), 1)
        self.assertTrue(prod["images"][0]["image"].endswith("co-ords/botanical.jpg"))

        # Verify nested variants
        self.assertEqual(len(prod["variants"]), 1)
        variant = prod["variants"][0]
        self.assertEqual(variant["clothing_type"], "feeding")
        self.assertEqual(variant["color"]["name"], "Teal")
        self.assertEqual(variant["color"]["hex_code"], "#0d9488")
        self.assertEqual(variant["size"]["name"], "M")
        self.assertEqual(variant["sku"], "SFK-BOT-F-TEA-M")
        self.assertEqual(variant["stock"], 12)
        self.assertEqual(variant["final_price"], "1599.00")

    def test_product_detail_api(self):
        """GET /api/catalog/products/<slug>/ returns single product detail."""
        response = self.client.get('/api/catalog/products/botanical-co-ord-set/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["title"], "Botanical Co-ord Set")
        self.assertEqual(data["slug"], "botanical-co-ord-set")

    def test_product_filtering(self):
        """Filtering by category, clothing_type, and handstock."""
        # By category
        res = self.client.get('/api/catalog/products/?category=co-ord-sets')
        self.assertEqual(len(res.json()), 1)

        # By other category (empty)
        res = self.client.get('/api/catalog/products/?category=sarees')
        self.assertEqual(len(res.json()), 0)

        # By handstock
        res = self.client.get('/api/catalog/products/?handstock=true')
        self.assertEqual(len(res.json()), 1)

        # By clothing_type
        res = self.client.get('/api/catalog/products/?clothing_type=feeding')
        self.assertEqual(len(res.json()), 1)
        res = self.client.get('/api/catalog/products/?clothing_type=standard')
        self.assertEqual(len(res.json()), 0)


class HomepageSectionTests(TestCase):
    """
    Test suite for HomepageSection and HomepageSectionItem models and API endpoints.
    Verifies section ordering, product assignment ordering, inactive exclusions,
    and multi-section product assignments.
    """

    def setUp(self):
        self.client = APIClient()
        self.category, _ = Category.objects.get_or_create(slug="sarees", defaults={"name": "Sarees"})

        # Create test products
        self.prod1 = Product.objects.create(
            title="Kanchivaram Silk Saree",
            slug="kanchivaram-silk-saree",
            sku_prefix="SFK-SAR-1",
            category=self.category,
            feeding_config="none",
            price=Decimal("4999.00"),
            is_active=True,
        )
        self.prod2 = Product.objects.create(
            title="Banarasi Brocade Saree",
            slug="banarasi-brocade-saree",
            sku_prefix="SFK-SAR-2",
            category=self.category,
            feeding_config="none",
            price=Decimal("5999.00"),
            is_active=True,
        )
        self.inactive_prod = Product.objects.create(
            title="Archived Out-of-Stock Saree",
            slug="archived-saree",
            sku_prefix="SFK-SAR-ARC",
            category=self.category,
            feeding_config="none",
            price=Decimal("2000.00"),
            is_active=False,
        )

    def test_homepage_section_list_api_ordered(self):
        """GET /api/catalog/sections/ returns 6 canonical sections in display_order."""
        response = self.client.get('/api/catalog/sections/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data), 6)
        expected_slugs = [
            'feeding-collection',
            'handstock',
            'sarees',
            'kids-wear',
            'new-arrivals',
            'best-sellers',
        ]
        self.assertEqual([s["slug"] for s in data], expected_slugs)

    def test_homepage_section_detail_api(self):
        """GET /api/catalog/sections/<slug>/ returns single section."""
        response = self.client.get('/api/catalog/sections/sarees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["title"], "Sarees")
        self.assertEqual(data["slug"], "sarees")
        self.assertEqual(data["direction"], "left")

    def test_homepage_section_products_ordering(self):
        """Assigned products within a section appear in exact order defined by HomepageSectionItem."""
        section = HomepageSection.objects.get(slug='sarees')

        # Assign prod2 first (order 1), prod1 second (order 2)
        HomepageSectionItem.objects.create(section=section, product=self.prod2, order=1)
        HomepageSectionItem.objects.create(section=section, product=self.prod1, order=2)

        response = self.client.get('/api/catalog/sections/sarees/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        products = response.json()["products"]

        self.assertEqual(len(products), 2)
        self.assertEqual(products[0]["slug"], "banarasi-brocade-saree")
        self.assertEqual(products[1]["slug"], "kanchivaram-silk-saree")

    def test_inactive_product_excluded_from_section(self):
        """Assigned product with is_active=False is excluded from public section results."""
        section = HomepageSection.objects.get(slug='sarees')
        HomepageSectionItem.objects.create(section=section, product=self.prod1, order=1)
        HomepageSectionItem.objects.create(section=section, product=self.inactive_prod, order=2)

        response = self.client.get('/api/catalog/sections/sarees/')
        products = response.json()["products"]
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["slug"], "kanchivaram-silk-saree")

    def test_inactive_section_excluded_from_storefront(self):
        """Deactivated section is omitted from GET /api/catalog/sections/."""
        HomepageSection.objects.create(
            title="Seasonal Diwali Festive",
            slug="seasonal-diwali-festive",
            display_order=99,
            is_active=False,
        )
        response = self.client.get('/api/catalog/sections/')
        slugs = [s["slug"] for s in response.json()]
        self.assertNotIn("seasonal-diwali-festive", slugs)

    def test_product_in_multiple_sections(self):
        """A single product can belong to multiple homepage sections simultaneously."""
        sec_sarees = HomepageSection.objects.get(slug='sarees')
        sec_bestsellers = HomepageSection.objects.get(slug='best-sellers')

        HomepageSectionItem.objects.create(section=sec_sarees, product=self.prod1, order=1)
        HomepageSectionItem.objects.create(section=sec_bestsellers, product=self.prod1, order=1)

        # Appears in Sarees
        res1 = self.client.get('/api/catalog/sections/sarees/')
        self.assertEqual(len(res1.json()["products"]), 1)

        # Also appears in Best Sellers
        res2 = self.client.get('/api/catalog/sections/best-sellers/')
        self.assertEqual(len(res2.json()["products"]), 1)

    def test_section_product_uniqueness(self):
        """Assigning duplicate product to the same section raises IntegrityError."""
        section = HomepageSection.objects.get(slug='sarees')
        HomepageSectionItem.objects.create(section=section, product=self.prod1, order=1)

        with self.assertRaises(IntegrityError):
            HomepageSectionItem.objects.create(section=section, product=self.prod1, order=2)

