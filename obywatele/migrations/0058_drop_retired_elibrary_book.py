from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('obywatele', '0057_uzytkownik_apartment_number_uzytkownik_country_and_more')]

    operations = [
        # eLibrary was removed from the app registry without dropping its legacy table.
        # A rollback must not recreate this obsolete table or its discarded data.
        migrations.RunSQL('DROP TABLE IF EXISTS "elibrary_book"', reverse_sql=migrations.RunSQL.noop)
    ]
