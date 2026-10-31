import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from fitlifeguide.domain import (
    MAX_EXERCISES,
    Workout,
    exercises_with_legacy,
    normalize_exercises,
    serialize_exercises,
)
from tools.forms import CustomExerciseForm, ExerciseForm, ExerciseFormSet
from tools.plan import get_plan_context, parse_week
from tools.repositories import MEAL_ORDER, create_custom_exercise, list_exercise_catalog, recent_exercises
from tools.views import _exercise_items, add_workout, create_exercise, edit_workout


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


def _formset_data(rows):
    data = {
        'exercises-TOTAL_FORMS': str(len(rows)),
        'exercises-INITIAL_FORMS': '0',
        'exercises-MIN_NUM_FORMS': '0',
        'exercises-MAX_NUM_FORMS': '30',
    }
    for index, row in enumerate(rows):
        for field, value in row.items():
            data[f'exercises-{index}-{field}'] = value
    return data


class ExerciseDataTests(SimpleTestCase):
    def test_free_text_is_kept_as_legacy_notes(self):
        exercises, legacy = exercises_with_legacy('Push-ups\n3x10 Squats')

        self.assertEqual(exercises, [])
        self.assertEqual(legacy, 'Push-ups\n3x10 Squats')

    def test_structured_strength_is_normalized(self):
        items = normalize_exercises([
            {'name': ' Bench press ', 'sets': 3, 'reps': '10', 'weight_kg': '80'},
        ])

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['name'], 'Bench press')
        self.assertEqual(items[0]['type'], 'strength')
        self.assertEqual(items[0]['sets'], 3)
        self.assertEqual(items[0]['reps'], 10)
        self.assertEqual(items[0]['weight_kg'], 80.0)
        self.assertEqual(items[0]['order'], 0)
        self.assertEqual(items[0]['display'], 'Bench press — 3×10 @ 80 kg')

    def test_timed_and_cardio_display(self):
        timed = normalize_exercises([{'name': 'Plank', 'type': 'timed', 'sets': 3, 'seconds': 45}])
        cardio = normalize_exercises([
            {'name': 'Run', 'type': 'cardio', 'minutes': 20, 'distance_km': 3.5},
        ])

        self.assertEqual(timed[0]['display'], 'Plank — 3×45 s')
        self.assertEqual(cardio[0]['display'], 'Run — 20 min · 3.5 km')

    def test_non_numeric_reps_are_preserved_as_legacy(self):
        exercises, legacy = exercises_with_legacy([
            {'name': 'Squat', 'sets': 3, 'reps': '8-10'},
            {'name': 'Bench press', 'sets': 3, 'reps': 8},
        ])

        self.assertEqual([item['name'] for item in exercises], ['Bench press'])
        self.assertEqual(legacy, 'Squat - 3x8-10')

    def test_serialization_orders_strips_ui_fields_and_caps(self):
        rows = [
            {
                'name': f'Exercise {index}',
                'type': 'strength',
                'sets': 3,
                'reps': 10,
                'weight_kg': 40,
                'order': MAX_EXERCISES - index,
                'display': 'ignored',
            }
            for index in range(MAX_EXERCISES + 2)
        ]

        items = serialize_exercises(rows)

        self.assertEqual(len(items), MAX_EXERCISES)
        self.assertEqual([item['order'] for item in items], list(range(MAX_EXERCISES)))
        self.assertNotIn('display', items[0])
        self.assertEqual(items[0]['weight_kg'], 40.0)

    def test_formset_builds_storage_rows_and_drops_blanks(self):
        formset = ExerciseFormSet(_formset_data([
            {
                'name': '  Bench press  ',
                'type': 'strength',
                'sets': '3',
                'reps': '10',
                'weight_kg': '80',
            },
            {'name': '', 'type': 'strength', 'sets': '', 'reps': ''},
        ]), prefix='exercises')

        self.assertTrue(formset.is_valid(), formset.errors)
        self.assertEqual(
            _exercise_items(formset),
            [{
                'name': 'Bench press',
                'type': 'strength',
                'order': 0,
                'sets': 3,
                'reps': 10,
                'weight_kg': 80.0,
            }],
        )

    def test_strength_requires_sets_and_reps(self):
        form = ExerciseForm({'name': 'Squat', 'type': 'strength', 'sets': '3'})

        self.assertFalse(form.is_valid())
        self.assertIn('reps', form.errors)

    def test_timed_requires_seconds(self):
        form = ExerciseForm({'name': 'Plank', 'type': 'timed', 'sets': '3'})

        self.assertFalse(form.is_valid())
        self.assertIn('seconds', form.errors)

    def test_cardio_requires_minutes(self):
        form = ExerciseForm({'name': 'Run', 'type': 'cardio', 'distance_km': '3'})

        self.assertFalse(form.is_valid())
        self.assertIn('minutes', form.errors)

    def test_name_is_trimmed_and_limited(self):
        valid = ExerciseForm({
            'name': '  Squat  ',
            'type': 'strength',
            'sets': '3',
            'reps': '5',
        })
        too_long = ExerciseForm({
            'name': 'x' * 81,
            'type': 'strength',
            'sets': '3',
            'reps': '5',
        })

        self.assertTrue(valid.is_valid())
        self.assertEqual(valid.cleaned_data['name'], 'Squat')
        self.assertFalse(too_long.is_valid())
        self.assertIn('name', too_long.errors)

    def test_formset_enforces_max_rows(self):
        rows = [
            {'name': f'Exercise {index}', 'type': 'strength', 'sets': '3', 'reps': '5'}
            for index in range(MAX_EXERCISES + 1)
        ]
        formset = ExerciseFormSet(_formset_data(rows), prefix='exercises')

        self.assertFalse(formset.is_valid())
        self.assertTrue(any('30' in str(error) for error in formset.non_form_errors()))

    def test_custom_exercise_form_trims_name(self):
        form = CustomExerciseForm({'name': '  Sled push  ', 'type': 'cardio'})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['name'], 'Sled push')


class FakeDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self.data = data

    def to_dict(self):
        return self.data


class FakeDocRef:
    def __init__(self, docs, doc_id):
        self.docs = docs
        self.id = doc_id

    def set(self, payload, merge=False):
        self.docs.append(FakeDoc(self.id, payload))


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def stream(self):
        return iter(self.docs)

    def where(self, field, operator, value):
        return FakeCollection([
            doc for doc in self.docs if doc.data.get(field) == value
        ])

    def document(self, doc_id=None):
        return FakeDocRef(self.docs, doc_id or f'new-{len(self.docs)}')


class FakeDB:
    def __init__(self, docs):
        self.collection_ref = FakeCollection(docs)

    def collection(self, name):
        return self.collection_ref


class ExerciseRepositoryTests(SimpleTestCase):
    def test_catalog_dedupes_case_insensitively_and_filters_owner(self):
        docs = [
            FakeDoc('squat', {'name': 'Squat', 'owner_id': '', 'type': 'strength', 'muscle_group': 'Legs'}),
            FakeDoc('bench', {'name': 'Bench press', 'owner_id': '', 'type': 'strength', 'muscle_group': 'Chest'}),
            FakeDoc('other', {'name': 'Squat', 'owner_id': 'user-2', 'type': 'strength'}),
            FakeDoc('mine', {'name': ' squat ', 'owner_id': 'user-1', 'type': 'strength', 'muscle_group': 'Custom'}),
            FakeDoc('row', {'name': 'Row', 'owner_id': 'user-1', 'type': 'strength', 'muscle_group': 'Back'}),
        ]

        with patch('tools.repositories.get_db', return_value=FakeDB(docs)):
            catalog = list_exercise_catalog('user-1')

        self.assertEqual([item['name'] for item in catalog], ['Bench press', 'Row', 'squat'])
        self.assertEqual(catalog[2]['muscle_group'], 'Custom')

    def test_custom_exercise_reuses_existing_name_and_enforces_cap(self):
        existing = [
            FakeDoc(f'custom-{index}', {
                'name': f'Custom {index}',
                'owner_id': 'user-1',
                'type': 'strength',
            })
            for index in range(50)
        ]

        with patch('tools.repositories.get_db', return_value=FakeDB(existing)):
            entry, created = create_custom_exercise('user-1', '  custom 1  ', 'timed')
            capped, capped_created = create_custom_exercise('user-1', 'New exercise', 'strength')

        self.assertFalse(created)
        self.assertEqual(entry['name'], 'Custom 1')
        self.assertEqual(len(existing), 50)
        self.assertIsNone(capped)
        self.assertFalse(capped_created)

    def test_recent_exercises_uses_last_ten_workouts_and_dedupes(self):
        workouts = [
            Workout(
                id='workout-1',
                date=date(2026, 10, 20),
                week_start=date(2026, 10, 19),
                day_of_week='Tue',
                title='Session',
                exercises=normalize_exercises([
                    {'name': 'Squat', 'sets': 3, 'reps': 5},
                    {'name': 'Bench press', 'sets': 3, 'reps': 8},
                ]),
            ),
            Workout(
                id='workout-2',
                date=date(2026, 10, 19),
                week_start=date(2026, 10, 19),
                day_of_week='Mon',
                title='Session',
                exercises=normalize_exercises([
                    {'name': 'squat', 'sets': 3, 'reps': 5},
                    {'name': 'Row', 'sets': 3, 'reps': 10},
                    {'name': 'Run', 'type': 'cardio', 'minutes': 20},
                    {'name': 'Plank', 'type': 'timed', 'sets': 3, 'seconds': 45},
                ]),
            ),
            *[
                Workout(
                    id=f'workout-{index}',
                    date=date(2026, 10, 10),
                    week_start=date(2026, 10, 5),
                    day_of_week='Sat',
                    title='Older session',
                    exercises=normalize_exercises([
                        {'name': f'Older {index}', 'sets': 3, 'reps': 8},
                    ]),
                )
                for index in range(3, 11)
            ],
        ]

        with patch('tools.repositories.list_workouts_by_user', return_value=workouts) as list_workouts:
            recent = recent_exercises('user-1', limit=4)

        list_workouts.assert_called_once_with('user-1', limit=10)
        self.assertEqual([item['name'] for item in recent], ['Squat', 'Bench press', 'Row', 'Run'])


class WorkoutFormViewTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.user = SimpleNamespace(id='user-1')
        self.context_patch = patch(
            'tools.views._exercise_context',
            return_value={'exercise_catalog': [], 'recent_exercises': [], 'max_exercises': 30},
        )
        self.context_patch.start()
        self.addCleanup(self.context_patch.stop)

    def _post(self, url, rows):
        data = _formset_data(rows)
        data.update({
            'date': '2026-10-31',
            'title': 'Leg day',
            'duration_minutes': '45',
            'goal': 'Get stronger',
            'notes': '',
        })
        request = self.rf.post(url, data)
        request.user = self.user
        return request

    def test_add_workout_saves_structured_exercises(self):
        request = self._post('/add-workout/', [{
            'name': 'Back squat',
            'type': 'strength',
            'sets': '4',
            'reps': '8',
            'weight_kg': '80',
        }])

        with (
            patch('tools.views.create_workout') as create_workout,
            patch('tools.views.messages.success'),
        ):
            response = add_workout.__wrapped__(request)

        self.assertEqual(response.status_code, 302)
        create_workout.assert_called_once()
        self.assertEqual(
            create_workout.call_args.args[3],
            [{
                'name': 'Back squat',
                'type': 'strength',
                'order': 0,
                'sets': 4,
                'reps': 8,
                'weight_kg': 80.0,
            }],
        )

    def test_add_workout_rejects_invalid_numbers(self):
        request = self._post('/add-workout/', [{
            'name': 'Back squat',
            'type': 'strength',
            'sets': '4',
            'reps': 'many',
        }])

        with (
            patch('tools.views.create_workout') as create_workout,
            patch('tools.views.render') as render,
        ):
            add_workout.__wrapped__(request)

        create_workout.assert_not_called()
        context = render.call_args.args[2]
        self.assertFalse(context['exercise_formset'].is_valid())

    def test_edit_workout_preserves_legacy_text(self):
        workout = Workout(
            id='workout-1',
            date=date(2026, 10, 31),
            week_start=date(2026, 10, 26),
            day_of_week='Sat',
            title='Leg day',
            exercises=normalize_exercises([
                {'name': 'Old squat', 'sets': 3, 'reps': '8-10'},
            ]),
            legacy_exercises_text='Old squat - 3x8-10',
        )
        request = self._post('/edit-workout/workout-1/', [{
            'name': 'Back squat',
            'type': 'strength',
            'sets': '4',
            'reps': '8',
        }])

        with (
            patch('tools.views.get_workout', return_value=workout),
            patch('tools.views.update_workout') as update_workout,
            patch('tools.views.messages.success'),
        ):
            response = edit_workout.__wrapped__(request, 'workout-1')

        self.assertEqual(response.status_code, 302)
        update_workout.assert_called_once()
        self.assertEqual(update_workout.call_args.args[7], 'Old squat - 3x8-10')


class CustomExerciseEndpointTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.user = SimpleNamespace(id='user-1')

    def _request(self, payload):
        request = self.rf.post(
            '/exercises/create/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        request.user = self.user
        return request

    def test_endpoint_requires_login(self):
        request = self.rf.post('/exercises/create/', data='{}', content_type='application/json')
        request.user = AnonymousUser()

        response = create_exercise(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_endpoint_creates_trimmed_custom_exercise(self):
        request = self._request({'name': '  Sled push  ', 'type': 'cardio'})

        with patch('tools.views.create_custom_exercise', return_value=(
            {'name': 'Sled push', 'muscle_group': 'Custom', 'type': 'cardio'},
            True,
        )) as create:
            response = create_exercise.__wrapped__(request)

        self.assertEqual(response.status_code, 201)
        create.assert_called_once_with('user-1', 'Sled push', 'cardio')
        self.assertEqual(json.loads(response.content)['name'], 'Sled push')

    def test_endpoint_rejects_blank_name(self):
        request = self._request({'name': '   ', 'type': 'strength'})

        with patch('tools.views.create_custom_exercise') as create:
            response = create_exercise.__wrapped__(request)

        self.assertEqual(response.status_code, 400)
        create.assert_not_called()

    def test_endpoint_reports_custom_cap(self):
        request = self._request({'name': 'Sled push', 'type': 'cardio'})

        with patch('tools.views.create_custom_exercise', return_value=(None, False)):
            response = create_exercise.__wrapped__(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('custom exercises', json.loads(response.content)['error'])

    def test_endpoint_rejects_invalid_json(self):
        request = self.rf.post(
            '/exercises/create/',
            data='{not json',
            content_type='application/json',
        )
        request.user = self.user

        response = create_exercise.__wrapped__(request)

        self.assertEqual(response.status_code, 400)
