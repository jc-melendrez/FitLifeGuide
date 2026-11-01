import json
import shutil
import subprocess
from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from fitlifeguide.domain import CommentList, Profile, User, label_for, parse_date, parse_datetime
from users.firebase_auth import InvalidFirebaseToken


class DomainTests(SimpleTestCase):
    def test_parse_date_accepts_dates_datetimes_and_strings(self):
        self.assertEqual(parse_date(date(2026, 10, 29)), date(2026, 10, 29))
        self.assertEqual(
            parse_date(datetime(2026, 10, 29, 12, 30, tzinfo=dt_timezone.utc)),
            date(2026, 10, 29),
        )
        self.assertEqual(parse_date('2026-10-29'), date(2026, 10, 29))
        self.assertIsNone(parse_date(None))

    def test_parse_datetime_makes_naive_values_aware(self):
        value = parse_datetime('2026-10-29T12:30:00')
        self.assertIsNotNone(value.tzinfo)

    def test_comment_list_behaves_like_a_queryset(self):
        comments = CommentList()
        self.assertFalse(comments.exists)
        self.assertEqual(comments.count, 0)
        comments.append(object())
        self.assertTrue(comments.exists)
        self.assertEqual(comments.count, 1)

    def test_label_for_falls_back_to_raw_value(self):
        choices = (('run', 'Run'), ('rest', 'Rest'))
        self.assertEqual(label_for(choices, 'run'), 'Run')
        self.assertEqual(label_for(choices, 'unknown'), 'unknown')
        self.assertEqual(label_for(choices, ''), '')


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    FIREBASE_API_KEY='test-api-key',
    FIREBASE_AUTH_DOMAIN='test.firebaseapp.com',
    FIREBASE_PROJECT_ID='demo-fitlife',
    FIREBASE_APP_ID='1:2:web:3',
)
class FirebaseAuthViewTests(SimpleTestCase):
    def setUp(self):
        self.user = User(
            id='app-user',
            username='alex',
            email='alex@example.com',
            date_joined=timezone.now(),
            profile=Profile(user_id='app-user'),
        )
        self.verified = {
            'uid': 'firebase-user',
            'email': 'alex@example.com',
            'name': '',
        }

    def post_json(self, url_name, payload):
        return self.client.post(
            reverse(url_name),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_login_page_renders_firebase_config(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'firebase-config')
        self.assertContains(response, '<meta name="referrer" content="strict-origin">')
        self.assertNotContains(response, 'content="no-referrer"')
        self.assertContains(response, 'data-callback-url="http://testserver/auth/firebase/"')
        self.assertContains(response, 'data-complete-url="http://testserver/auth/complete-profile/"')
        self.assertContains(response, 'onsubmit="return false"')
        self.assertContains(response, 'firebase_auth.js?v=5')
        self.assertIn('no-store', response['Cache-Control'])

    def test_register_page_is_not_cached(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'firebase_auth.js?v=5')
        self.assertIn('no-store', response['Cache-Control'])

    def test_callback_page_renders_absolute_urls(self):
        response = self.client.get(reverse('firebase_callback'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-callback-url="http://testserver/auth/firebase/"')
        self.assertContains(response, 'data-complete-url="http://testserver/auth/complete-profile/"')

    def test_firebase_client_uses_local_sdk(self):
        static_dir = Path(__file__).resolve().parent / 'static' / 'users'
        client_source = (static_dir / 'firebase_auth.js').read_text(encoding='utf-8')
        vendor_dir = static_dir / 'vendor' / 'firebase'
        app_source = (vendor_dir / 'firebase-app.js').read_text(encoding='utf-8')
        auth_source = (vendor_dir / 'firebase-auth.js').read_text(encoding='utf-8')

        self.assertNotIn('gstatic.com', client_source)
        self.assertNotIn('from"https://', app_source)
        self.assertNotIn("from 'https://", app_source)
        self.assertNotIn('from"https://', auth_source)
        self.assertNotIn("from 'https://", auth_source)
        self.assertIn('from"./firebase-app.js"', auth_source)
        self.assertIn('./vendor/firebase/firebase-app.js', client_source)
        self.assertIn('./vendor/firebase/firebase-auth.js', client_source)

    def test_firebase_client_is_valid_es_module(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js is not installed')
        static_dir = Path(__file__).resolve().parent / 'static' / 'users'
        client_source = (static_dir / 'firebase_auth.js').read_text(encoding='utf-8')
        result = subprocess.run(
            [node, '--input-type=module', '--check'],
            input=client_source,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_callback_logs_in_existing_firebase_user(self):
        with patch('users.views.verify_firebase_id_token', return_value=self.verified), \
                patch('users.views.get_user_by_firebase_uid', return_value=self.user):
            response = self.post_json('firebase_callback', {'idToken': 'token'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertEqual(self.client.session['_auth_user_id'], self.user.id)

    def test_callback_links_existing_user_by_email(self):
        with patch('users.views.verify_firebase_id_token', return_value=self.verified), \
                patch('users.views.get_user_by_firebase_uid', return_value=None), \
                patch('users.views.get_user_by_email', return_value=self.user), \
                patch('users.views.link_firebase_uid', return_value=self.user) as link:
            response = self.post_json('firebase_callback', {'idToken': 'token'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        link.assert_called_once_with(self.user.id, self.verified['uid'])
        self.assertEqual(self.client.session['_auth_user_id'], self.user.id)

    def test_callback_returns_needs_profile_for_new_user(self):
        with patch('users.views.verify_firebase_id_token', return_value=self.verified), \
                patch('users.views.get_user_by_firebase_uid', return_value=None), \
                patch('users.views.get_user_by_email', return_value=None):
            response = self.post_json('firebase_callback', {'idToken': 'token'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'status': 'needs_profile',
            'email': self.verified['email'],
        })

    def test_callback_rejects_invalid_token(self):
        with patch(
            'users.views.verify_firebase_id_token',
            side_effect=InvalidFirebaseToken('This sign-in link is invalid or has expired.'),
        ):
            response = self.post_json('firebase_callback', {'idToken': 'bad-token'})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['status'], 'error')

    def test_callback_rejects_inactive_user(self):
        self.user.is_active = False
        with patch('users.views.verify_firebase_id_token', return_value=self.verified), \
                patch('users.views.get_user_by_firebase_uid', return_value=self.user):
            response = self.post_json('firebase_callback', {'idToken': 'token'})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['status'], 'error')

    def test_complete_profile_creates_and_logs_in_user(self):
        with patch('users.views.verify_firebase_id_token', return_value=self.verified), \
                patch('users.views.get_user_by_firebase_uid', return_value=None), \
                patch('users.views.get_user_by_email', return_value=None), \
                patch('users.forms.get_user_by_username', return_value=None), \
                patch('users.forms.create_user', return_value=self.user) as create:
            response = self.post_json('complete_profile', {
                'idToken': 'token',
                'username': 'alex',
                'goal': 'build_muscle',
                'days_per_week': '4',
                'location': 'Manila',
                'bio': 'Lifting.',
                'birth_date': '2000-01-02',
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        create.assert_called_once()
        self.assertEqual(self.client.session['_auth_user_id'], self.user.id)

    def test_complete_profile_rejects_taken_username(self):
        with patch('users.views.verify_firebase_id_token', return_value=self.verified), \
                patch('users.views.get_user_by_firebase_uid', return_value=None), \
                patch('users.views.get_user_by_email', return_value=None), \
                patch('users.forms.get_user_by_username', return_value=self.user):
            response = self.post_json('complete_profile', {
                'idToken': 'token',
                'username': 'alex',
                'goal': 'build_muscle',
                'days_per_week': '4',
            })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'invalid')
        self.assertIn('username', response.json()['errors'])
