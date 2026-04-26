"""
Factory_Boy factories for all models.
Use these factories to create test data more efficiently.
"""
import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for User model."""
    class Meta:
        model = User

    username = factory.Sequence(lambda n: 'user_{}'.format(n))
    email = factory.Sequence(lambda n: 'user{0}@example.com'.format(n))
    is_staff = False
    is_superuser = False


class AdminUserFactory(DjangoModelFactory):
    """Factory for admin User."""
    class Meta:
        model = User

    username = factory.Sequence(lambda n: 'admin_{}'.format(n))
    email = factory.Sequence(lambda n: 'admin{0}@example.com'.format(n))
    is_staff = True
    is_superuser = True


class PostCategoryFactory(DjangoModelFactory):
    """Factory for board.PostCategory."""
    class Meta:
        model = 'board.PostCategory'

    name = factory.Sequence(lambda n: 'Category {0}'.format(n))
    priority = factory.Sequence(lambda n: n % 10 + 1)


class PostFactory(DjangoModelFactory):
    """Factory for board.Post."""
    class Meta:
        model = 'board.Post'

    title = factory.Sequence(lambda n: 'Post {0}'.format(n))
    subtitle = factory.Sequence(lambda n: 'Subtitle {0}'.format(n))
    text = factory.Sequence(lambda n: '<p>Content {0}</p>'.format(n))
    is_public = True
    is_archived = False
    is_important = False

    author = factory.SubFactory(UserFactory)
    category = factory.SubFactory(PostCategoryFactory)


class CategoryFactory(DjangoModelFactory):
    """Factory for bookkeeping.Category."""
    class Meta:
        model = 'bookkeeping.Category'

    name = factory.Sequence(lambda n: 'BK Category {0}'.format(n))


class PartnerFactory(DjangoModelFactory):
    """Factory for bookkeeping.Partner."""
    class Meta:
        model = 'bookkeeping.Partner'

    name = factory.Sequence(lambda n: 'Partner {0}'.format(n))
    email = factory.Sequence(lambda n: 'partner{0}@example.com'.format(n))
    phone = '+48123456789'
    city = 'Warsaw'
    country = 'Poland'


class TransactionFactory(DjangoModelFactory):
    """Factory for bookkeeping.Transaction."""
    class Meta:
        model = 'bookkeeping.Transaction'

    type = 'I'
    amount = 100.00
    note = factory.Sequence(lambda n: 'Transaction {0}'.format(n))
    created_date = factory.LazyFunction(lambda: __import__('django.utils').utils.timezone.now().date())
    payment_received_date = factory.LazyFunction(lambda: __import__('django.utils').utils.timezone.now().date())

    author = factory.SubFactory(UserFactory)
    category = factory.SubFactory(CategoryFactory)
    partner = factory.SubFactory(PartnerFactory)


class RoomFactory(DjangoModelFactory):
    """Factory for chat.Room."""
    class Meta:
        model = 'chat.Room'

    title = factory.Sequence(lambda n: 'Room {0}'.format(n))
    public = True
    archived = False
    protected = False


class MessageFactory(DjangoModelFactory):
    """Factory for chat.Message."""
    class Meta:
        model = 'chat.Message'

    text = factory.Sequence(lambda n: 'Message {0}'.format(n))
    anonymous = False
    reactions = {}

    sender = factory.SubFactory(UserFactory)
    room = factory.SubFactory(RoomFactory)


class BookFactory(DjangoModelFactory):
    """Factory for elibrary.Book."""
    class Meta:
        model = 'elibrary.Book'

    title = factory.Sequence(lambda n: 'Book {0}'.format(n))
    author = factory.Sequence(lambda n: 'Author {0}'.format(n % 10))
    abstract = factory.Sequence(lambda n: 'Abstract {0}'.format(n))

    uploader = factory.SubFactory(UserFactory)


class EventFactory(DjangoModelFactory):
    """Factory for events.Event."""
    class Meta:
        model = 'events.Event'

    title = factory.Sequence(lambda n: 'Event {0}'.format(n))
    description = factory.Sequence(lambda n: 'Description {0}'.format(n))
    place = 'Online'
    frequency = 'once'
    is_active = True
    is_public = True


class DecyzjaFactory(DjangoModelFactory):
    """Factory for glosowania.Decyzja."""
    class Meta:
        model = 'glosowania.Decyzja'

    title = factory.Sequence(lambda n: 'Bill {0}'.format(n))
    tresc = factory.Sequence(lambda n: 'Law text {0}'.format(n))
    kara = factory.Sequence(lambda n: 'Penalty {0}'.format(n))
    uzasadnienie = factory.Sequence(lambda n: 'Reasoning {0}'.format(n))
    ile_osob_podpisalo = 0
    za = 0
    przeciw = 0
    status = 1

    author = factory.SubFactory(UserFactory)
    chat_room = factory.SubFactory(RoomFactory)


class ArgumentFactory(DjangoModelFactory):
    """Factory for glosowania.Argument."""
    class Meta:
        model = 'glosowania.Argument'

    content = factory.Sequence(lambda n: 'Argument content {0}'.format(n))
    argument_type = 'FOR'

    decyzja = factory.SubFactory(DecyzjaFactory)
    author = factory.SubFactory(UserFactory)


class FeedItemFactory(DjangoModelFactory):
    """Factory for home.FeedItem."""
    class Meta:
        model = 'home.FeedItem'

    title = factory.Sequence(lambda n: 'Feed Item {0}'.format(n))
    description = factory.Sequence(lambda n: 'Description {0}'.format(n))
    content_type = 'post'
    object_id = factory.Sequence(lambda n: n)
    url = factory.LazyAttribute(lambda o: '/item/{0}'.format(o.object_id))

    author = factory.SubFactory(UserFactory)


class UzytkownikFactory(DjangoModelFactory):
    """Factory for obywatele.Uzytkownik."""
    class Meta:
        model = 'obywatele.Uzytkownik'

    reputation = factory.Sequence(lambda n: n % 100)
    city = 'Warsaw'
    phone = '+48123456789'

    uid = factory.SubFactory(UserFactory)


class TestFactoryUsage:
    """Example tests using factories."""
    def test_create_post_with_factory(self, db):
        """Test creating post using factory."""
        post = PostFactory()
        assert post.title is not None
        assert PostFactory._meta.model.objects.count() >= 1

    def test_create_bulk_posts(self, db):
        """Test creating multiple posts efficiently."""
        posts = PostFactory.create_batch(10)
        assert len(posts) == 10
        assert PostFactory._meta.model.objects.count() >= 10

    def test_create_decyzja_with_related(self, db):
        """Test creating decyzja with related objects."""
        decyzja = DecyzjaFactory()
        assert decyzja.title is not None
        assert decyzja.author is not None
        assert decyzja.chat_room is not None
