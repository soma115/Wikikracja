from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('glosowania', '0021_decyzjawersja'),
    ]

    operations = [
        migrations.AddField(
            model_name='decyzja',
            name='proposed_parameters',
            field=models.JSONField(
                blank=True,
                editable=False,
                help_text='If set, this referendum changes system parameters. Applied when approved.',
                null=True,
                verbose_name='Proposed system parameters',
            ),
        ),
    ]
