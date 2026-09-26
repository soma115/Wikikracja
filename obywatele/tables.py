import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from obywatele.models import Uzytkownik
from zzz.templatetags.citizen_filters import user_display_name

# https://django-tables2.readthedocs.io/en/latest/pages/filtering.html


class UzytkownikTable(tables.Table):
    uid = tables.Column(accessor='uid', verbose_name=_('Name and surname'), linkify=lambda record: record.get_absolute_url(), order_by=('uid__last_name', 'uid__first_name'))
    voivodeship = tables.Column(accessor='voivodeship__name', verbose_name=_('Voivodeship'), default='—')
    why = tables.Column(verbose_name=_('Why?'))
    business_description = tables.Column(verbose_name=_('Business'))

    def render_uid(self, record):
        return user_display_name(record.uid)

    def render_business_description(self, record):
        return record.business_description if record.business_active else '—'

    class Meta:
        model = Uzytkownik
        fields = ('uid', 'city', 'voivodeship', 'skills_knowledge_hobby', 'to_give_away', 'to_borrow', 'for_sale', 'i_need', 'want_to_learn', 'business_description', 'job', 'why')
        template_name = "tw/table.html"
        attrs = {'class': 'tw-citizens-table tw-table-hover tw-table-sm tw-align-middle tw-mb-0', 'data-column-toggle': 'true'}
        paginate_by = False
