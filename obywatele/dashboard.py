from datetime import timedelta as td

from django.contrib.auth.models import User
from django.utils import timezone

from .models import Uzytkownik


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widgets for citizens/members."""
    new_people = list(Uzytkownik.objects.filter(uid__is_active=False).select_related('uid').order_by('-uid__date_joined')[:7])

    pop = User.objects.filter(is_active=True).count()
    thirty_days_ago = timezone.now() - td(days=30)
    active_last_month = User.objects.filter(is_active=True, last_login__gte=thirty_days_ago).count()
    active_pct = round(active_last_month / pop * 100) if pop else 0

    skills_knowledge_hobby_count = Uzytkownik.objects.exclude(skills_knowledge_hobby__isnull=True).exclude(skills_knowledge_hobby='').count()
    give_away_count = Uzytkownik.objects.exclude(to_give_away__isnull=True).exclude(to_give_away='').count()
    borrow_count = Uzytkownik.objects.exclude(to_borrow__isnull=True).exclude(to_borrow='').count()
    for_sale_count = Uzytkownik.objects.exclude(for_sale__isnull=True).exclude(for_sale='').count()

    return {
        'new_people': new_people,
        'active_pct': active_pct,
        'skills_knowledge_hobby_count': skills_knowledge_hobby_count,
        'skills_count': skills_knowledge_hobby_count,
        'knowledge_count': skills_knowledge_hobby_count,
        'give_away_count': give_away_count,
        'borrow_count': borrow_count,
        'for_sale_count': for_sale_count,
    }
