from django.db import migrations


def populate_countries_and_regions(apps, schema_editor):
    Country = apps.get_model('obywatele', 'Country')
    Region = apps.get_model('obywatele', 'Region')
    Uzytkownik = apps.get_model('obywatele', 'Uzytkownik')

    # Create Poland
    poland, created = Country.objects.get_or_create(
        code='PL',
        defaults={'name': 'Poland'}
    )

    # Polish voivodeships mapping (old choice value -> region name)
    voivodeship_mapping = {
        'dolnoslaskie': 'Dolnośląskie',
        'kujawsko_pomorskie': 'Kujawsko-Pomorskie',
        'lubelskie': 'Lubelskie',
        'lubuskie': 'Lubuskie',
        'lodzkie': 'Łódzkie',
        'malopolskie': 'Małopolskie',
        'mazowieckie': 'Mazowieckie',
        'opolskie': 'Opolskie',
        'podkarpackie': 'Podkarpackie',
        'podlaskie': 'Podlaskie',
        'pomorskie': 'Pomorskie',
        'slaskie': 'Śląskie',
        'swietokrzyskie': 'Świętokrzyskie',
        'warminsko_mazurskie': 'Warmińsko-Mazurskie',
        'wielkopolskie': 'Wielkopolskie',
        'zachodniopomorskie': 'Zachodniopomorskie',
    }

    # Create regions and build reverse mapping
    region_map = {}
    for old_value, region_name in voivodeship_mapping.items():
        region, _ = Region.objects.get_or_create(
            country=poland,
            name=region_name
        )
        region_map[old_value] = region

    # Migrate existing users
    for user in Uzytkownik.objects.all():
        # Get the old voivodeship value from the database directly
        # Since the field has been changed to ForeignKey, we need to check if there's
        # any data that needs migration. In this case, since this is a fresh migration
        # after the field change, existing users will have NULL values.
        # This migration is primarily for setting up the initial data.
        pass


class Migration(migrations.Migration):
    dependencies = [
        ('obywatele', '0024_country_region_alter_uzytkownik_voivodeship'),
    ]

    operations = [
        migrations.RunPython(populate_countries_and_regions),
    ]
