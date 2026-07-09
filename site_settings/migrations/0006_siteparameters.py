from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('site_settings', '0005_remove_sitesettings_onboarding_category_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteParameters',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wymaganych_podpisow', models.PositiveIntegerField(default=2, verbose_name='Required signatures')),
                ('czas_na_zebranie_podpisow', models.PositiveIntegerField(default=365, verbose_name='Time to gather signatures (days)')),
                ('dyskusja', models.PositiveIntegerField(default=3, verbose_name='Discussion period (days)')),
                ('czas_trwania_referendum', models.PositiveIntegerField(default=3, verbose_name='Referendum duration (days)')),
                ('archive_public_chat_room', models.PositiveIntegerField(default=9, verbose_name='Archive public chat room after (days)')),
                ('delete_public_chat_room', models.PositiveIntegerField(default=360, verbose_name='Delete public chat room after (days)')),
                ('acceptance', models.PositiveIntegerField(default=3, verbose_name='Acceptance threshold')),
                ('delete_inactive_user_after', models.PositiveIntegerField(default=30, verbose_name='Delete inactive user after (days)')),
                ('group_is_public', models.BooleanField(default=True, verbose_name='Group is public')),
                ('site_domain', models.CharField(blank=True, default='', max_length=255, verbose_name='Site domain')),
                ('site_name', models.CharField(blank=True, default='', max_length=255, verbose_name='Site name')),
                ('site_name_max_12_chars', models.CharField(blank=True, default='', max_length=12, verbose_name='Short site name (PWA)')),
                ('site_description', models.CharField(blank=True, default='', max_length=500, verbose_name='Site description')),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
            ],
            options={
                'verbose_name': 'Site parameters',
                'verbose_name_plural': 'Site parameters',
            },
        ),
    ]
