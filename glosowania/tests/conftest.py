"""Fixtures for glosowania tests."""
import pytest
from tests.factories import UserFactory


@pytest.fixture
def sample_users(db):
    """5 testowych userów."""
    return UserFactory.create_batch(5)
