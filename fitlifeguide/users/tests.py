import tempfile

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import EmailOTP, Profile


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class AuthSmokeTests(TestCase):
    def test_register_creates_user_and_profile(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': 'Str0ngPass!234',
            'password2': 'Str0ngPass!234',
        })

        self.assertRedirects(response, reverse('login'))
        user = User.objects.get(username='newuser')
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_login_requires_and_accepts_otp(self):
        user = User.objects.create_user('otpuser', 'otp@example.com', 'Str0ngPass!234')
        mail.outbox.clear()

        response = self.client.post(reverse('login'), {
            'username': 'otpuser',
            'password': 'Str0ngPass!234',
        })

        self.assertRedirects(response, reverse('verify_otp'))
        self.assertEqual(self.client.session['pre_2fa_user_id'], user.id)
        self.assertEqual(len(mail.outbox), 1)

        otp = EmailOTP.objects.get(user=user)
        response = self.client.post(reverse('verify_otp'), {'otp': otp.code})

        self.assertRedirects(response, reverse('home'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.id)

    def test_profile_loads(self):
        user = User.objects.create_user('profileuser', 'profile@example.com', 'Str0ngPass!234')
        self.client.force_login(user)

        response = self.client.get(reverse('profile'))

        self.assertEqual(response.status_code, 200)
