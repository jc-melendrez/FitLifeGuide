from django.core.management.base import BaseCommand

from fitlifeguide.firestore import get_db

FORUMS = (
    ('general', 'General Training', 'Talk about anything training related.'),
    ('form-checks', 'Form Checks', 'Post a lift or movement and ask for feedback.'),
    ('nutrition', 'Nutrition', 'Meals, macros, and what actually works for you.'),
    ('progress', 'Progress Logs', 'Share wins, setbacks, and the boring middle.'),
)


class Command(BaseCommand):
    help = 'Create the default Firestore forums.'

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
        self.stdout.write(self.style.SUCCESS('Firestore seed complete.'))
