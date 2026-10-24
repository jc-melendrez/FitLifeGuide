import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from community.models import BlogPost


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
