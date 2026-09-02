from django.utils import timezone

from .models import Decyzja, KtoJuzGlosowal


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widgets for voting/referendums."""
    ongoing_count = Decyzja.objects.filter(status=Decyzja.Status.REFERENDUM).count()
    upcoming_count = Decyzja.objects.filter(status=Decyzja.Status.DISCUSSION).count()
    signatures_count = Decyzja.objects.filter(status=Decyzja.Status.PROPOSITION).count()

    new_proposals = Decyzja.objects.filter(status=Decyzja.Status.PROPOSITION).select_related('author').order_by('-data_ostatniej_modyfikacji')[:3]

    discussed_proposals = Decyzja.objects.filter(status=Decyzja.Status.DISCUSSION).select_related('author').order_by('-data_ostatniej_modyfikacji')[:3]

    active_referendum = None
    referendum_obj = Decyzja.objects.filter(status=Decyzja.Status.REFERENDUM).select_related('author').order_by('-data_referendum_start').first()

    if referendum_obj and referendum_obj.data_referendum_start and referendum_obj.data_referendum_stop:
        today = timezone.now().date()
        days_remaining = max(0, (referendum_obj.data_referendum_stop - today).days)
        total_days = max(1, (referendum_obj.data_referendum_stop - referendum_obj.data_referendum_start).days)
        time_pct = min(100, round(days_remaining / total_days * 100))

        if time_pct > 50:
            bar_color = 'success'
        elif time_pct >= 20:
            bar_color = 'warning'
        else:
            bar_color = 'danger'

        user_voted = KtoJuzGlosowal.objects.filter(projekt=referendum_obj, ktory_uzytkownik_juz_zaglosowal=user).exists()

        active_referendum = {'obj': referendum_obj, 'days_remaining': days_remaining, 'total_days': total_days, 'time_pct': time_pct, 'bar_color': bar_color, 'user_voted': user_voted}

    return {
        'ongoing_count': ongoing_count,
        'upcoming_count': upcoming_count,
        'signatures_count': signatures_count,
        'new_proposals': new_proposals,
        'discussed_proposals': discussed_proposals,
        'active_referendum': active_referendum,
    }


def get_site_admin_context(user) -> dict:
    """Return site-admin-specific context for voting restarts."""
    restarted_referendums = Decyzja.objects.filter(referendum_restart_count__gt=0).order_by('-referendum_restart_count')
    total_referendum_restarts = sum(d.referendum_restart_count for d in restarted_referendums)

    return {'restarted_referendums': restarted_referendums, 'total_referendum_restarts': total_referendum_restarts}
