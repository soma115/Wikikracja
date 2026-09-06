import datetime

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import Argument, Decyzja, KtoJuzGlosowal, ZebranePodpisy


def get_user_activity(user) -> list[dict]:
    items = []

    for arg in Argument.objects.filter(author=user).select_related('decyzja').order_by('-created_at'):
        items.append({'type': 'argument', 'title': arg.decyzja.title, 'ts': arg.created_at, 'label': _('Added argument'), 'url': reverse('glosowania:details', kwargs={'pk': arg.decyzja_id})})

    for zp in ZebranePodpisy.objects.filter(podpis_uzytkownika=user).select_related('projekt'):
        if zp.projekt:
            items.append({'type': 'signature', 'title': zp.projekt.title, 'ts': None, 'label': _('Signed proposal'), 'url': reverse('glosowania:details', kwargs={'pk': zp.projekt_id})})

    for kg in KtoJuzGlosowal.objects.filter(ktory_uzytkownik_juz_zaglosowal=user).select_related('projekt'):
        items.append({'type': 'voted', 'title': kg.projekt.title, 'ts': None, 'label': _('Voted in referendum'), 'url': reverse('glosowania:details', kwargs={'pk': kg.projekt_id})})

    return items


def get_user_created_items(user) -> list[dict]:
    items = []
    for d in Decyzja.objects.filter(author=user).order_by('-data_powstania'):
        items.append(
            {
                'title': d.title or '—',
                'ts': datetime.datetime(d.data_powstania.year, d.data_powstania.month, d.data_powstania.day, tzinfo=datetime.timezone.utc) if d.data_powstania else None,
                'label': _('Voting proposal'),
                'url': reverse('glosowania:details', kwargs={'pk': d.pk}),
            }
        )
    return items
