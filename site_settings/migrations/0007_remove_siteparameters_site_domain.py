from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('site_settings', '0006_siteparameters'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='SiteParameters',
            name='site_domain',
        ),
    ]
