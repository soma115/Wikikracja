from django.contrib.auth.models import User
from django.test import TestCase

from glosowania.models import Decyzja, ZebranePodpisy
from glosowania.stepper import get_stepper_counts


class StepperCountsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(username="alice", password="x")
        cls.bob = User.objects.create_user(username="bob", password="x")

    def _decyzja(self, author, status, signed_by_author=True):
        d = Decyzja.objects.create(author=author, title="t", tresc="x", status=status)
        if signed_by_author:
            ZebranePodpisy.objects.create(projekt=d, podpis_uzytkownika=author)
        return d

    def test_empty_db_returns_zeros(self):
        counts = get_stepper_counts()
        self.assertEqual(counts, {
            "proposition": 0,
            "discussion": 0,
            "referendum": 0,
            "approved": 0,
            "rejected": 0,
        })

    def test_proposition_counts_all_status_1(self):
        self._decyzja(self.alice, status=Decyzja.Status.PROPOSITION, signed_by_author=False)
        self._decyzja(self.bob, status=Decyzja.Status.PROPOSITION, signed_by_author=True)
        self._decyzja(self.alice, status=Decyzja.Status.DISCUSSION, signed_by_author=True)
        counts = get_stepper_counts()
        self.assertEqual(counts["proposition"], 2)

    def test_discussion_counts_only_when_author_signed(self):
        self._decyzja(self.alice, status=Decyzja.Status.DISCUSSION, signed_by_author=True)
        self._decyzja(self.bob, status=Decyzja.Status.DISCUSSION, signed_by_author=True)
        self._decyzja(self.alice, status=Decyzja.Status.DISCUSSION, signed_by_author=False)
        counts = get_stepper_counts()
        self.assertEqual(counts["discussion"], 2)

    def test_referendum_counts_only_when_author_signed(self):
        self._decyzja(self.alice, status=Decyzja.Status.REFERENDUM, signed_by_author=True)
        self._decyzja(self.alice, status=Decyzja.Status.REFERENDUM, signed_by_author=False)
        counts = get_stepper_counts()
        self.assertEqual(counts["referendum"], 1)

    def test_approved_counts_status_5(self):
        self._decyzja(self.alice, status=Decyzja.Status.APPROVED, signed_by_author=False)
        self._decyzja(self.bob, status=Decyzja.Status.APPROVED, signed_by_author=True)
        counts = get_stepper_counts()
        self.assertEqual(counts["approved"], 2)

    def test_rejected_counts_status_4(self):
        self._decyzja(self.alice, status=Decyzja.Status.REJECTED, signed_by_author=False)
        counts = get_stepper_counts()
        self.assertEqual(counts["rejected"], 1)

    def test_rejected_ignores_author_signed_filter(self):
        self._decyzja(self.alice, status=Decyzja.Status.REJECTED, signed_by_author=False)
        self._decyzja(self.bob, status=Decyzja.Status.REJECTED, signed_by_author=True)
        counts = get_stepper_counts()
        self.assertEqual(counts["rejected"], 2)

    def test_discussion_excludes_orphaned_decyzja(self):
        d = Decyzja.objects.create(author=None, title="orphan", tresc="x", status=Decyzja.Status.DISCUSSION)
        ZebranePodpisy.objects.create(projekt=d, podpis_uzytkownika=self.alice)
        counts = get_stepper_counts()
        self.assertEqual(counts["discussion"], 0)
        self.assertEqual(counts["referendum"], 0)

    def test_single_aggregate_query(self):
        for _ in range(3):
            self._decyzja(self.alice, status=Decyzja.Status.PROPOSITION, signed_by_author=False)
            self._decyzja(self.alice, status=Decyzja.Status.DISCUSSION, signed_by_author=True)
        with self.assertNumQueries(1):
            get_stepper_counts()
