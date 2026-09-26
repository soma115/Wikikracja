from django.db import migrations


LEGACY_FIELDS = (
    ('to_give_away', 'give'),
    ('to_borrow', 'borrow'),
    ('for_sale', 'sale'),
    ('i_need', 'need'),
)


def migrate_legacy_resources(apps, schema_editor):
    Uzytkownik = apps.get_model('obywatele', 'Uzytkownik')
    ResourceItem = apps.get_model('obywatele', 'ResourceItem')
    ResourceAssignment = apps.get_model('obywatele', 'ResourceAssignment')

    for profile in Uzytkownik.objects.select_related('uid').iterator():
        for field_name, kind in LEGACY_FIELDS:
            value = (getattr(profile, field_name) or '').strip()
            if not value:
                continue
            name = value[:200]
            item = ResourceItem.objects.filter(name__iexact=name).first()
            if item is None:
                item = ResourceItem.objects.create(name=name, created_by_id=profile.uid_id)
            ResourceAssignment.objects.get_or_create(profile_id=profile.pk, item_id=item.pk, kind=kind)


class Migration(migrations.Migration):
    dependencies = [
        ('obywatele', '0046_resourceitem_resourceassignment_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_resources, migrations.RunPython.noop),
    ]
