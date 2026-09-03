"""Send email activity digests to users whose digest frequency is due."""

import html
import logging
from datetime import datetime
from datetime import timedelta as td

from django.conf import settings as s
from django.contrib.auth import get_user_model
from django.template.defaultfilters import linebreaksbr
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import escape, mark_safe
from django.utils.translation import gettext_lazy as _

from home.services.feed import build_user_digest
from home.templatetags.feed_filters import content_type_label
from zzz.email import send_bulk_email_in_thread
from zzz.management.base_command import TranslatedCommand
from zzz.richtext import strip_tags
from zzz.utils import build_site_url, get_site_domain

log = logging.getLogger(__name__)

DIGEST_SEND_HOUR = 8
DIGEST_SEND_MINUTE = 0


def _period_start(now: datetime, frequency: str) -> datetime:
    """Return the start of the current digest period at 08:00 local time."""
    base = now.replace(hour=DIGEST_SEND_HOUR, minute=DIGEST_SEND_MINUTE, second=0, microsecond=0)
    if frequency == 'daily':
        return base
    if frequency == 'weekly':
        return base - td(days=base.weekday())
    if frequency == 'monthly':
        return base.replace(day=1)
    return base


def _is_digest_due(profile, now: datetime) -> bool:
    """Check whether the user is due for a digest at the given time."""
    if profile.email_frequency == 'never':
        return False

    period_start = _period_start(now, profile.email_frequency)
    if now < period_start:
        return False

    last = profile.last_email_digest_at
    return not last or last < period_start


def _format_timestamp(ts: datetime) -> str:
    """Format a digest item timestamp; include year when it differs from now."""
    if not ts:
        return ''
    now = timezone.now()
    fmt = '%d.%m.%Y %H:%M' if ts.year != now.year else '%d.%m %H:%M'
    return ts.strftime(fmt)


def _build_sections_html(sections: list[dict]) -> str:
    """Build the inner HTML for all digest sections as a marked-safe string."""
    parts = []
    for section in sections:
        parts.append(f'<h2 class="email-section-title">{escape(section["label"])}</h2>')
        for item in section['items']:
            parts.append('<div class="email-item">')
            parts.append(f'<a class="email-item-title" href="{escape(item["url"])}">{escape(item["title"])}</a>')
            parts.append(f'<span class="email-item-meta">&nbsp;[{escape(item["timestamp"])}]</span>')
            if item['meta']:
                parts.append(f'<span class="email-item-count">&nbsp;({escape(item["meta"])})</span>')
            if item['description_html']:
                parts.append(f'<p class="email-item-desc">{item["description_html"]}</p>')
            parts.append('</div>')
    return mark_safe(''.join(parts))


class Command(TranslatedCommand):
    help = 'Send email activity digests to users whose frequency is due'

    def run(self, *args, **options):
        User = get_user_model()
        now = timezone.localtime(timezone.now())

        profiles = User.objects.filter(is_active=True, uzytkownik__isnull=False).select_related('uzytkownik').exclude(uzytkownik__email_frequency='never').order_by('id')

        sent = 0
        skipped = 0

        for user in profiles:
            profile = user.uzytkownik

            if not _is_digest_due(profile, now):
                continue

            items = build_user_digest(user, profile.last_email_digest_at or now)

            if not items:
                profile.last_email_digest_at = now
                profile.save(update_fields=['last_email_digest_at'])
                skipped += 1
                log.info(f'No digest items for user {user.id}; skipping')
                continue

            context = self._build_digest_context(user, items)
            subject = _('[{HOST}] Activity digest').format(HOST=self.host)
            text = render_to_string('emails/digest.txt', context)
            html = render_to_string('emails/digest.html', context)

            try:
                send_bulk_email_in_thread(
                    [user.email], subject, text, html_message=html, fail_silently=True, sleep_before=0, per_recipient_sleep=s.EMAIL_SEND_DELAY_SECONDS, raise_on_error=False, daemon=False
                ).join()

                profile.last_email_digest_at = now
                profile.save(update_fields=['last_email_digest_at'])

                sent += 1
                log.info(f'Sent digest to user {user.id} ({user.email}); {len(items)} items')
            except Exception as e:
                log.error(f'Failed to send digest to user {user.id}: {e}', exc_info=True)

        log.info(f'Digest run finished: sent={sent}, skipped={skipped}, now={now}')

    def _build_digest_context(self, user, items):
        since_dt = user.uzytkownik.last_email_digest_at
        since_str = since_dt.strftime('%d.%m.%Y %H:%M') if since_dt else '-'

        by_type = {}
        for item in items:
            by_type.setdefault(item['content_type'], []).append(item)

        sections = []
        for content_type, type_items in by_type.items():
            section = {'label': str(content_type_label(content_type)), 'items': []}
            for item in type_items:
                title = item['title'] or '—'
                author = item.get('author')
                if author:
                    title = f'{title} — {author.username}'

                update_count = item.get('update_count', 1)
                meta = ''
                if content_type == 'room_messages' and update_count > 1:
                    meta = f'{update_count} {_("messages")}'
                elif update_count > 1:
                    meta = f'{update_count} {_("updates")}'

                description = html.unescape(strip_tags(item.get('description') or '')).strip()

                section['items'].append(
                    {
                        'title': title,
                        'url': build_site_url(item['url']),
                        'timestamp': _format_timestamp(item.get('timestamp')),
                        'description': description,
                        'description_html': linebreaksbr(description) if description else '',
                        'meta': meta,
                    }
                )
            sections.append(section)

        return {
            'user': user,
            'site_name': get_site_domain(),
            'title': _('Activity digest'),
            'digest_intro': _('Activity digest for %(username)s since %(date)s') % {'username': user.username, 'date': since_str},
            'no_activity_text': _('No activity in this section.'),
            'manage_button_text': _('Manage email notifications'),
            'manage_text': _('You can manage your email notifications here:'),
            'since': since_str,
            'settings_url': build_site_url('/obywatele/settings/'),
            'sections': sections,
            'sections_html': _build_sections_html(sections),
        }
