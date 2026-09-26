import django_filters

from obywatele.models import Uzytkownik

# https://django-filter.readthedocs.io/en/main/guide/usage.html


class UzytkownikFilter(django_filters.FilterSet):
    # city = django_filters.CharFilter(method='custom_filter')
    city = django_filters.CharFilter(lookup_expr='icontains')
    hobby = django_filters.CharFilter(lookup_expr='icontains')
    resources = django_filters.CharFilter(method='filter_resources')
    skills = django_filters.CharFilter(lookup_expr='icontains')
    knowledge = django_filters.CharFilter(lookup_expr='icontains')
    want_to_learn = django_filters.CharFilter(lookup_expr='icontains')
    business_description = django_filters.CharFilter(lookup_expr='icontains')
    job = django_filters.CharFilter(lookup_expr='icontains')
    other = django_filters.CharFilter(lookup_expr='icontains')
    why = django_filters.CharFilter(lookup_expr='icontains')

    def filter_resources(self, queryset, name, value):
        return queryset.filter(resource_assignments__item__name__icontains=value).distinct()

    class Meta:
        model = Uzytkownik
        fields = ['city', 'hobby', 'resources', 'skills', 'knowledge', 'want_to_learn', 'business_description', 'job', 'other', 'why']
