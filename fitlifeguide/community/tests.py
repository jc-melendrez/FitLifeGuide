import base64
import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tools.models import WorkoutPlan, WorkoutPlanner

from .models import BlogComment, BlogPost, Forum, ForumPost, Thread


class CommunityTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)

        self.user = User.objects.create_user('logger', 'logger@example.com', 'Str0ngPass!234')
        self.other = User.objects.create_user('other', 'other@example.com', 'Str0ngPass!234')
        self.client.force_login(self.user)

        self.workout_plan = WorkoutPlan.objects.create(user=self.user)
        self.workout = WorkoutPlanner.objects.create(
            user=self.user,
            workout_plan=self.workout_plan,
            date=date(2026, 10, 21),
            week_start=date(2026, 10, 19),
            day_of_week='Wed',
            title='Lower Body',
            exercises='Squats',
            duration_minutes=45,
            goal='Strength',
            status='completed',
        )
        self.post = BlogPost.objects.create(
            title='Leg day done',
            author=self.user,
            content='Five sets of squats.',
            published=True,
            workout=self.workout,
        )
        self.forum = Forum.objects.create(name='Training', description='Talk training.')
        self.thread = Thread.objects.create(
            forum=self.forum,
            title='Best leg day?',
            author=self.user,
            content='What is your go-to leg day?',
        )
        ForumPost.objects.create(
            thread=self.thread,
            author=self.user,
            content='Squats and lunges.',
        )

    def test_posts_page_shows_training_log_details(self):
        response = self.client.get(reverse('posts'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Training <span class="fl-lime">log</span>', html=True)
        self.assertContains(response, 'Lower Body')
        self.assertContains(response, '45 min')
        self.assertContains(response, 'fl-log')

    def test_post_timestamp_uses_one_unit(self):
        BlogPost.objects.filter(pk=self.post.pk).update(
            created_at=timezone.now() - timedelta(days=400)
        )

        response = self.client.get(reverse('posts'))

        self.assertContains(response, '1\u00a0year ago')
        self.assertNotContains(response, 'year,')
        self.assertContains(response, 'fl-log-time')

    def test_create_post_links_workout_and_image(self):
        image = SimpleUploadedFile(
            'session.gif',
            base64.b64decode('R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='),
            content_type='image/gif',
        )

        response = self.client.post(reverse('create_post'), {
            'title': 'New session',
            'content': 'Felt strong.',
            'workout': self.workout.id,
            'published': 'on',
            'image': image,
        })

        self.assertRedirects(response, reverse('posts'))
        post = BlogPost.objects.get(title='New session')
        self.assertEqual(post.workout, self.workout)
        self.assertTrue(post.image.name.startswith('post_pics/'))

    def test_create_post_rejects_another_users_workout(self):
        other_plan = WorkoutPlan.objects.create(user=self.other)
        other_workout = WorkoutPlanner.objects.create(
            user=self.other,
            workout_plan=other_plan,
            date=date(2026, 10, 22),
            week_start=date(2026, 10, 19),
            day_of_week='Thu',
            title='Private workout',
            exercises='Rows',
        )

        response = self.client.post(reverse('create_post'), {
            'title': 'Bad link',
            'content': 'Should fail.',
            'workout': other_workout.id,
            'published': 'on',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(BlogPost.objects.filter(title='Bad link').exists())

    def test_post_detail_shows_workout_and_comments(self):
        BlogComment.objects.create(post=self.post, author=self.user, content='Nice work.')

        response = self.client.get(reverse('post_detail', args=[self.post.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lower Body')
        self.assertContains(response, 'Nice work.')
        self.assertContains(response, 'fl-comments')

    def test_forum_pages_use_fl_layout(self):
        for url, marker in (
            (reverse('forum_list'), 'fl-forum-grid'),
            (reverse('forum_threads', args=[self.forum.slug]), 'fl-thread-list'),
            (reverse('thread_detail', args=[self.thread.slug]), 'fl-replies'),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, marker)

    def test_like_post_returns_json(self):
        response = self.client.post(reverse('like_post', args=[self.post.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['liked'])
        self.assertEqual(response.json()['total_likes'], 1)
