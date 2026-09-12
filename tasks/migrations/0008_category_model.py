from django.db import migrations, models
import django.db.models.deletion


INITIAL_CATEGORIES = [
    ("meetings",  "Spotkania", "Sprawy na spotkania", 1, False),
    ("education", "Edukacja",  "Dzielenie się wiedzą", 2, False),
    ("other",     "Inne",      "", 99, True),
]


def seed_categories_and_migrate_tasks(apps, schema_editor):
    Category = apps.get_model("tasks", "Category")
    Task = apps.get_model("tasks", "Task")

    slug_to_id = {}
    for slug, name, description, order, is_protected in INITIAL_CATEGORIES:
        cat = Category.objects.create(
            slug=slug,
            name=name,
            description=description,
            order=order,
            is_protected=is_protected,
        )
        slug_to_id[slug] = cat.id

    other_id = slug_to_id["other"]
    for task in Task.objects.all():
        cat_id = slug_to_id.get(task.category_old, other_id)
        Task.objects.filter(pk=task.pk).update(category_id=cat_id)


def reverse_migrate(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    Category = apps.get_model("tasks", "Category")

    id_to_slug = {cat.id: cat.slug for cat in Category.objects.all()}
    for task in Task.objects.select_related("category").all():
        slug = id_to_slug.get(task.category_id, "other")
        Task.objects.filter(pk=task.pk).update(category_old=slug)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0007_add_task_category"),
    ]

    operations = [
        # 1. Create Category table
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True, default="")),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_protected", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("order", "name")},
        ),

        # 2. Rename old category column so we can read it during data migration
        migrations.RenameField(
            model_name="task",
            old_name="category",
            new_name="category_old",
        ),

        # 3. Add new FK column (nullable)
        migrations.AddField(
            model_name="task",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tasks",
                to="tasks.category",
            ),
        ),

        # 4. Seed categories + migrate task rows
        migrations.RunPython(seed_categories_and_migrate_tasks, reverse_migrate),

        # 5. Remove old string column
        migrations.RemoveField(
            model_name="task",
            name="category_old",
        ),
    ]
