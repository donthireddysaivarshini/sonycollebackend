import json
import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from catalog.models import (
    Category,
    Color,
    Size,
    Product,
    ProductImage,
    ProductVariant,
    HeroSlide,
    HomepageSection,
)


class Command(BaseCommand):
    help = "Seed database with all products, categories, hero slides, and variants from frontend data."

    def handle(self, *args, **options):
        file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'catalog_seed_data.json')
        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"Seed file not found at {file_path}"))
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.stdout.write(self.style.NOTICE("Starting catalog seed from frontend data..."))

        with transaction.atomic():
            # 1. Categories
            categories_data = data.get('categories', [])
            category_map = {}
            for idx, c in enumerate(categories_data):
                slug = c.get('slug')
                raw_img = c.get('image', '').lstrip('/').replace('images/', '', 1)
                cat, created = Category.objects.update_or_create(
                    slug=slug,
                    defaults={
                        'name': c.get('name'),
                        'image': raw_img,
                        'item_count_label': c.get('itemCount', ''),
                        'description': c.get('description', ''),
                        'tagline': c.get('tagline', ''),
                        'display_order': idx + 1,
                        'is_active': True,
                    }
                )
                category_map[slug] = cat
                # Also record common aliases
                if slug == 'partywear-dresses':
                    category_map['dresses'] = cat
                elif slug == 'kids-collections':
                    category_map['kids-wear'] = cat
                    category_map['kidswear'] = cat
                elif slug == 'co-ord-sets':
                    category_map['co-ords'] = cat
                elif slug == '3-piece-dresses':
                    category_map['3pc-sets'] = cat

            self.stdout.write(self.style.SUCCESS(f"Processed {len(categories_data)} categories."))

            # 2. Hero Slides
            slides_data = data.get('hero_slides', [])
            HeroSlide.objects.all().delete()
            for idx, s in enumerate(slides_data):
                desk_img = s.get('desktopImage', '').lstrip('/').replace('images/', '', 1)
                mob_img = s.get('mobileImage', '').lstrip('/').replace('images/', '', 1)
                HeroSlide.objects.create(
                    title=s.get('title', f"Promotion {idx + 1}"),
                    cta_link=s.get('ctaLink', '/shop'),
                    desktop_image=desk_img,
                    mobile_image=mob_img,
                    preserve_artwork=s.get('preserveArtwork', True),
                    display_order=idx + 1,
                    is_active=True,
                )
            self.stdout.write(self.style.SUCCESS(f"Seeded {len(slides_data)} hero slides."))

            # 3. Size order lookup
            size_order_map = {'S': 1, 'M': 2, 'L': 3, 'XL': 4, 'XXL': 5, '3XL': 6, 'Free Size': 7}

            # 4. Products & Variants
            products_data = data.get('products', [])
            preferred_feeding_ids = {'prod-26', 'prod-29', 'prod-27', 'prod-5', 'prod-1', 'prod-2', 'prod-4', 'prod-10'}

            total_variants = 0
            total_images = 0

            for p in products_data:
                cat_slug = p.get('category', '').lower()
                cat = category_map.get(cat_slug)
                if not cat:
                    # Fallback to first category
                    cat = Category.objects.filter(is_active=True).first()

                feeding_config = p.get('feedingConfig', 'both')
                if feeding_config not in ('both', 'feeding-only', 'none'):
                    feeding_config = 'both'

                price = Decimal(str(p.get('price', 1499)))
                mrp_val = p.get('originalPrice')
                mrp = Decimal(str(mrp_val)) if mrp_val else None

                # Section flags
                is_feeding_sec = p.get('id') in preferred_feeding_ids or feeding_config in ('both', 'feeding-only')
                is_handstock_sec = bool(p.get('isHandstock'))
                is_sarees_sec = cat.slug == 'sarees' or cat_slug == 'sarees'
                is_kidswear_sec = cat.slug == 'kids-collections' or cat_slug in ('kids-collections', 'kids-wear', 'kidswear')
                is_new_arr = bool(p.get('isNewArrival'))
                is_best_sell = bool(p.get('isBestseller') or p.get('isFeatured'))

                care_inst = p.get('careInstructions', [])
                care_text = '\n'.join(care_inst) if isinstance(care_inst, list) else str(care_inst)

                prod, _ = Product.objects.update_or_create(
                    slug=p.get('slug'),
                    defaults={
                        'title': p.get('title'),
                        'sku_prefix': p.get('skuPrefix', f"SK-{p.get('id')}"),
                        'category': cat,
                        'feeding_config': feeding_config,
                        'price': price,
                        'mrp': mrp,
                        'description': p.get('description', ''),
                        'fabric': p.get('fabric', 'Cotton / Festive Blend'),
                        'care_instructions': care_text,
                        'is_feeding_collection': is_feeding_sec,
                        'is_handstock': is_handstock_sec,
                        'is_sarees_collection': is_sarees_sec,
                        'is_kidswear_collection': is_kidswear_sec,
                        'is_new_arrival': is_new_arr,
                        'is_best_seller': is_best_sell,
                        'is_active': True,
                        'rating': Decimal(str(p.get('rating', '4.80'))),
                        'review_count': int(p.get('reviewCount', 120)),
                    }
                )

                # Colors first so images can link to them
                color_by_name = {}
                for c in p.get('availableColors', []):
                    c_obj, _ = Color.objects.get_or_create(
                        name=c['name'],
                        defaults={'hex_code': c.get('hex', '#552058')}
                    )
                    color_by_name[c['name']] = c_obj

                # Images
                prod.images.all().delete()
                available_colors = list(color_by_name.values())
                for img_idx, img_url in enumerate(p.get('images', [])):
                    clean_img = img_url.lstrip('/').replace('images/', '', 1)
                    img_clothing = 'Standard' if feeding_config == 'none' else 'Feeding'
                    matched_color = None
                    clean_lower = clean_img.lower()
                    for c_name, c_obj in color_by_name.items():
                        if c_name.lower() in clean_lower:
                            matched_color = c_obj
                            break
                    if not matched_color and available_colors:
                        matched_color = available_colors[img_idx % len(available_colors)]

                    ProductImage.objects.create(
                        product=prod,
                        clothing_type=img_clothing,
                        image=clean_img,
                        color=matched_color,
                        order=img_idx,
                        is_primary=(img_idx == 0),
                    )
                    total_images += 1

                # Sizes
                for s_name in p.get('availableSizes', []):
                    Size.objects.get_or_create(
                        name=s_name,
                        defaults={'order': size_order_map.get(s_name, 99)}
                    )

                # Variants
                prod.variants.all().delete()
                for v in p.get('variants', []):
                    color_obj, _ = Color.objects.get_or_create(
                        name=v['color']['name'],
                        defaults={'hex_code': v['color'].get('hex', '#552058')}
                    )
                    size_obj, _ = Size.objects.get_or_create(
                        name=v['size'],
                        defaults={'order': size_order_map.get(v['size'], 99)}
                    )

                    c_type = v.get('clothingType', 'Feeding')
                    if feeding_config == 'none':
                        c_type = 'Standard'
                    elif feeding_config == 'feeding-only':
                        c_type = 'Feeding'
                    elif c_type not in ('Feeding', 'Non-Feeding'):
                        c_type = 'Feeding'

                    sku = v.get('sku') or f"{prod.sku_prefix}-{c_type[:1]}-{color_obj.name[:2]}-{size_obj.name}"
                    v_price = Decimal(str(v.get('price', price)))
                    price_override = v_price if v_price != price else None

                    ProductVariant.objects.create(
                        product=prod,
                        clothing_type=c_type,
                        color=color_obj,
                        size=size_obj,
                        sku=sku,
                        stock=int(v.get('stock', 25)),
                        reserved_stock=0,
                        price_override=price_override,
                    )
                    total_variants += 1

            # 5. Homepage Sections
            sections_config = [
                {
                    'slug': 'feeding-collection',
                    'title': 'Feeding & Non-Feeding',
                    'subtitle': 'Versatile ethnic wear designed for feeding comfort and regular styling',
                    'badge_label': 'Feeding & Regular',
                    'view_all_link': '/shop?section=feeding-collection',
                    'direction': 'left',
                    'display_order': 1,
                },
                {
                    'slug': 'handstock',
                    'title': 'Handstocks',
                    'subtitle': 'Ready to dispatch within 24 hours directly from warehouse',
                    'badge_label': 'Ready to Ship',
                    'view_all_link': '/shop?section=handstock',
                    'direction': 'right',
                    'display_order': 2,
                },
                {
                    'slug': 'sarees',
                    'title': 'Sarees',
                    'subtitle': 'Handloom silk and festive sarees crafted with timeless tradition',
                    'badge_label': 'Pure Silk',
                    'view_all_link': '/shop?section=sarees',
                    'direction': 'left',
                    'display_order': 3,
                },
                {
                    'slug': 'kids-wear',
                    'title': 'Kids Wear',
                    'subtitle': 'Charming ethnic festive frocks and lehengas for little stars',
                    'badge_label': 'Festive',
                    'view_all_link': '/shop?section=kids-wear',
                    'direction': 'right',
                    'display_order': 4,
                },
                {
                    'slug': 'new-arrivals',
                    'title': 'New Arrivals',
                    'subtitle': 'Fresh drops and the latest bridal, festive, and casual additions',
                    'badge_label': 'New',
                    'view_all_link': '/shop?section=new-arrivals',
                    'direction': 'left',
                    'display_order': 5,
                },
                {
                    'slug': 'best-sellers',
                    'title': 'Best Sellers',
                    'subtitle': 'Most-loved ensembles rated by over 1,000 happy mothers',
                    'badge_label': 'Top Rated',
                    'view_all_link': '/shop?section=best-sellers',
                    'direction': 'right',
                    'display_order': 6,
                },
            ]

            for s_cfg in sections_config:
                sec, _ = HomepageSection.objects.update_or_create(
                    slug=s_cfg['slug'],
                    defaults={
                        'title': s_cfg['title'],
                        'subtitle': s_cfg['subtitle'],
                        'badge_label': s_cfg['badge_label'],
                        'view_all_link': s_cfg['view_all_link'],
                        'direction': s_cfg['direction'],
                        'display_order': s_cfg['display_order'],
                        'is_active': True,
                    }
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded {len(products_data)} products, {total_images} gallery images, and {total_variants} product variants!"
                )
            )
