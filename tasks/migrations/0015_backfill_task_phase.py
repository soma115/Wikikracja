from django.db import migrations


def backfill_task_phase(apps, schema_editor):
    from django.db.models import IntegerField, Sum
    from django.db.models.functions import Coalesce

    Task = apps.get_model("tasks", "Task")
    database = schema_editor.connection.alias
    realization_ids = (
        Task.objects.using(database)
        .filter(status="active", assigned_to__isnull=False)
        .annotate(vote_score=Coalesce(Sum("votes__value"), 0, output_field=IntegerField()))
        .filter(vote_score__gte=2)
        .values_list("pk", flat=True)
    )
    Task.objects.using(database).filter(pk__in=realization_ids).update(phase="realization")


class Migration(migrations.Migration):
    dependencies = [("tasks", "0014_task_currency_task_due_date_task_estimated_cost_and_more")]

    operations = [migrations.RunPython(backfill_task_phase, migrations.RunPython.noop)]
