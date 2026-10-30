from django.db import migrations


def reconcile_active_task_phases(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    database = schema_editor.connection.alias

    tasks = Task.objects.using(database).filter(status="active").prefetch_related("votes", "approved_helpers")
    for task in tasks.iterator(chunk_size=500):
        vote_score = sum(vote.value for vote in task.votes.all())
        helpers = task.approved_helpers.all()
        helper_count = sum(helper.pk != task.assigned_to_id for helper in helpers)
        team_size = int(task.assigned_to_id is not None) + helper_count
        required_people = task.required_people or 1
        ready = task.assigned_to_id is not None and vote_score >= 2 and team_size >= required_people
        phase = "realization" if ready else "proposal"
        if task.phase != phase:
            Task.objects.using(database).filter(pk=task.pk).update(phase=phase)


class Migration(migrations.Migration):
    dependencies = [("tasks", "0017_remove_task_currency_remove_task_estimated_cost_and_more")]

    operations = [migrations.RunPython(reconcile_active_task_phases, migrations.RunPython.noop)]
