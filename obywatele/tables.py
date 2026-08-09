import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from obywatele.models import Uzytkownik

# https://django-tables2.readthedocs.io/en/latest/pages/filtering.html


class UzytkownikTable(tables.Table):
    uid = tables.Column(accessor='uid.username', verbose_name=_('Username'), linkify=lambda record: record.get_absolute_url())
    why = tables.Column(verbose_name=_('Why?'))

    class Meta:
        model = Uzytkownik
        fields = ('uid', 'city', 'responsibilities', 'skills_knowledge_hobby', 'to_give_away', 'to_borrow', 'for_sale', 'i_need', 'want_to_learn', 'business', 'job', 'why')
        template_name = "django_tables2/bootstrap5.html"
        attrs = {'class': 'table table-hover table-sm align-middle mb-0', 'data-column-toggle': 'true', 'style': 'table-layout: auto;'}
        paginate_by = False
