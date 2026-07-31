from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('site_settings', '0007_remove_siteparameters_site_domain'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='SiteSettings',
            name='branding_text',
        ),
        migrations.RemoveField(
            model_name='SiteSettings',
            name='brand_mark_dark',
        ),
    ]
