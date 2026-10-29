from django.test import SimpleTestCase
from django.utils import timezone

from fitlifeguide.domain import (
    DEFAULT_AVATAR,
    Comment,
    CommentList,
    author_from_doc,
)


class CommentTreeTests(SimpleTestCase):
    def test_comment_list_supports_queryset_like_checks(self):
        comments = CommentList()
        self.assertFalse(comments.exists)
        self.assertEqual(comments.count, 0)

        comments.append(self._comment('one'))
        self.assertTrue(comments.exists)
        self.assertEqual(comments.count, 1)

    def test_descendant_count_walks_children(self):
        parent = self._comment('parent')
        child = self._comment('child')
        grandchild = self._comment('grandchild')
        child.children.append(grandchild)
        parent.children.append(child)

        self.assertEqual(parent.get_descendant_count, 2)
        self.assertFalse(parent.is_leaf_node)
        self.assertTrue(grandchild.is_leaf_node)

    def test_author_from_doc_uses_default_avatar(self):
        author = author_from_doc({'author_id': 'u1', 'author_username': 'runner'})
        self.assertEqual(author.id, 'u1')
        self.assertEqual(author.username, 'runner')
        self.assertEqual(author.avatar_url, DEFAULT_AVATAR)

    def _comment(self, content):
        return Comment(
            id=content,
            post_id='post-1',
            author=author_from_doc({}),
            content=content,
            created_at=timezone.now(),
        )
