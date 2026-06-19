from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('obywatele', '0021_deletionrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='deletionrequest',
            name='reason',
            field=models.TextField(blank=True, null=True, verbose_name='Reason for deletion'),
        ),
    ]
