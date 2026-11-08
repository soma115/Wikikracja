from datetime import timedelta as td

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Uzytkownik


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widgets for citizens/members."""
    new_people = list(Uzytkownik.objects.filter(uid__is_active=False).select_related('uid').order_by('-uid__date_joined')[:7])

    pop = User.objects.filter(is_active=True).count()
    now = timezone.now()
    green_since = now - td(minutes=settings.PRESENCE_GREEN_MINUTES)
    yellow_since = now - td(days=settings.PRESENCE_YELLOW_DAYS)
    thirty_days_ago = now - td(days=30)
    presence_qs = Uzytkownik.objects.filter(uid__is_active=True)
    active_green = presence_qs.filter(last_presence_at__gte=green_since).count()
    active_yellow = presence_qs.filter(last_presence_at__lt=green_since, last_presence_at__gte=yellow_since).count()
    active_recent = presence_qs.filter(last_presence_at__lt=yellow_since, last_presence_at__gte=thirty_days_ago).count()
    active_last_month = active_green + active_yellow + active_recent
    inactive = pop - active_last_month
    active_pct = round(active_last_month / pop * 100) if pop else 0
    active_green_end_pct = round(active_green / pop * 100) if pop else 0
    active_yellow_end_pct = round((active_green + active_yellow) / pop * 100) if pop else 0
    active_recent_end_pct = active_pct

    skills_knowledge_hobby_count = Uzytkownik.objects.exclude(skills_knowledge_hobby__isnull=True).exclude(skills_knowledge_hobby='').count()

    return {
        'new_people': new_people,
        'active_pct': active_pct,
        'active_last_month': active_last_month,
        'active_green': active_green,
        'active_yellow': active_yellow,
        'active_recent': active_recent,
        'inactive': inactive,
        'active_green_end_pct': active_green_end_pct,
        'active_yellow_end_pct': active_yellow_end_pct,
        'active_recent_end_pct': active_recent_end_pct,
        'population_end_pct': 100 if pop else 0,
        'skills_knowledge_hobby_count': skills_knowledge_hobby_count,
        'skills_count': skills_knowledge_hobby_count,
        'knowledge_count': skills_knowledge_hobby_count,
    }
