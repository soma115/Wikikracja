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
    resources = tables.Column(verbose_name=_('Resources'), empty_values=())

    def render_uid(self, record):
        return user_display_name(record.uid)

    def render_business_description(self, record):
        return record.business_description if record.business_active else '—'

    def render_resources(self, record):
        return ', '.join(f'{assignment.item.name} ({assignment.get_kind_display()})' for assignment in record.resource_assignments.all()) or '—'

    class Meta:
        model = Uzytkownik
        fields = ('uid', 'city', 'voivodeship', 'resources', 'want_to_learn', 'business_description', 'job', 'why')
        template_name = "tw/table.html"
        attrs = {'class': 'tw-citizens-table tw-table-hover tw-table-sm tw-align-middle tw-mb-0', 'data-column-toggle': 'true'}
        paginate_by = False
