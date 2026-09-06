from django.db.models import Count, Q

from glosowania.models import Decyzja, author_signed_exists


def get_stepper_counts():
    """Return counts per stepper stage in a single aggregate query.

    discussion/referendum count only items whose author has signed
    (same filter as is_author_signed in the views).
    """
    Status = Decyzja.Status
    return Decyzja.objects.annotate(_signed=author_signed_exists()).aggregate(
        proposition=Count("id", filter=Q(status=Status.PROPOSITION)),
        discussion=Count("id", filter=Q(status=Status.DISCUSSION, _signed=True)),
        referendum=Count("id", filter=Q(status=Status.REFERENDUM, _signed=True)),
        rejected=Count("id", filter=Q(status=Status.REJECTED)),
        approved=Count("id", filter=Q(status=Status.APPROVED)),
    )
