import os
import time
from datetime import date, datetime, timezone as dt_timezone

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from fitlifeguide.domain import CommentList, label_for, parse_date, parse_datetime
from users.repositories import get_otp, get_user_by_username


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
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ALLOWED_HOSTS=['testserver'],
)
class FirestoreAuthFlowTests(SimpleTestCase):
    def test_register_login_otp_and_profile(self):
        if not os.environ.get('FIRESTORE_EMULATOR_HOST'):
            self.skipTest('Firestore emulator is not configured')

        stamp = str(int(time.time() * 1000))
        username = f'test_{stamp}'
        email = f'{username}@example.com'
        password = 'Str0ngPass!234'

        response = self.client.post(reverse('register'), {
            'email': email,
            'username': username,
            'password1': password,
            'password2': password,
        })
        self.assertRedirects(response, reverse('login'))

        user = get_user_by_username(username)
        self.assertIsNotNone(user)
        self.assertEqual(user.email, email)

        response = self.client.post(reverse('login'), {
            'username': username,
            'password': password,
        })
        self.assertRedirects(response, reverse('verify_otp'))

        otp = get_otp(user.id)
        self.assertIsNotNone(otp)

        response = self.client.post(reverse('verify_otp'), {'otp': otp['code']})
        self.assertRedirects(response, reverse('home'))

        response = self.client.post(reverse('profile'), {
            'email': email,
            'username': username,
            'location': 'Manila',
            'bio': 'Test bio',
            'birth_date': '2000-01-02',
            'status': 'run',
        })
        self.assertRedirects(response, reverse('profile'))

        updated = get_user_by_username(username)
        self.assertEqual(updated.profile.location, 'Manila')
        self.assertEqual(updated.profile.bio, 'Test bio')
        self.assertEqual(updated.profile.status, 'run')
