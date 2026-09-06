from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('home', '0014_alter_feeditem_content_type_and_more')]

    operations = [migrations.SeparateDatabaseAndState(state_operations=[migrations.DeleteModel(name='ReadStatus')], database_operations=[])]
