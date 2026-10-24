import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from community.models import BlogPost
from tools.models import MealPlan, MealPlanner, WorkoutPlan, WorkoutPlanner
from videos.models import VideoHistory

from .models import EmailOTP, Profile


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class AuthSmokeTests(TestCase):
    def test_register_page_renders_auth_shell(self):
        response = self.client.get(reverse('register'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'fl-auth-grid')
        self.assertContains(response, 'Create account')

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

    def test_profile_totals_are_not_capped_by_recent_lists(self):
        user = User.objects.create_user('statsuser', 'stats@example.com', 'Str0ngPass!234')
        self.client.force_login(user)
        workout_plan = WorkoutPlan.objects.create(user=user)
        meal_plan = MealPlan.objects.create(user=user)
        today = date.today()

        for index in range(9):
            day = today - timedelta(days=index)
            WorkoutPlanner.objects.create(
                user=user,
                workout_plan=workout_plan,
                date=day,
                week_start=day,
                day_of_week='Mon',
                title=f'Workout {index}',
                exercises='Squat',
            )
            MealPlanner.objects.create(
                user=user,
                meal_plan=meal_plan,
                date=day,
                week_start=day,
                day_of_week='Mon',
                meal_type='lunch',
                food_items='Rice',
            )
            BlogPost.objects.create(author=user, title=f'Post {index}', content='Body')
            VideoHistory.objects.create(
                user=user,
                video_id=f'video{index}',
                title=f'Video {index}',
                thumbnail_url='https://example.com/thumb.jpg',
                channel_title='Channel',
                duration='PT5M',
            )

        response = self.client.get(reverse('profile'))

        self.assertEqual(response.context['workout_count'], 9)
        self.assertEqual(response.context['meal_count'], 9)
        self.assertEqual(response.context['post_count'], 9)
        self.assertEqual(response.context['video_count'], 9)
        self.assertEqual(len(response.context['workouts']), 7)
        self.assertEqual(len(response.context['meals']), 7)
        self.assertEqual(len(response.context['posts']), 5)
        self.assertEqual(len(response.context['video_history']), 9)

    def test_edit_profile_renders_plain_status_pills(self):
        user = User.objects.create_user('pilluser', 'pill@example.com', 'Str0ngPass!234')
        self.client.force_login(user)

        response = self.client.get(reverse('edit_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="fl-status-pills"')
        for label in ('Run', 'Lift', 'Rest', 'Cook'):
            self.assertContains(response, label)

    def test_edit_profile_saves_plain_status(self):
        user = User.objects.create_user('statususer', 'status@example.com', 'Str0ngPass!234')
        self.client.force_login(user)

        response = self.client.post(reverse('edit_profile'), {
            'username': 'statususer',
            'email': 'status@example.com',
            'location': '',
            'bio': '',
            'birth_date': '',
            'status': 'run',
        })

        self.assertRedirects(response, reverse('profile'))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.status, 'run')


class StatusMigrationTests(TransactionTestCase):
    migrate_from = [('users', '0006_alter_profile_avatar_alter_profile_cover_image')]
    migrate_to = [('users', '0008_map_profile_status')]
    old_statuses = [
        '\U0001F4AA',
        '\U0001F3C3',
        '\U0001F9D8',
        '\U0001F957',
        '\U0001F634',
        '\U0001F3AF',
        '\U0001F31F',
        '\U0001F50B',
        '\U0001F3AE',
        '\U0001F4DA',
    ]

    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        User = old_apps.get_model('auth', 'User')
        Profile = old_apps.get_model('users', 'Profile')

        for index, status in enumerate(self.old_statuses):
            user = User.objects.create(username=f'migration{index}')
            Profile.objects.create(user=user, status=status)

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)

    def test_status_mapping_is_reversible(self):
        new_apps = self.executor.loader.project_state(self.migrate_to).apps
        Profile = new_apps.get_model('users', 'Profile')
        field = Profile._meta.get_field('status')

        self.assertEqual(field.max_length, 4)
        self.assertEqual(field.default, 'rest')
        self.assertEqual(Profile.objects.filter(status='lift').count(), 1)
        self.assertEqual(Profile.objects.filter(status='run').count(), 1)
        self.assertEqual(Profile.objects.filter(status='cook').count(), 1)
        self.assertEqual(Profile.objects.filter(status='rest').count(), 7)

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        Profile = old_apps.get_model('users', 'Profile')

        self.assertEqual(Profile.objects.filter(status='\U0001F4AA').count(), 1)
        self.assertEqual(Profile.objects.filter(status='\U0001F3C3').count(), 1)
        self.assertEqual(Profile.objects.filter(status='\U0001F957').count(), 1)
        self.assertEqual(Profile.objects.filter(status='\U0001F31F').count(), 7)
