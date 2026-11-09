from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.auths.models import User
from apps.blog.models import Category, Comment, Post, Tag


class BlogRelationshipTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            "author@example.com",
            "Test-password-974!",
            first_name="Test",
            last_name="Author",
        )
        self.category = Category.objects.create(name="Python", slug="python")
        self.post = Post.objects.create(
            author=self.user,
            category=self.category,
            title="First post",
            slug="first-post",
            body="Hello",
        )
        self.comment = Comment.objects.create(post=self.post, author=self.user, body="A comment")

    def test_category_delete_preserves_post(self) -> None:
        self.category.delete()
        self.post.refresh_from_db()
        self.assertIsNone(self.post.category)
        self.assertEqual(self.post.status, Post.Status.DRAFT)

    def test_post_delete_removes_comments(self) -> None:
        self.post.delete()
        self.assertFalse(Comment.objects.exists())

    def test_author_delete_removes_content(self) -> None:
        self.user.delete()
        self.assertFalse(Post.objects.exists())
        self.assertFalse(Comment.objects.exists())

    def test_tags_and_unique_slug(self) -> None:
        tag = Tag.objects.create(name="Django", slug="django")
        self.post.tags.add(tag)
        self.assertEqual(list(tag.posts.all()), [self.post])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Post.objects.create(author=self.user, title="Duplicate", slug="first-post", body="Body")
