from django.db import migrations

OLD_TO_NEW = {
    '\U0001F4AA': 'lift',
    '\U0001F3C3': 'run',
    '\U0001F9D8': 'rest',
    '\U0001F957': 'cook',
    '\U0001F634': 'rest',
    '\U0001F3AF': 'rest',
    '\U0001F31F': 'rest',
    '\U0001F50B': 'rest',
    '\U0001F3AE': 'rest',
    '\U0001F4DA': 'rest',
}

NEW_TO_OLD = {
    'run': '\U0001F3C3',
    'lift': '\U0001F4AA',
    'rest': '\U0001F31F',
    'cook': '\U0001F957',
}


def forwards(apps, schema_editor):
    Profile = apps.get_model('users', 'Profile')
    for old, new in OLD_TO_NEW.items():
        Profile.objects.filter(status=old).update(status=new)


def backwards(apps, schema_editor):
    Profile = apps.get_model('users', 'Profile')
    for new, old in NEW_TO_OLD.items():
        Profile.objects.filter(status=new).update(status=old)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_alter_profile_status'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
