from django.db import migrations

SECTIONS_DATA = [
    {
        'title': 'Feeding & Non-Feeding',
        'slug': 'feeding-collection',
        'subtitle': 'Thoughtfully Designed for Every Stage of Motherhood',
        'badge_label': 'Feeding & Regular',
        'view_all_link': '/shop?clothingType=Feeding',
        'direction': 'left',
        'display_order': 1,
    },
    {
        'title': 'Handstock',
        'slug': 'handstock',
        'subtitle': 'Ready to Dispatch in 24 Hours • Limited Quantities',
        'badge_label': 'Ready to Ship',
        'view_all_link': '/shop?handstock=true',
        'direction': 'right',
        'display_order': 2,
    },
    {
        'title': 'Sarees',
        'slug': 'sarees',
        'subtitle': 'Timeless Traditional Drapes for Auspicious Moments',
        'badge_label': 'Pure Silk',
        'view_all_link': '/category/sarees',
        'direction': 'left',
        'display_order': 3,
    },
    {
        'title': 'Kids Wear',
        'slug': 'kids-wear',
        'subtitle': 'Adorable Comfort for Little Ones & Festive Celebrations',
        'badge_label': 'Festive',
        'view_all_link': '/category/kids-collections',
        'direction': 'right',
        'display_order': 4,
    },
    {
        'title': 'New Arrivals',
        'slug': 'new-arrivals',
        'subtitle': 'Fresh Designs Straight from Our Master Weavers',
        'badge_label': 'New',
        'view_all_link': '/shop?sort=newest',
        'direction': 'left',
        'display_order': 5,
    },
    {
        'title': 'Best Sellers',
        'slug': 'best-sellers',
        'subtitle': 'Loved by Over 10,000+ Happy Mothers Nationwide',
        'badge_label': 'Best Seller',
        'view_all_link': '/shop?sort=bestseller',
        'direction': 'right',
        'display_order': 6,
    },
]


def seed_sections(apps, schema_editor):
    HomepageSection = apps.get_model('catalog', 'HomepageSection')
    for data in SECTIONS_DATA:
        HomepageSection.objects.get_or_create(
            slug=data['slug'],
            defaults=data,
        )


def unseed_sections(apps, schema_editor):
    HomepageSection = apps.get_model('catalog', 'HomepageSection')
    slugs = [s['slug'] for s in SECTIONS_DATA]
    HomepageSection.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0003_homepagesection_homepagesectionitem'),
    ]

    operations = [
        migrations.RunPython(seed_sections, unseed_sections),
    ]
