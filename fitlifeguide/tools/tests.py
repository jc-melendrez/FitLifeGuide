import tempfile
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import MealPlan, MealPlanner, WorkoutPlan, WorkoutPlanner


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class PlannerSmokeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('planner', 'planner@example.com', 'Str0ngPass!234')
        self.client.force_login(self.user)

    def test_add_meal(self):
        MealPlan.objects.create(user=self.user)

        response = self.client.post(
            reverse('tools:add_meal') + '?date=2026-10-24&meal_type=lunch',
            {'food_items': 'Rice and chicken', 'calories': 600, 'notes': ''},
        )

        self.assertRedirects(response, reverse('tools:meal_planner'))
        meal = MealPlanner.objects.get(user=self.user)
        self.assertEqual(meal.food_items, 'Rice and chicken')
        self.assertEqual(meal.meal_type, 'lunch')
        self.assertEqual(meal.date, date(2026, 10, 24))

    def test_add_workout(self):
        WorkoutPlan.objects.create(user=self.user)

        response = self.client.post(reverse('tools:add_workout'), {
            'date': '2026-10-24',
            'title': 'Push day',
            'exercises': 'Bench press',
            'duration_minutes': 45,
            'goal': 'Strength',
            'notes': '',
        })

        self.assertRedirects(response, reverse('tools:workout_hub'))
        workout = WorkoutPlanner.objects.get(user=self.user)
        self.assertEqual(workout.title, 'Push day')
        self.assertEqual(workout.date, date(2026, 10, 24))
