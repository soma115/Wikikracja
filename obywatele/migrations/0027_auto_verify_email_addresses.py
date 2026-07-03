from django.db import migrations


def create_and_verify_email_addresses(apps, schema_editor):
    """
    Tworzy brakujące rekordy EmailAddress dla aktywnych użytkowników
    i ustawia verified=True dla niepotwierdzonych rekordów.

    To naprawia problem, gdzie AllAuth tworzy EmailAddress z verified=False
    przy logowaniu użytkowników, którzy nie mają rekordu EmailAddress.
    """
    User = apps.get_model('auth', 'User')
    EmailAddress = apps.get_model('account', 'EmailAddress')

    # 1. Tworzy brakujące EmailAddress dla aktywnych użytkowników
    created_count = 0
    for user in User.objects.filter(is_active=True):
        email_address, created = EmailAddress.objects.get_or_create(
            user=user,
            email=user.email,
            defaults={
                'verified': True,
                'primary': True
            }
        )
        if created:
            created_count += 1

    # 2. Ustawia verified=True dla niepotwierdzonych EmailAddress aktywnych użytkowników
    updated_count = EmailAddress.objects.filter(
        user__is_active=True,
        verified=False
    ).update(verified=True)

    print(f"Created {created_count} EmailAddress records for active users")
    print(f"Updated {updated_count} EmailAddress records to verified=True")


class Migration(migrations.Migration):
    dependencies = [
        ('obywatele', '0026_remove_uzytkownik_gift_remove_uzytkownik_hobby_and_more'),
        ('account', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_and_verify_email_addresses),
    ]
