# Generated manually - data migration to add sample quick links

from django.db import migrations


def add_sample_quick_links(apps, schema_editor):
    QuickLink = apps.get_model('site_settings', 'QuickLink')
    
    sample_links = [
        {
            'title': 'Weź udział w dyskusji',
            'url': '/chat/',
            'icon': 'fa-comments',
            'order': 2,
        },
        {
            'title': 'Podejmi się wykonania Zadania',
            'url': '/tasks/',
            'icon': 'fa-tasks',
            'order': 4,
        },
        {
            'title': 'Zagłosuj albo stwórz przepis',
            'url': '/glosowania/',
            'icon': 'fa-vote-yea',
            'order': 3,
        },
        {
            'title': 'Weź udział w Wydarzeniu',
            'url': '/events/',
            'icon': 'fa-calendar',
            'order': 5,
        },
        {
            'title': 'Przeczytaj nasze Dokumenty',
            'url': '/board/',
            'icon': 'fa-book',
            'order': 1,
        },
    ]
    
    for link_data in sample_links:
        QuickLink.objects.get_or_create(
            url=link_data['url'],
            defaults=link_data
        )


class Migration(migrations.Migration):
    dependencies = [
        ('site_settings', '0003_quicklink'),
    ]

    operations = [
        migrations.RunPython(add_sample_quick_links),
    ]
