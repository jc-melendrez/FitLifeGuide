import tempfile
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from community.models import BlogPost
from tools.models import WorkoutPlan, WorkoutPlanner


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class SearchSmokeTests(TestCase):
    def test_search_finds_published_post_without_store(self):
        user = User.objects.create_user('author', 'author@example.com', 'Str0ngPass!234')
        BlogPost.objects.create(
            author=user,
            title='Beginner Strength',
            content='Start here',
            published=True,
        )

        with patch('mainpage.views.videos_views', return_value=[]):
            response = self.client.get(reverse('home'), {'q': 'Strength'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Beginner Strength')

    def test_search_does_not_expose_other_users_workouts(self):
        owner = User.objects.create_user('owner', 'owner@example.com', 'Str0ngPass!234')
        other = User.objects.create_user('other', 'other@example.com', 'Str0ngPass!234')
        plan = WorkoutPlan.objects.create(user=owner)
        WorkoutPlanner.objects.create(
            user=owner,
            workout_plan=plan,
            date=date.today(),
            week_start=date.today(),
            day_of_week='Mon',
            title='Private Strength',
            exercises='Squat',
        )

        with patch('mainpage.views.videos_views', return_value=[]):
            response = self.client.get(reverse('home'), {'q': 'Private'})
            self.assertNotContains(response, 'Private Strength')

            self.client.force_login(other)
            response = self.client.get(reverse('home'), {'q': 'Private'})
            self.assertNotContains(response, 'Private Strength')

            self.client.force_login(owner)
            response = self.client.get(reverse('home'), {'q': 'Private'})
            self.assertContains(response, 'Private Strength')

    def test_landing_and_about_render(self):
        response = self.client.get(reverse('welcome'))

        self.assertContains(response, 'Workouts logged')
        self.assertContains(response, 'Meals planned')
        self.assertContains(response, 'Members training')

        response = self.client.get(reverse('about'))

        self.assertContains(response, 'Built for the work between workouts.')
