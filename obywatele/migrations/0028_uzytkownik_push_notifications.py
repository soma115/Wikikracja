# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('obywatele', '0027_auto_verify_email_addresses'),
    ]

    operations = [
        migrations.AddField(
            model_name='uzytkownik',
            name='push_notifications_chat',
            field=models.BooleanField(default=True, help_text='Receive push notifications about new chat messages', verbose_name='Push chat notifications'),
        ),
        migrations.AddField(
            model_name='uzytkownik',
            name='push_notifications_glosowania',
            field=models.BooleanField(default=True, help_text='Receive push notifications about law proposals and voting', verbose_name='Push voting notifications'),
        ),
        migrations.AddField(
            model_name='uzytkownik',
            name='push_notifications_obywatele',
            field=models.BooleanField(default=True, help_text='Receive push notifications about new citizens and membership requests', verbose_name='Push citizenship notifications'),
        ),
    ]
