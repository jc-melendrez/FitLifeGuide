import tempfile
from datetime import date, timedelta
from unittest.mock import patch

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


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class PlanTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('planuser', 'plan@example.com', 'Str0ngPass!234')
        self.client.force_login(self.user)
        self.week_start = date(2026, 10, 19)
        self.today = date(2026, 10, 21)
        self.now_patcher = patch('tools.plan.timezone.localdate', return_value=self.today)
        self.now_patcher.start()
        self.addCleanup(self.now_patcher.stop)
        self.meal_plan = MealPlan.objects.create(user=self.user)
        self.workout_plan = WorkoutPlan.objects.create(user=self.user)

    def _meal(self, meal_date, meal_type, food='Meal', status='planned', week_start=None,
              calories=None, notes=''):
        return MealPlanner.objects.create(
            user=self.user,
            meal_plan=self.meal_plan,
            date=meal_date,
            week_start=week_start or self.week_start,
            day_of_week=meal_date.strftime('%a'),
            meal_type=meal_type,
            food_items=food,
            calories=calories,
            notes=notes,
            status=status,
        )

    def _workout(self, workout_date, title='Workout', status='planned', week_start=None,
                 exercises='Move', duration_minutes=None, goal='', notes=''):
        return WorkoutPlanner.objects.create(
            user=self.user,
            workout_plan=self.workout_plan,
            date=workout_date,
            week_start=week_start or self.week_start,
            day_of_week=workout_date.strftime('%a'),
            title=title,
            exercises=exercises,
            duration_minutes=duration_minutes,
            goal=goal,
            notes=notes,
            status=status,
        )

    def test_plan_renders_empty_week(self):
        response = self.client.get(reverse('tools:plan'), {'week': '2026-10-19'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '+ Add workout')
        self.assertContains(response, 'No community ideas yet.')

    def test_plan_expands_today_only(self):
        response = self.client.get(reverse('tools:plan'), {'week': '2026-10-19'})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['today_in_week'])
        self.assertEqual(
            [day['expanded'] for day in response.context['days']],
            [False, False, True, False, False, False, False],
        )
        self.assertContains(response, 'aria-expanded="true"', count=1)

    def test_plan_has_no_expansion_outside_today_week(self):
        response = self.client.get(reverse('tools:plan'), {'week': '2026-10-26'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['today_in_week'])
        self.assertFalse(any(day['expanded'] for day in response.context['days']))
        self.assertNotContains(response, 'aria-expanded="true"')
        self.assertContains(response, 'data-plan-today')

    def test_plan_past_and_future_results(self):
        self._workout(self.week_start, 'Done workout', status='completed')
        self._meal(self.week_start + timedelta(days=1), 'lunch', 'Missed lunch')
        self._workout(self.week_start + timedelta(days=3), 'Future workout')

        response = self.client.get(reverse('tools:plan'), {'week': '2026-10-19'})
        days = response.context['days']

        self.assertEqual(days[0]['status'], 'Done')
        self.assertEqual(days[1]['status'], 'Missed')
        self.assertEqual(days[2]['status'], 'Today')
        self.assertEqual(days[3]['status'], 'Planned')

        self.assertEqual(days[4]['status'], 'Rest')
        self.assertContains(response, 'is-missed')

    def test_plan_workout_statuses(self):
        self._workout(self.week_start, 'Done workout', status='completed')
        self._workout(self.week_start + timedelta(days=1), 'Missed workout')
        self._workout(self.week_start + timedelta(days=2), 'Today workout')
        self._workout(self.week_start + timedelta(days=3), 'Planned workout')

        response = self.client.get(reverse('tools:plan'), {'week': '2026-10-19'})
        statuses = [day['workout_status'] for day in response.context['days']]

        self.assertEqual(
            statuses,
            ['Done', 'Missed', 'Planned', 'Planned', 'Rest', 'Rest', 'Rest'],
        )

    def test_plan_compact_content_respects_view(self):
        self._meal(self.week_start, 'lunch', 'Rice and chicken')
        self._workout(self.week_start, 'Lower Body')

        both = self.client.get(reverse('tools:plan'), {'week': '2026-10-19'})
        meals = self.client.get(
            reverse('tools:plan'),
            {'week': '2026-10-19', 'view': 'meals'},
        )
        workouts = self.client.get(
            reverse('tools:plan'),
            {'week': '2026-10-19', 'view': 'workouts'},
        )

        both_html = both.content.decode()
        meals_html = meals.content.decode()
        workouts_html = workouts.content.decode()

        self.assertEqual(both_html.count('fl-plan-compact-workout'), 7)
        self.assertEqual(both_html.count('fl-plan-compact-meal-bar'), 28)
        self.assertEqual(meals_html.count('fl-plan-compact-workout'), 0)
        self.assertEqual(meals_html.count('fl-plan-compact-meal-bar'), 28)
        self.assertEqual(workouts_html.count('fl-plan-compact-workout'), 7)
        self.assertEqual(workouts_html.count('fl-plan-compact-meal-bar'), 0)
        self.assertNotContains(meals, 'Lower Body')
        self.assertContains(workouts, 'Lower Body')

    def test_plan_expanded_sections_respect_view(self):
        both = self.client.get(reverse('tools:plan'), {'week': '2026-10-19'})
        meals = self.client.get(
            reverse('tools:plan'),
            {'week': '2026-10-19', 'view': 'meals'},
        )
        workouts = self.client.get(
            reverse('tools:plan'),
            {'week': '2026-10-19', 'view': 'workouts'},
        )

        self.assertEqual(both.content.decode().count('fl-plan-add'), 35)
        self.assertEqual(meals.content.decode().count('fl-plan-add'), 28)
        self.assertEqual(workouts.content.decode().count('fl-plan-add'), 7)

    def test_plan_links_and_copy_preserve_view(self):
        response = self.client.get(
            reverse('tools:plan'),
            {'week': '2026-10-19', 'view': 'meals'},
        )

        self.assertContains(response, '/plan/?view=meals')
        self.assertContains(response, 'name="view" value="meals"')
        self.assertContains(response, 'Copy meals + workouts')

    def test_plan_shows_meals_and_workouts(self):
        self._meal(self.week_start, 'lunch', 'Rice and chicken')
        self._workout(self.week_start, 'Lower Body')

        response = self.client.get(reverse('tools:plan'), {'week': '2026-10-19'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rice and chicken')
        self.assertContains(response, 'Lower Body')
        self.assertContains(response, 'Your')

    def test_plan_can_hide_workouts(self):
        self._meal(self.week_start, 'lunch', 'Rice and chicken')
        self._workout(self.week_start, 'Lower Body')

        response = self.client.get(
            reverse('tools:plan'),
            {'week': '2026-10-19', 'view': 'meals'},
        )

        self.assertContains(response, 'Rice and chicken')
        self.assertNotContains(response, 'Lower Body')

    def test_copy_last_week_keeps_existing_entries(self):
        source_week = self.week_start - timedelta(days=7)
        self._meal(
            source_week,
            'breakfast',
            'Source breakfast',
            status='eaten',
            week_start=source_week,
            calories=450,
            notes='Source meal note',
        )
        self._meal(source_week, 'lunch', 'Source lunch', week_start=source_week)
        self._meal(self.week_start, 'lunch', 'Keep lunch')
        self._workout(source_week, 'Source Monday', week_start=source_week)
        self._workout(
            source_week + timedelta(days=1),
            'Source Tuesday',
            status='completed',
            week_start=source_week,
            exercises='Squat',
            duration_minutes=50,
            goal='Legs',
            notes='Source workout note',
        )
        self._workout(self.week_start, 'Keep Monday')

        response = self.client.post(
            reverse('tools:copy_last_week'),
            {'week': '2026-10-19', 'view': 'meals'},
        )

        self.assertRedirects(
            response,
            reverse('tools:plan') + '?week=2026-10-19&view=meals',
        )
        self.assertEqual(
            MealPlanner.objects.filter(user=self.user, week_start=self.week_start).count(),
            2,
        )
        self.assertEqual(
            MealPlanner.objects.get(
                user=self.user,
                date=self.week_start,
                meal_type='lunch',
            ).food_items,
            'Keep lunch',
        )
        copied_meal = MealPlanner.objects.get(
            user=self.user,
            date=self.week_start,
            meal_type='breakfast',
        )
        self.assertEqual(copied_meal.food_items, 'Source breakfast')
        self.assertEqual(copied_meal.calories, 450)
        self.assertEqual(copied_meal.notes, 'Source meal note')
        self.assertEqual(copied_meal.status, 'planned')
        self.assertEqual(
            WorkoutPlanner.objects.filter(user=self.user, week_start=self.week_start).count(),
            2,
        )
        self.assertEqual(
            WorkoutPlanner.objects.get(user=self.user, date=self.week_start).title,
            'Keep Monday',
        )
        copied_workout = WorkoutPlanner.objects.get(
            user=self.user,
            date=self.week_start + timedelta(days=1),
        )
        self.assertEqual(copied_workout.title, 'Source Tuesday')
        self.assertEqual(copied_workout.exercises, 'Squat')
        self.assertEqual(copied_workout.duration_minutes, 50)
        self.assertEqual(copied_workout.goal, 'Legs')
        self.assertEqual(copied_workout.notes, 'Source workout note')
        self.assertEqual(copied_workout.status, 'planned')

    def test_copy_last_week_redirects_with_view(self):
        response = self.client.post(
            reverse('tools:copy_last_week'),
            {'week': '2026-10-19', 'view': 'workouts'},
        )

        self.assertRedirects(
            response,
            reverse('tools:plan') + '?week=2026-10-19&view=workouts',
        )

    def test_add_meal_returns_to_next_url(self):
        response = self.client.post(
            reverse('tools:add_meal')
            + '?date=2026-10-24&meal_type=lunch&next=/plan/?week=2026-10-19',
            {'food_items': 'Oats', 'calories': 300, 'notes': ''},
        )

        self.assertRedirects(response, '/plan/?week=2026-10-19')

    def test_add_meal_ignores_external_next_url(self):
        response = self.client.post(
            reverse('tools:add_meal')
            + '?date=2026-10-24&meal_type=lunch&next=https://evil.example/steal',
            {'food_items': 'Oats', 'calories': 300, 'notes': ''},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('tools:meal_planner'))

    def test_add_workout_returns_to_next_url(self):
        response = self.client.post(
            reverse('tools:add_workout') + '?next=/plan/?week=2026-10-19',
            {
                'date': '2026-10-24',
                'title': 'Push day',
                'exercises': 'Bench press',
                'duration_minutes': 45,
                'goal': 'Strength',
                'notes': '',
            },
        )

        self.assertRedirects(response, '/plan/?week=2026-10-19')
