# Third party imports
from django.test import SimpleTestCase

# Local folder imports
from tasks.views import _compute_priority_map


def task_ids(count):
    return list(range(1, count + 1))


# ---------------------------------------------------------------------------
# _compute_priority_map
# ---------------------------------------------------------------------------
class ComputePriorityMapTest(SimpleTestCase):
    def test_empty_rows(self):
        self.assertEqual(_compute_priority_map([]), {})

    def test_single_task_gets_critical(self):
        m = _compute_priority_map([1])
        self.assertEqual(m[1][1], "critical")

    def test_top_20_percent_get_critical(self):
        m = _compute_priority_map(task_ids(10))
        critical = [task_id for task_id, (_, cat) in m.items() if cat == "critical"]
        self.assertEqual(len(critical), 2)  # ceil(10 * 0.2) = 2
        self.assertEqual(critical, [1, 2])  # pierwsze w kolejności kanonicznej

    def test_next_30_percent_get_important(self):
        # 10 zadań: 2 critical, 3 important, 5 beneficial
        m = _compute_priority_map(task_ids(10))
        important = [task_id for task_id, (_, cat) in m.items() if cat == "important"]
        self.assertEqual(len(important), 3)  # ceil(10 * 0.3) = 3
        self.assertEqual(important, [3, 4, 5])

    def test_remaining_tasks_get_beneficial(self):
        m = _compute_priority_map(task_ids(10))
        beneficial = [task_id for task_id, (_, cat) in m.items() if cat == "beneficial"]
        self.assertEqual(len(beneficial), 5)  # 10 - 2 - 3 = 5

    def test_priority_labels_set_for_all(self):
        m = _compute_priority_map(task_ids(5))
        for label, _cat in m.values():
            self.assertIsNotNone(label)
