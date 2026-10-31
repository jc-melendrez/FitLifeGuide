from django.core.management.base import BaseCommand
from django.utils.text import slugify

from fitlifeguide.firestore import get_db

FORUMS = (
    ('general', 'General Training', 'Talk about anything training related.'),
    ('form-checks', 'Form Checks', 'Post a lift or movement and ask for feedback.'),
    ('nutrition', 'Nutrition', 'Meals, macros, and what actually works for you.'),
    ('progress', 'Progress Logs', 'Share wins, setbacks, and the boring middle.'),
)

EXERCISES = (
    ('Back squat', 'Legs', 'strength'),
    ('Front squat', 'Legs', 'strength'),
    ('Deadlift', 'Posterior chain', 'strength'),
    ('Romanian deadlift', 'Hamstrings', 'strength'),
    ('Bench press', 'Chest', 'strength'),
    ('Incline bench press', 'Chest', 'strength'),
    ('Overhead press', 'Shoulders', 'strength'),
    ('Pull-up', 'Back', 'strength'),
    ('Chin-up', 'Back', 'strength'),
    ('Barbell row', 'Back', 'strength'),
    ('Dumbbell row', 'Back', 'strength'),
    ('Lat pulldown', 'Back', 'strength'),
    ('Dip', 'Chest', 'strength'),
    ('Lunge', 'Legs', 'strength'),
    ('Leg press', 'Legs', 'strength'),
    ('Leg curl', 'Hamstrings', 'strength'),
    ('Calf raise', 'Calves', 'strength'),
    ('Bicep curl', 'Arms', 'strength'),
    ('Tricep pushdown', 'Arms', 'strength'),
    ('Lateral raise', 'Shoulders', 'strength'),
    ('Face pull', 'Shoulders', 'strength'),
    ('Hip thrust', 'Glutes', 'strength'),
    ('Plank', 'Core', 'timed'),
    ('Side plank', 'Core', 'timed'),
    ('Hollow hold', 'Core', 'timed'),
    ('Wall sit', 'Legs', 'timed'),
    ('Battle ropes', 'Conditioning', 'timed'),
    ('Run', 'Cardio', 'cardio'),
    ('Cycling', 'Cardio', 'cardio'),
    ('Rowing', 'Cardio', 'cardio'),
    ('Jump rope', 'Cardio', 'cardio'),
    ('Incline walk', 'Cardio', 'cardio'),
)


class Command(BaseCommand):
    help = 'Create the default Firestore forums and exercise catalog.'

    def handle(self, *args, **options):
        db = get_db()
        for slug, name, description in FORUMS:
            doc_ref = db.collection('forums').document(slug)
            existing = doc_ref.get()
            payload = {
                'name': name,
                'slug': slug,
                'description': description,
            }
            if not existing.exists:
                payload['thread_count'] = 0
            doc_ref.set(payload, merge=True)
            self.stdout.write(f'forum: {slug}')

        for name, muscle_group, exercise_type in EXERCISES:
            slug = slugify(name)
            doc_ref = db.collection('exercise_catalog').document(slug)
            doc_ref.set({
                'name': name,
                'name_lower': name.lower(),
                'slug': slug,
                'muscle_group': muscle_group,
                'type': exercise_type,
                'owner_id': '',
                'seeded': True,
            }, merge=True)
            self.stdout.write(f'exercise: {slug}')

        self.stdout.write(self.style.SUCCESS('Firestore seed complete.'))
