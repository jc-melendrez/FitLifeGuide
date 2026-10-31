from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from mainpage.repositories import search_posts, search_workouts


class SearchTests(SimpleTestCase):
    @patch('mainpage.repositories.list_posts')
    def test_search_posts_is_case_insensitive_and_only_published(self, list_posts):
        list_posts.return_value = [
            SimpleNamespace(published=True, title='Beginner Strength', content='Start here'),
            SimpleNamespace(published=False, title='Draft Strength', content='Hidden'),
            SimpleNamespace(published=True, title='Cardio', content='Run'),
        ]

        results = search_posts('strength')

        self.assertEqual([post.title for post in results], ['Beginner Strength'])

    @patch('mainpage.repositories.list_workouts_by_user')
    def test_search_workouts_only_returns_owner_matches(self, list_workouts):
        list_workouts.return_value = [
            SimpleNamespace(
                title='Push day',
                exercises=[{'name': 'Bench press', 'type': 'strength', 'sets': 3, 'reps': 8}],
                legacy_exercises_text='',
            ),
            SimpleNamespace(
                title='Leg day',
                exercises=[{'name': 'Squat', 'type': 'strength', 'sets': 3, 'reps': 5}],
                legacy_exercises_text='',
            ),
            SimpleNamespace(
                title='Old session',
                exercises=[],
                legacy_exercises_text='Bench press 3x10',
            ),
        ]

        results = search_workouts('user-1', 'bench')

        self.assertEqual([workout.title for workout in results], ['Push day', 'Old session'])
        list_workouts.assert_called_once_with('user-1')
