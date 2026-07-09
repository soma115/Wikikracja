from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('glosowania', '0022_decyzja_proposed_parameters'),
    ]

    operations = [
        migrations.AddField(
            model_name='decyzja',
            name='proposed_brand_mark',
            field=models.ImageField(
                blank=True,
                editable=False,
                help_text='If set, this referendum changes the site logo. Applied when approved.',
                null=True,
                upload_to='site_branding/proposed/',
                verbose_name='Proposed logo',
            ),
        ),
    ]
