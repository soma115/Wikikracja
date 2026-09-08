import django_filters

from obywatele.models import Uzytkownik

# https://django-filter.readthedocs.io/en/main/guide/usage.html


class UzytkownikFilter(django_filters.FilterSet):
    # city = django_filters.CharFilter(method='custom_filter')
    city = django_filters.CharFilter(lookup_expr='icontains')
    responsibilities = django_filters.CharFilter(lookup_expr='icontains')
    hobby = django_filters.CharFilter(lookup_expr='icontains')
    to_give_away = django_filters.CharFilter(lookup_expr='icontains')
    to_borrow = django_filters.CharFilter(lookup_expr='icontains')
    for_sale = django_filters.CharFilter(lookup_expr='icontains')
    i_need = django_filters.CharFilter(lookup_expr='icontains')
    skills = django_filters.CharFilter(lookup_expr='icontains')
    knowledge = django_filters.CharFilter(lookup_expr='icontains')
    want_to_learn = django_filters.CharFilter(lookup_expr='icontains')
    business = django_filters.CharFilter(lookup_expr='icontains')
    job = django_filters.CharFilter(lookup_expr='icontains')
    other = django_filters.CharFilter(lookup_expr='icontains')
    why = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Uzytkownik
        fields = ['city', 'responsibilities', 'hobby', 'to_give_away', 'to_borrow', 'for_sale', 'i_need', 'skills', 'knowledge', 'want_to_learn', 'business', 'job', 'other', 'why']
