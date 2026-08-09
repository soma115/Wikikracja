# Standard library imports
from datetime import datetime, timezone

# Third party imports
from django.test import SimpleTestCase

# Local folder imports
from tasks.models import Task
from tasks.views import _apply_task_sort, _assign_priorities


def make_annotated_task(title, votes_score, votes_up=0, votes_down=0, status=Task.Status.ACTIVE, updated_at=None, chat_msg_count=0):
    """In-memory Task-like object with annotated fields — nie zapisuje do bazy."""
    task = Task(title=title, description="", status=status)
    task.votes_score = votes_score
    task.votes_up = votes_up
    task.votes_down = votes_down
    task.chat_msg_count = chat_msg_count
    if updated_at:
        task.updated_at = updated_at
        task.created_at = updated_at
    return task


# ---------------------------------------------------------------------------
# _assign_priorities
# ---------------------------------------------------------------------------
class AssignPrioritiesTest(SimpleTestCase):
    def test_empty_list_does_not_crash(self):
        _assign_priorities([])

    def test_single_task_gets_critical(self):
        task = make_annotated_task("T1", votes_score=0)
        _assign_priorities([task])
        self.assertEqual(task.priority_category, "critical")

    def test_score_minus_2_gets_rejected(self):
        task = make_annotated_task("T1", votes_score=-2)
        _assign_priorities([task])
        self.assertEqual(task.priority_category, "rejected")

    def test_score_minus_1_not_rejected(self):
        task = make_annotated_task("T1", votes_score=-1)
        _assign_priorities([task])
        self.assertNotEqual(task.priority_category, "rejected")

    def test_top_20_percent_get_critical(self):
        tasks = [make_annotated_task(f"T{i}", votes_score=0) for i in range(10)]
        _assign_priorities(tasks)
        critical = [t for t in tasks if t.priority_category == "critical"]
        self.assertEqual(len(critical), 2)  # ceil(10 * 0.2) = 2

    def test_next_30_percent_get_important(self):
        # 10 zadań: 2 critical, 3 important, 5 beneficial
        tasks = [make_annotated_task(f"T{i}", votes_score=0) for i in range(10)]
        _assign_priorities(tasks)
        important = [t for t in tasks if t.priority_category == "important"]
        self.assertEqual(len(important), 3)  # ceil(10 * 0.3) = 3

    def test_remaining_tasks_get_beneficial(self):
        tasks = [make_annotated_task(f"T{i}", votes_score=0) for i in range(10)]
        _assign_priorities(tasks)
        beneficial = [t for t in tasks if t.priority_category == "beneficial"]
        self.assertEqual(len(beneficial), 5)  # 10 - 2 - 3 = 5

    def test_priority_labels_set_for_all(self):
        tasks = [make_annotated_task(f"T{i}", votes_score=0) for i in range(5)]
        _assign_priorities(tasks)
        for task in tasks:
            self.assertIsNotNone(task.priority_label)

    def test_all_rejected_tasks_only_rejected(self):
        tasks = [make_annotated_task(f"T{i}", votes_score=-2) for i in range(3)]
        _assign_priorities(tasks)
        for task in tasks:
            self.assertEqual(task.priority_category, "rejected")

    def test_mixed_rejected_and_non_rejected(self):
        good = make_annotated_task("Good", votes_score=0)
        bad = make_annotated_task("Bad", votes_score=-2)
        _assign_priorities([good, bad])
        self.assertEqual(good.priority_category, "critical")
        self.assertEqual(bad.priority_category, "rejected")


# ---------------------------------------------------------------------------
# _apply_task_sort
# ---------------------------------------------------------------------------
class ApplyTaskSortTest(SimpleTestCase):
    def setUp(self):
        self.t1 = make_annotated_task("A", votes_score=5, votes_up=5, updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc), chat_msg_count=10)
        self.t2 = make_annotated_task("B", votes_score=1, votes_up=1, updated_at=datetime(2024, 6, 1, tzinfo=timezone.utc), chat_msg_count=2)
        self.tasks = [self.t1, self.t2]

    def test_sort_by_date_desc(self):
        result = _apply_task_sort(self.tasks, "date", "desc")
        self.assertEqual(result[0], self.t2)

    def test_sort_by_date_asc(self):
        result = _apply_task_sort(self.tasks, "date", "asc")
        self.assertEqual(result[0], self.t1)

    def test_sort_by_score_desc(self):
        result = _apply_task_sort(self.tasks, "score", "desc")
        self.assertEqual(result[0], self.t1)

    def test_sort_by_score_asc(self):
        result = _apply_task_sort(self.tasks, "score", "asc")
        self.assertEqual(result[0], self.t2)

    def test_sort_by_score_uses_votes_up_not_votes_score(self):
        # 'Poparcie' = liczba helpers (votes_up); głosy sprzeciwu nie obniżają
        # rankingu zadania — są osobnym sygnałem (próg rejection).
        # Bez tego zabezpieczenia zadanie z mniejszą liczbą helpers, ale lepszym
        # netto, byłoby wyżej — co myli usera widzącego tylko liczbę helpers.
        more_helpers_some_against = make_annotated_task("A", votes_score=2, votes_up=5)
        fewer_helpers_no_against = make_annotated_task("B", votes_score=3, votes_up=3)
        result = _apply_task_sort([more_helpers_some_against, fewer_helpers_no_against], "score", "desc")
        self.assertEqual(result[0].title, "A")

    def test_sort_by_buzz_desc(self):
        result = _apply_task_sort(self.tasks, "buzz", "desc")
        self.assertEqual(result[0], self.t1)

    def test_sort_by_buzz_asc(self):
        result = _apply_task_sort(self.tasks, "buzz", "asc")
        self.assertEqual(result[0], self.t2)

    def test_unknown_sort_returns_unchanged(self):
        result = _apply_task_sort(self.tasks, "unknown", "desc")
        self.assertEqual(result, self.tasks)
