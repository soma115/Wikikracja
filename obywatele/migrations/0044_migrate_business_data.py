from django.db import migrations
from django.db.models import F


def copy_legacy_business(apps, schema_editor):
    Uzytkownik = apps.get_model('obywatele', 'Uzytkownik')
    Uzytkownik.objects.exclude(business__isnull=True).exclude(business='').update(
        business_active=True,
        business_description=F('business'),
    )


def restore_legacy_business(apps, schema_editor):
    Uzytkownik = apps.get_model('obywatele', 'Uzytkownik')
    Uzytkownik.objects.filter(business='').exclude(business_description='').update(
        business=F('business_description'),
    )


class Migration(migrations.Migration):
    dependencies = [
        ('obywatele', '0043_uzytkownik_business_active_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_legacy_business, restore_legacy_business),
    ]
