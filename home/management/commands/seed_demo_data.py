from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from ankiety.models import Survey, SurveyOption, SurveyVote
from board.models import Post, PostCategory
from bookkeeping.models import Asset, Partner, Transaction
from bookkeeping.models import Category as BookkeepingCategory
from events.models import Event
from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, ZebranePodpisy
from obywatele.models import Country, Region, Uzytkownik
from site_settings.models import SiteParameters
from tasks.models import Category as TaskCategory
from tasks.models import Task, TaskEvaluation, TaskVote

DEMO_PREFIX = "Demo: "
DEMO_USERNAMES = {"alex": "demo_alex", "jordan": "demo_jordan", "morgan": "demo_morgan", "taylor": "demo_taylor"}


class Command(BaseCommand):
    help = "Create additive English-language demo data without changing existing records."

    def handle(self, *args, **options):
        users = self._create_users()
        self._create_location_data(users)
        posts = self._create_posts(users)
        tasks = self._create_tasks(users)
        surveys = self._create_surveys(users)
        self._create_events()
        self._create_votings(users)
        self._create_bookkeeping(users)
        self._create_chat_messages(users, posts, tasks, surveys)
        self._ensure_brand_mark()

        self.stdout.write(self.style.SUCCESS("English demo data created (existing records were preserved)."))
        self.stdout.write(f"Users: {', '.join(user.username for user in users.values())}")
        self.stdout.write("Demo records use the 'Demo:' prefix where the model has no dedicated marker.")

    def _create_users(self):
        User = get_user_model()
        names = {
            "alex": ("Alex", "Rivera", "alex.rivera@example.test"),
            "jordan": ("Jordan", "Lee", "jordan.lee@example.test"),
            "morgan": ("Morgan", "Patel", "morgan.patel@example.test"),
            "taylor": ("Taylor", "Nguyen", "taylor.nguyen@example.test"),
        }
        users = {}
        for key, username in DEMO_USERNAMES.items():
            first_name, last_name, email = names[key]
            user, created = User.objects.get_or_create(username=username, defaults={"email": email})
            changed = []
            for field, value in (("first_name", first_name), ("last_name", last_name), ("email", email), ("is_active", True)):
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed.append(field)
            if created:
                user.set_unusable_password()
                changed.append("password")
            if changed:
                user.save(update_fields=changed)
            profile, _ = Uzytkownik.objects.get_or_create(uid=user)
            profile.language = "en"
            profile.onboarding_status = Uzytkownik.OnboardingStatus.FORM_COMPLETED
            profile.data_przyjecia = profile.data_przyjecia or timezone.localdate() - timedelta(days=90)
            profile.city = {"alex": "Portland", "jordan": "Bristol", "morgan": "Toronto", "taylor": "Austin"}[key]
            profile.responsibilities = {
                "alex": "Community facilitation and meeting notes",
                "jordan": "Accessibility and inclusive participation",
                "morgan": "Budget review and open records",
                "taylor": "Urban gardening and volunteer coordination",
            }[key]
            profile.skills_knowledge_hobby = {
                "alex": "Mediation, writing, cycling",
                "jordan": "UX research, accessibility, photography",
                "morgan": "Accounting, data analysis, cooking",
                "taylor": "Permaculture, teaching, repair workshops",
            }[key]
            profile.job = {"alex": "Community organizer", "jordan": "Product designer", "morgan": "Financial analyst", "taylor": "Teacher"}[key]
            profile.why = "I want to help our group make transparent, practical decisions together."
            profile.email_frequency = Uzytkownik.EmailFrequency.WEEKLY
            profile.save()
            self._attach_image(profile, f"demo-avatar-{key}.png", key, (160, 160))
            users[key] = user
        return users

    def _create_location_data(self, users):
        country, _ = Country.objects.get_or_create(code="US", defaults={"name": "United States"})
        region, _ = Region.objects.get_or_create(country=country, name="Oregon")
        users["alex"].uzytkownik.voivodeship = region
        users["alex"].uzytkownik.save(update_fields=["voivodeship"])

    def _create_posts(self, users):
        categories = {}
        for name, description, priority in (
            ("Community life", "Ideas and updates about everyday community life.", 10),
            ("Open governance", "Documents about transparent and participatory decision-making.", 20),
            ("Resources", "Shared guides, tools, and practical resources.", 30),
        ):
            category, _ = PostCategory.objects.get_or_create(name=DEMO_PREFIX + name, defaults={"description": description, "priority": priority})
            categories[name] = category

        posts = []
        definitions = (
            ("Welcome to the Riverside Commons", "A short introduction for new members", "Community life", "alex", True, "welcome-riverside-commons"),
            ("How We Make Decisions Together", "A practical guide to proposals and referenda", "Open governance", "jordan", True, "how-we-make-decisions"),
            ("Shared Tools and Lending Library", "A growing list of things neighbours can borrow", "Resources", "taylor", False, "shared-tools-library"),
        )
        for title, subtitle, category, author, important, slug in definitions:
            post, created = Post.objects.get_or_create(
                slug=slug,
                defaults={
                    "title": DEMO_PREFIX + title,
                    "subtitle": subtitle,
                    "text": f"<h2>{title}</h2><p>This is demo content for an English-speaking community. It shows how a clear, welcoming document can support informed participation.</p><p>Everyone is invited to read, ask questions, and contribute a practical next step.</p>",
                    "author": users[author],
                    "updated_by": users[author],
                    "category": categories[category],
                    "visibility": Post.Visibility.PUBLIC,
                    "is_important": False,
                },
            )
            if created and important:
                Post.objects.filter(pk=post.pk).update(is_important=True)
                post.is_important = True
            if created or not post.featured_image:
                self._attach_image(post, f"demo-post-{slug}.png", title, (1200, 675), field="featured_image")
            posts.append(post)
        return posts

    def _create_tasks(self, users):
        categories = {}
        for name in ("Neighbourhood", "Digital commons", "Environment"):
            category, _ = TaskCategory.objects.get_or_create(name=DEMO_PREFIX + name, defaults={"slug": "demo-" + name.lower().replace(" ", "-"), "description": "Demo activity category."})
            categories[name] = category
        definitions = (
            ("Map accessible routes to the community hall", "Create a simple, public map of step-free routes and entrances.", "Neighbourhood", "alex", "jordan", Task.Status.ACTIVE),
            ("Prepare the spring seed exchange", "Collect seeds, label them clearly, and host an open exchange table.", "Environment", "taylor", "alex", Task.Status.COMPLETED),
            ("Publish the meeting notes template", "Draft a reusable template for agendas, decisions, and follow-up actions.", "Digital commons", "jordan", "morgan", Task.Status.ACTIVE),
        )
        tasks = []
        for title, description, category, creator, assignee, status in definitions:
            task, _ = Task.objects.get_or_create(
                title=DEMO_PREFIX + title,
                defaults={"description": description, "category": categories[category], "created_by": users[creator], "assigned_to": users[assignee], "status": status, "team_mode": True},
            )
            task.votes.get_or_create(user=users["alex"], defaults={"value": TaskVote.Value.UP})
            task.votes.get_or_create(user=users["morgan"], defaults={"value": TaskVote.Value.UP})
            task.evaluations.get_or_create(user=users["taylor"], defaults={"value": TaskEvaluation.Value.SUCCESS if status == Task.Status.COMPLETED else TaskEvaluation.Value.FAILURE})
            tasks.append(task)
        return tasks

    def _create_surveys(self, users):
        survey, _ = Survey.objects.get_or_create(
            title=DEMO_PREFIX + "Which evening works best for the monthly assembly?",
            defaults={
                "description": "Help us choose a recurring time that works for the largest number of participants.",
                "end_date": timezone.now() + timedelta(days=30),
                "author": users["alex"],
                "allow_multiple_choice": False,
                "allow_custom_options": True,
            },
        )
        options = []
        for order, text in enumerate(("Tuesday at 18:00", "Thursday at 18:00", "Saturday at 10:00")):
            option, _ = SurveyOption.objects.get_or_create(survey=survey, text=text, defaults={"order": order, "created_by": users["alex"]})
            options.append(option)
        SurveyVote.objects.get_or_create(survey=survey, user=users["jordan"], option=options[1])
        SurveyVote.objects.get_or_create(survey=survey, user=users["taylor"], option=options[2])
        return [survey]

    def _create_events(self):
        now = timezone.now()
        definitions = (
            ("Demo: Riverside Commons Assembly", "Open monthly meeting for proposals, updates, and shared decisions.", now + timedelta(days=10), "Riverside Community Hall"),
            ("Demo: Seed and Repair Exchange", "Bring seeds, small tools, or something that needs a second life.", now + timedelta(days=17), "Garden Workshop"),
        )
        for title, description, start_date, place in definitions:
            Event.objects.get_or_create(
                title=title, defaults={"description": description, "start_date": start_date, "end_date": start_date + timedelta(hours=2), "place": place, "is_public": True, "is_active": True}
            )

    def _create_votings(self, users):
        decision, created = Decyzja.objects.get_or_create(
            title=DEMO_PREFIX + "Adopt a transparent community budget",
            defaults={
                "tresc": "The group publishes a quarterly summary of income, spending, and remaining funds.",
                "kara": "None; this is a transparency commitment.",
                "uzasadnienie": "A simple public summary helps members understand how shared resources are used.",
                "args_for": "Improves trust and makes it easier to participate in budget decisions.",
                "args_against": "Preparing the summary requires a small amount of regular volunteer time.",
                "path": "Proposal → discussion → referendum → result",
                "author": users["morgan"],
                "status": Decyzja.Status.PROPOSITION,
            },
        )
        if created:
            decision.status = Decyzja.Status.REFERENDUM
            decision.data_referendum_start = timezone.localdate() - timedelta(days=2)
            decision.data_referendum_stop = timezone.localdate() + timedelta(days=5)
            decision.za = 3
            decision.przeciw = 1
            decision.save(update_fields=["status", "data_referendum_start", "data_referendum_stop", "za", "przeciw"])
        for author, argument_type, content in (
            ("alex", "FOR", "A quarterly summary is small enough to maintain and useful enough to matter."),
            ("jordan", "AGAINST", "We should agree on a minimum format before promising a regular publication date."),
        ):
            Argument.objects.get_or_create(decyzja=decision, author=users[author], argument_type=argument_type, defaults={"content": content})
        for key in ("morgan", "alex", "jordan", "taylor"):
            ZebranePodpisy.objects.get_or_create(projekt=decision, podpis_uzytkownika=users[key])
        for key in ("alex", "jordan", "taylor", "morgan"):
            KtoJuzGlosowal.objects.get_or_create(projekt=decision, ktory_uzytkownik_juz_zaglosowal=users[key])
        decision.ile_osob_podpisalo = ZebranePodpisy.objects.filter(projekt=decision).count()
        decision.save(update_fields=["ile_osob_podpisalo"])

    def _create_bookkeeping(self, users):
        asset, _ = Asset.objects.get_or_create(code="DEMO", defaults={"name": "Demo credits", "symbol": "DC", "is_default": not Asset.objects.filter(is_default=True).exists()})
        category, _ = BookkeepingCategory.objects.get_or_create(name=DEMO_PREFIX + "Community operations")
        partner, _ = Partner.objects.get_or_create(name=DEMO_PREFIX + "Riverside Print Co.", defaults={"email": "hello@example.test", "city": "Portland", "country": "United States"})
        Transaction.objects.get_or_create(
            note="Demo: printed meeting materials", defaults={"type": Transaction.OUTGOING, "asset": asset, "category": category, "partner": partner, "amount": Decimal("85.00"), "author": users["morgan"]}
        )
        Transaction.objects.get_or_create(
            note="Demo: member contributions", defaults={"type": Transaction.INCOMING, "asset": asset, "category": category, "partner": partner, "amount": Decimal("240.00"), "author": users["morgan"]}
        )

    def _create_chat_messages(self, users, posts, tasks, surveys):
        from chat.models import Message

        messages = (
            (posts[0].chat_room, users["jordan"], "Glad to see a clear welcome page. The lending library is a great next step."),
            (tasks[0].chat_room, users["morgan"], "I can review the first draft of the accessibility map this week."),
            (surveys[0].chat_room, users["taylor"], "Saturday mornings work well for the seed exchange volunteers."),
        )
        for room, sender, text in messages:
            Message.objects.get_or_create(room=room, sender=sender, text=DEMO_PREFIX + text)

    def _ensure_brand_mark(self):
        settings = SiteParameters.get()
        if not settings.brand_mark:
            self._attach_image(settings, "demo-brand-mark.png", "Riverside Commons", (512, 512), field="brand_mark")

    def _attach_image(self, instance, filename, label, size, field=None):
        field = field or "avatar"
        image_field = getattr(instance, field)
        if image_field:
            return
        width, height = size
        image = Image.new("RGB", size, (20, 47, 74))
        draw = ImageDraw.Draw(image)
        draw.rectangle((width * 0.08, height * 0.08, width * 0.92, height * 0.92), outline=(101, 196, 169), width=max(2, width // 80))
        draw.text((width * 0.12, height * 0.44), label[:32], fill=(245, 243, 232))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        image_field.save(filename, ContentFile(buffer.getvalue()), save=True)
