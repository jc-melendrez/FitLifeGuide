import tempfile
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from community.models import BlogPost
from tools.models import MealPlan, MealPlanner, WorkoutPlan, WorkoutPlanner


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


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class TodayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('todayuser', 'today@example.com', 'Str0ngPass!234')
        self.today = timezone.localdate()
        self.week_start = self.today - timedelta(days=self.today.weekday())
        self.workout_plan = WorkoutPlan.objects.create(user=self.user)
        self.meal_plan = MealPlan.objects.create(user=self.user)

    def _workout(self):
        return WorkoutPlanner.objects.create(
            user=self.user,
            workout_plan=self.workout_plan,
            date=self.today,
            week_start=self.week_start,
            day_of_week=self.today.strftime('%a'),
            title='Lower Body',
            exercises='Squat',
            duration_minutes=45,
            goal='Strength',
            status='planned',
        )

    def test_guest_home_redirects_to_welcome(self):
        response = self.client.get(reverse('home'))

        self.assertRedirects(response, reverse('welcome'))

    def test_today_shows_workout_meals_and_week_progress(self):
        self._workout()
        MealPlanner.objects.create(
            user=self.user,
            meal_plan=self.meal_plan,
            date=self.today,
            week_start=self.week_start,
            day_of_week=self.today.strftime('%a'),
            meal_type='lunch',
            food_items='Rice and chicken',
            status='planned',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lower Body')
        self.assertContains(response, 'Rice and chicken')
        self.assertContains(response, '0/5')
        self.assertContains(response, 'Open workout')

    def test_today_counts_completed_workouts_in_week(self):
        WorkoutPlanner.objects.create(
            user=self.user,
            workout_plan=self.workout_plan,
            date=self.week_start,
            week_start=self.week_start,
            day_of_week=self.week_start.strftime('%a'),
            title='Upper Body',
            exercises='Press',
            duration_minutes=40,
            goal='Strength',
            status='completed',
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('home'))

        self.assertContains(response, '1/5')

    def test_skip_today_marks_planned_workout_missed(self):
        workout = self._workout()
        other = User.objects.create_user('otheruser', 'other@example.com', 'Str0ngPass!234')
        other_plan = WorkoutPlan.objects.create(user=other)
        other_workout = WorkoutPlanner.objects.create(
            user=other,
            workout_plan=other_plan,
            date=self.today,
            week_start=self.week_start,
            day_of_week=self.today.strftime('%a'),
            title='Other User Workout',
            exercises='Rows',
            status='planned',
        )
        self.client.force_login(self.user)

        response = self.client.post(reverse('tools:skip_today'))

        self.assertRedirects(response, reverse('home'))
        workout.refresh_from_db()
        other_workout.refresh_from_db()
        self.assertEqual(workout.status, 'missed')
        self.assertEqual(other_workout.status, 'planned')
