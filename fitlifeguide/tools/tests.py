from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from fitlifeguide.domain import normalize_exercises
from tools.forms import ExerciseFormSet
from tools.plan import get_plan_context, parse_week
from tools.repositories import MEAL_ORDER
from tools.views import _exercise_items


class WorkoutHubRedirectTests(SimpleTestCase):
    def test_workout_hub_redirects_to_plan(self):
        response = self.client.get('/workout-hub/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, '/plan/')


class WorkoutDetailUrlTests(SimpleTestCase):
    def test_workout_detail_url_resolves(self):
        self.assertEqual(reverse('tools:workout_detail', args=['abc']), '/workout/abc/')

    def test_workout_detail_requires_login(self):
        response = self.client.get(reverse('tools:workout_detail', args=['abc']))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)


class PlanHelperTests(SimpleTestCase):
    def test_parse_week_normalizes_to_monday(self):
        self.assertEqual(parse_week('2026-10-29'), date(2026, 10, 26))

    def test_parse_week_falls_back_to_today(self):
        with patch('tools.plan.timezone.localdate', return_value=date(2026, 10, 29)):
            self.assertEqual(parse_week('not-a-date'), date(2026, 10, 26))
            self.assertEqual(parse_week(None), date(2026, 10, 26))

    def test_meal_order_has_one_entry_per_meal(self):
        self.assertEqual(MEAL_ORDER, ('breakfast', 'lunch', 'dinner', 'snack'))
        self.assertEqual(len(MEAL_ORDER), len(set(MEAL_ORDER)))

    def test_plan_context_marks_today_and_rest_days(self):
        user = SimpleNamespace(id='user-1')
        today = date(2026, 10, 21)
        week_start = date(2026, 10, 19)

        with (
            patch('tools.plan.list_workouts_between', return_value=[]),
            patch('tools.plan.list_meals_between', return_value=[]),
            patch('tools.plan.community_meals', return_value=[]),
            patch('tools.plan.community_workouts', return_value=[]),
            patch('tools.plan.timezone.localdate', return_value=today),
        ):
            context = get_plan_context(user, week_start)

        self.assertTrue(context['today_in_week'])
        self.assertEqual(len(context['days']), 7)
        self.assertEqual(
            [day['status'] for day in context['days']],
            ['Rest', 'Rest', 'Today', 'Rest', 'Rest', 'Rest', 'Rest'],
        )
        self.assertEqual(
            [day['expanded'] for day in context['days']],
            [False, False, True, False, False, False, False],
        )


class ExerciseDataTests(SimpleTestCase):
    def test_free_text_exercises_are_normalized(self):
        items = normalize_exercises('Push-ups\n3x10 Squats')

        self.assertEqual(
            items,
            [
                {'name': 'Push-ups', 'sets': None, 'reps': ''},
                {'name': '3x10 Squats', 'sets': None, 'reps': ''},
            ],
        )

    def test_structured_exercises_are_kept(self):
        items = normalize_exercises([
            {'name': 'Bench Press', 'sets': 3, 'reps': '10'},
        ])

        self.assertEqual(
            items,
            [{'name': 'Bench Press', 'sets': 3, 'reps': '10'}],
        )

    def test_formset_drops_blank_rows(self):
        formset = ExerciseFormSet({
            'exercises-TOTAL_FORMS': '2',
            'exercises-INITIAL_FORMS': '0',
            'exercises-MIN_NUM_FORMS': '0',
            'exercises-MAX_NUM_FORMS': '1000',
            'exercises-0-name': 'Bench Press',
            'exercises-0-sets': '3',
            'exercises-0-reps': '10',
            'exercises-1-name': '',
            'exercises-1-sets': '',
            'exercises-1-reps': '',
        }, prefix='exercises')

        self.assertTrue(formset.is_valid())
        self.assertEqual(
            _exercise_items(formset),
            [{'name': 'Bench Press', 'sets': 3, 'reps': '10'}],
        )
