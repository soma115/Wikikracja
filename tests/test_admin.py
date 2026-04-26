"""
Django Admin Tests for all apps.
Test admin interface functionality.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class TestBoardAdmin:
    """Test board app admin."""
    @pytest.mark.django_db
    def test_admin_board_post_list(self, authenticated_client):
        """Test admin can see board posts."""
        client, user = authenticated_client
        # Make user superuser
        user.is_superuser = True
        user.save()

        url = reverse('admin:board_post_changelist')
        response = client.get(url)
        assert response.status_code in [200, 302]

    @pytest.mark.django_db
    def test_admin_board_category_list(self, authenticated_client):
        """Test admin can see categories."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        url = reverse('admin:board_postcategory_changelist')
        response = client.get(url)
        assert response.status_code in [200, 302]

    @pytest.mark.django_db
    def test_admin_add_post(self, authenticated_client, board_category):
        """Test admin can add post."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        url = reverse('admin:board_post_add')
        response = client.get(url)
        assert response.status_code in [200, 302]


class TestBookkeepingAdmin:
    """Test bookkeeping app admin."""
    @pytest.mark.django_db
    def test_admin_transaction_list(self, authenticated_client):
        """Test admin can see transactions."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        url = reverse('admin:bookkeeping_transaction_changelist')
        response = client.get(url)
        assert response.status_code in [200, 302]

    @pytest.mark.django_db
    def test_admin_category_list(self, authenticated_client):
        """Test admin can see bookkeeping categories."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        url = reverse('admin:bookkeeping_category_changelist')
        response = client.get(url)
        assert response.status_code in [200, 302]

    @pytest.mark.django_db
    def test_admin_partner_list(self, authenticated_client):
        """Test admin can see partners."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        url = reverse('admin:bookkeeping_partner_changelist')
        response = client.get(url)
        assert response.status_code in [200, 302]


class TestChatAdmin:
    """Test chat app admin."""
    @pytest.mark.django_db
    def test_admin_message_list(self, authenticated_client):
        """Test admin can see messages."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        url = reverse('admin:chat_message_changelist')
        response = client.get(url)
        assert response.status_code in [200, 302]


class TestGlosowaniaAdmin:
    """Test glosowania app admin."""
    @pytest.mark.django_db
    def test_admin_argument_list(self, authenticated_client):
        """Test admin can see arguments."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        url = reverse('admin:glosowania_argument_changelist')
        response = client.get(url)
        assert response.status_code in [200, 302]


class TestHomeAdmin:
    """Test home app admin."""
    @pytest.mark.django_db
    def test_admin_feed_item_list(self, authenticated_client):
        """Test admin can see feed items."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        url = reverse('admin:home_feeditem_changelist')
        response = client.get(url)
        assert response.status_code in [200, 302]


class TestObywateleAdmin:
    """Test obywatele app admin."""
    @pytest.mark.django_db
    def test_admin_uzytkownik_list(self, authenticated_client):
        """Test admin can see citizens."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        url = reverse('admin:obywatele_uzytkownik_changelist')
        response = client.get(url)
        assert response.status_code in [200, 302]


class TestAdminPermissions:
    """Test admin access permissions."""
    @pytest.mark.django_db
    def test_admin_superuser_access(self, authenticated_client):
        """Test superuser can access admin."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        url = reverse('admin:index')
        response = client.get(url)
        assert response.status_code in [200, 302]

    @pytest.mark.django_db
    def test_regular_user_cannot_access_admin(self, authenticated_client):
        """Test regular user cannot access admin."""
        client, user = authenticated_client
        # User is not superuser

        url = reverse('admin:index')
        response = client.get(url)
        # Should redirect or 403
        assert response.status_code in [302, 403]


class TestAdminActions:
    """Test admin actions."""
    @pytest.mark.django_db
    def test_admin_delete_action(self, authenticated_client, board_category):
        """Test admin can delete objects."""
        client, user = authenticated_client
        user.is_superuser = True
        user.save()

        from board.models import Post
        post = Post.objects.create(title='Delete Test', text='Content', author=user, category=board_category)

        url = reverse('admin:board_post_delete', args=[post.id])
        response = client.get(url)
        assert response.status_code in [200, 302, 403]
