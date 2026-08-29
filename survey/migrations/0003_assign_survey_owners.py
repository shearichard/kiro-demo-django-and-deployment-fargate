from django.db import migrations


def assign_owners(apps, schema_editor):
    Survey = apps.get_model('survey', 'Survey')
    User = apps.get_model('auth', 'User')
    superuser = User.objects.filter(is_superuser=True).order_by('id').first()
    if superuser:
        Survey.objects.filter(owner__isnull=True).update(owner=superuser)


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0002_add_survey_owner_nullable'),
    ]

    operations = [
        migrations.RunPython(assign_owners, migrations.RunPython.noop),
    ]
