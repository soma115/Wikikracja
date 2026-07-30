# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('obywatele', '0028_uzytkownik_push_notifications'),
    ]

    operations = [
        migrations.AddField(
            model_name='uzytkownik',
            name='email_notifications_events',
            field=models.BooleanField(default=True, help_text='Receive notifications about events', verbose_name='Event notifications'),
        ),
        migrations.AddField(
            model_name='uzytkownik',
            name='push_notifications_events',
            field=models.BooleanField(default=True, help_text='Receive push notifications about events', verbose_name='Push event notifications'),
        ),
    ]
