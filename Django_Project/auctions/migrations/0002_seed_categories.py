from django.db import migrations


def seed_categories(apps, schema_editor):
    Category = apps.get_model('auctions', 'Category')

    roots = {
        'Electronics': Category.objects.create(name='Electronics', slug='electronics', ordering=1),
        'Fashion': Category.objects.create(name='Fashion', slug='fashion', ordering=2),
        'Home': Category.objects.create(name='Home', slug='home', ordering=3),
        'Collectibles': Category.objects.create(name='Collectibles', slug='collectibles', ordering=4),
        'Art': Category.objects.create(name='Art', slug='art', ordering=5),
        'Vehicles': Category.objects.create(name='Vehicles', slug='vehicles', ordering=6),
    }

    child_categories = [
        ('Phones', 'phones', 'Electronics', 1),
        ('Gaming', 'gaming', 'Electronics', 2),
        ('Watches', 'watches', 'Fashion', 1),
        ('Luxury Bags', 'luxury-bags', 'Fashion', 2),
        ('Furniture', 'furniture', 'Home', 1),
        ('Decor', 'decor', 'Home', 2),
        ('Trading Cards', 'trading-cards', 'Collectibles', 1),
        ('Vintage Toys', 'vintage-toys', 'Collectibles', 2),
        ('Paintings', 'paintings', 'Art', 1),
        ('Photography', 'photography', 'Art', 2),
        ('Cars', 'cars', 'Vehicles', 1),
        ('Motorcycles', 'motorcycles', 'Vehicles', 2),
    ]

    for name, slug, parent_name, ordering in child_categories:
        Category.objects.create(
            name=name,
            slug=slug,
            parent=roots[parent_name],
            ordering=ordering,
        )


def remove_categories(apps, schema_editor):
    Category = apps.get_model('auctions', 'Category')
    Category.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('auctions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, remove_categories),
    ]
