"""Factory_Boy factories dla modeli Wikikracja. Używane w testach z /tests/.

Tylko factories dla modeli aktualnie używanych w testach. Nowe dodawaj na żądanie — patrz
[[feedback-test-factories-yagni]]: nie kopiuj wholesale z innych branchy.
"""

import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from glosowania.models import Decyzja

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user_{n}')
    email = factory.Sequence(lambda n: f'user{n}@example.com')
    is_staff = False
    is_superuser = False

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        """Hashuje hasło — domyślnie 'testpass123'. Pozwala UserFactory(password='X').

        update_fields=['password'] izoluje od side-effectów signali post_save(User)
        (np. obywatele.models tworzy Uzytkownik tylko gdy created=True).
        """
        if not create:
            return
        obj.set_password(extracted or 'testpass123')
        obj.save(update_fields=['password'])


class PostCategoryFactory(DjangoModelFactory):
    class Meta:
        model = 'board.PostCategory'

    name = factory.Sequence(lambda n: f'Category {n}')
    priority = factory.Sequence(lambda n: n % 10 + 1)


class PostFactory(DjangoModelFactory):
    class Meta:
        model = 'board.Post'

    title = factory.Sequence(lambda n: f'Post {n}')
    subtitle = factory.Sequence(lambda n: f'Subtitle {n}')
    text = factory.Sequence(lambda n: f'<p>Content {n}</p>')
    is_public = True
    is_important = False

    author = factory.SubFactory(UserFactory)
    category = factory.SubFactory(PostCategoryFactory)


class RoomFactory(DjangoModelFactory):
    class Meta:
        model = 'chat.Room'

    title = factory.Sequence(lambda n: f'Room {n}')
    public = True
    archived = False
    protected = False


class DecyzjaFactory(DjangoModelFactory):
    """UWAGA: NIE ustawiamy chat_room — sygnał glosowania.signals.create_or_update_chat_room_for_referendum
    automatycznie utworzy chat_room przy save() (gdy status=PROPOSITION). Podawanie chat_room SubFactory utworzy
    orphan'a — sygnał i tak go nadpisze."""

    class Meta:
        model = 'glosowania.Decyzja'

    title = factory.Sequence(lambda n: f'Bill {n}')
    tresc = factory.Sequence(lambda n: f'Law text {n}')
    kara = factory.Sequence(lambda n: f'Penalty {n}')
    uzasadnienie = factory.Sequence(lambda n: f'Reasoning {n}')
    ile_osob_podpisalo = 0
    za = 0
    przeciw = 0
    status = Decyzja.Status.PROPOSITION

    author = factory.SubFactory(UserFactory)
