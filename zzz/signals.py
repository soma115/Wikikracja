from django.dispatch import Signal

citizen_proposed = Signal()
"""Sent when a new person requests membership or is proposed by an existing citizen.

Provides arguments:
    candidate: The User being proposed.
    proposed_by: The User who proposed them, or None for self-registration.
"""

citizen_accepted = Signal()
"""Sent when an inactive candidate becomes an active citizen.

Provides arguments:
    user: The newly activated User.
"""

citizen_blocked = Signal()
"""Sent when a citizen loses active status because of insufficient reputation.

Provides arguments:
    user: The blocked User.
"""

citizen_deleted = Signal()
"""Sent when a user is deleted (request or inactivity cleanup).

Provides arguments:
    user: The User being deleted.
"""


vote_started = Signal()
"""Sent when a referendum/discussion transitions to voting phase.

Provides arguments:
    decyzja: The Decyzja instance entering the voting phase.
"""

vote_state_changed = Signal()
"""Sent when a Decyzja changes state and a notification is required.

Provides arguments:
    decyzja: The Decyzja instance that changed state.
    transition: One of 'proposed', 'modified', 'discussion_started',
        'started', 'approved', 'rejected', 'last_day', 'buffer_restart',
        'rejected_no_signatures'.
"""


task_created = Signal()
"""Sent when a new task is created.

Provides arguments:
    task: The newly created Task instance.
    url: Absolute URL to the task detail page.
"""


important_post_published = Signal()
"""Sent when a board post is marked as important (new or updated).

Provides arguments:
    post: The Post instance.
    url: Absolute URL to the post.
    created: Whether the post is newly created or updated.
"""


event_starting = Signal()
"""Sent when an event is about to start.

Provides arguments:
    event: The Event instance.
    body: Optional pre-computed body text.
"""


survey_created = Signal()
"""Sent when a new survey is created.

Provides arguments:
    survey: The Survey instance.
    url: Absolute URL to the survey detail page.
"""
