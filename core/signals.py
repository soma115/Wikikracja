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

vote_argument_added = Signal()
"""Sent when a new argument is added to a voting proposal.

Provides arguments:
    argument: The Argument instance.
"""


task_created = Signal()
"""Sent when a new task is created.

Provides arguments:
    task: The newly created Task instance.
    url: Absolute URL to the task detail page.
"""

task_helper_joined = Signal()
"""Sent when a user becomes willing to help with a coordinated task.

Provides arguments:
    task: The Task instance.
    helper: The User who became willing to help.
    coordinator_id: The task coordinator's user ID.
"""

task_status_changed = Signal()
"""Sent when a task changes status.

Provides arguments:
    task: The Task instance after the status change.
    previous_status: The previous status value.
"""


document_created = Signal()
"""Sent when a visible document is created.

Provides arguments:
    post: The Post instance.
    url: Absolute URL to the document.
"""


event_created = Signal()
"""Sent when a calendar event is created.

Provides arguments:
    event: The Event instance.
    url: Absolute URL to the event.
"""

event_updated = Signal()
"""Sent when an existing calendar event is edited.

Provides arguments:
    event: The Event instance.
    url: Absolute URL to the event.
"""


transaction_created = Signal()
"""Sent when a financial transaction is created.

Provides arguments:
    transaction: The Transaction instance.
    url: Absolute URL to the transaction.
"""

transaction_updated = Signal()
"""Sent when an existing financial transaction is edited.

Provides arguments:
    transaction: The Transaction instance.
    url: Absolute URL to the transaction.
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

survey_updated = Signal()
"""Sent when an existing survey is edited.

Provides arguments:
    survey: The Survey instance.
    url: Absolute URL to the survey detail page.
"""
