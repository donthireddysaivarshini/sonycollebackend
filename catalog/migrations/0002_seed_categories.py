from django.db import migrations

CATEGORIES_DATA = [
    {
        'name': 'Frocks',
        'slug': 'frocks',
        'display_order': 1,
        'image': '/images/frocks/teal-zari-tiered-frock.jpg',
        'item_count_label': 'Tiered & Flared',
        'description': 'Flared tiered frocks designed for ease of movement and everyday comfort.',
        'tagline': 'Effortless Flow & Comfort',
    },
    {
        'name': 'Co-ord Sets',
        'slug': 'co-ord-sets',
        'display_order': 2,
        'image': '/images/co-ords/crimson-botanical-coord.jpg',
        'item_count_label': 'Matching Sets',
        'description': 'Matching ethnic top and trouser pairs tailored for contemporary wear.',
        'tagline': 'Modern Coordinated Style',
    },
    {
        'name': 'Kurti + Dupatta',
        'slug': 'kurti-dupatta',
        'display_order': 3,
        'image': '/images/kurti-dupatta/magenta-ombre-kurti-dupatta.jpg',
        'item_count_label': 'Kurti Sets',
        'description': 'Straight-cut and anarkali kurtis paired with matching lightweight dupattas.',
        'tagline': 'Timeless Everyday Grace',
    },
    {
        'name': '3-Piece Dresses',
        'slug': '3-piece-dresses',
        'display_order': 4,
        'image': '/images/3pc-sets/indigo-blockprint-3pc-set.jpg',
        'item_count_label': 'Complete Sets',
        'description': 'Coordinated three-piece ethnic ensembles including kurti, bottoms, and dupatta.',
        'tagline': 'Curated 3-Piece Ensembles',
    },
    {
        'name': 'Partywear Dresses',
        'slug': 'partywear-dresses',
        'display_order': 5,
        'image': '/images/dresses/crimson-floral-maxi.jpg',
        'item_count_label': 'Gowns & Maxis',
        'description': 'Floor-length maxis and flared gowns crafted for festive and celebration wear.',
        'tagline': 'Celebration Ready Silhouettes',
    },
    {
        'name': 'Sarees',
        'slug': 'sarees',
        'display_order': 6,
        'image': '/images/sarees/emerald-checked-kanchivaram-saree.jpg',
        'item_count_label': 'Traditional Weaves',
        'description': 'Soft silk, linen, and handloom sarees suited for traditional occasions.',
        'tagline': 'Draped in Traditional Heritage',
    },
    {
        'name': 'Lehengas',
        'slug': 'lehengas',
        'display_order': 7,
        'image': '/images/dresses/crimson-floral-maxi.jpg',
        'item_count_label': 'Flared Lehengas',
        'description': 'Bridal and partywear lehengas with rich handwork and delicate dupattas.',
        'tagline': 'Opulent Festive Ensembles',
    },
    {
        'name': 'Kids Collections',
        'slug': 'kids-collections',
        'display_order': 8,
        'image': '/images/kidswear/maroon-pattu-frock.jpg',
        'item_count_label': 'Kids & Twinning',
        'description': 'Comfortable ethnic dresses for little ones and matching mom-child pairs.',
        'tagline': 'Cherished Family Moments',
    },
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    for cat_data in CATEGORIES_DATA:
        Category.objects.get_or_create(
            slug=cat_data['slug'],
            defaults=cat_data,
        )


def unseed_categories(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    slugs = [c['slug'] for c in CATEGORIES_DATA]
    Category.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
