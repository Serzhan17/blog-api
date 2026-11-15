"""Regression tests for chronology, SQL budgets and ORM edge cases."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.models import QuerySet
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.auths.models import User
from apps.blog import queries as q
from apps.blog.management.commands.queries import sample_arguments
from apps.blog.models import Category, Comment, Post, Tag


class QueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create(
            email="john@example.com", first_name="John", last_name="Smith"
        )
        cls.staff = User.objects.create(email="staff@example.com", is_staff=True)
        cls.inactive = User.objects.create(email="inactive@example.com", is_active=False)
        cls.empty_user = User.objects.create(email="empty@example.com")
        cls.category = Category.objects.create(name="Python", slug="python")
        cls.empty_category = Category.objects.create(name="Empty", slug="empty")
        cls.tag = Tag.objects.create(name="Python", slug="python")
        cls.tag2 = Tag.objects.create(name="Django", slug="django")
        cls.p1 = Post.objects.create(
            author=cls.author,
            title="Python API",
            slug="p1",
            body="first",
            category=cls.category,
            status=Post.Status.PUBLISHED,
        )
        cls.p2 = Post.objects.create(
            author=cls.author,
            title="Other",
            slug="p2",
            body="API body",
            status=Post.Status.PUBLISHED,
        )
        cls.draft = Post.objects.create(author=cls.author, title="Draft", slug="draft")
        cls.p1.tags.add(cls.tag, cls.tag2)
        cls.p2.tags.add(cls.tag)
        cls.now = timezone.now()
        for post, age in [(cls.p1, 60), (cls.p2, 20), (cls.draft, 10)]:
            created = cls.now - timedelta(days=age)
            Post.objects.filter(pk=post.pk).update(created_at=created, updated_at=created)
        cls.c1 = Comment.objects.create(post=cls.p1, author=cls.author, body="old")
        cls.c2 = Comment.objects.create(post=cls.p1, author=cls.staff, body="latest")
        cls.c3 = Comment.objects.create(post=cls.p1, author=cls.inactive, body="inactive")
        Comment.objects.filter(pk=cls.c2.pk).update(created_at=cls.now)
        Comment.objects.exclude(pk=cls.c2.pk).update(created_at=cls.now - timedelta(days=1))

    def test_every_read_query_sql_budget(self):
        args = sample_arguments()
        for number, function in q.QUERIES.items():
            if 40 <= number <= 44:
                continue
            with self.subTest(number=number):
                with CaptureQueriesContext(connection) as captured:
                    result = function(**args.get(number, {}))
                    if isinstance(result, QuerySet):
                        list(result)
                self.assertEqual(len(captured), 2 if number in (46, 47) else 1)

    def test_filters_and_projections(self):
        self.assertEqual(list(q.categories_by_name()), [self.empty_category, self.category])
        self.assertEqual(list(q.published_posts()), [self.p2, self.p1])
        self.assertEqual(list(q.newest_published_posts()), [self.p2, self.p1])
        self.assertIsNone(q.post_by_slug("missing"))
        self.assertEqual(q.post_by_slug("p1"), self.p1)
        self.assertEqual(q.active_users_count(), 2)
        self.assertTrue(q.has_drafts())
        self.assertEqual(list(q.published_posts_page(2)), [])
        self.assertEqual(list(q.posts_with_word_in_title("PYTHON")), [self.p1])
        self.assertEqual(q.users_with_email_domain("EXAMPLE.COM").count(), 4)
        self.assertEqual(set(q.posts_without_category()), {self.p2, self.draft})
        self.assertEqual(list(q.categories_by_slugs(["python"])), [self.category])
        self.assertEqual(list(q.author_published_posts("JOHN@EXAMPLE.COM")), [self.p2, self.p1])
        self.assertEqual(set(q.posts_with_tag("python")), {self.p1, self.p2})
        self.assertEqual(q.comments_in_category("python").count(), 3)
        self.assertEqual(list(q.users_with_published_posts()), [self.author])
        self.assertEqual(list(q.posts_without_tags()), [self.draft])
        self.assertEqual(list(q.users_without_comments()), [self.empty_user])
        self.assertEqual(list(q.posts_with_both_tags("python", "django")), [self.p1])
        self.assertEqual(set(q.search_posts("api")), {self.p1, self.p2})
        self.assertEqual(list(q.published_posts_missing_info()), [self.p2])
        self.assertEqual(list(q.comments_by_post_author()), [self.c1])
        self.assertFalse(q.comments_before_post().exists())
        self.assertEqual(q.published_authors_emails(), [self.author.email])
        overview = q.published_posts_overview()
        self.assertEqual(set(overview[0]), {"title", "author_email", "category_name"})
        self.assertEqual(overview[0]["category_name"], "Uncategorized")

    def test_dates_and_boundaries(self):
        self.p1.refresh_from_db()
        day = timezone.localdate(self.p1.created_at)
        self.assertEqual(list(q.posts_between(day, day)), [self.p1])
        self.assertIn(self.p1, q.posts_in_month(day.year, day.month))
        self.assertEqual(set(q.posts_last_days(30)), {self.p2, self.draft})
        Post.objects.filter(pk=self.p1.pk).update(
            updated_at=self.p1.created_at + timedelta(hours=1)
        )
        self.assertFalse(q.edited_posts().exists())
        Post.objects.filter(pk=self.p1.pk).update(
            updated_at=self.p1.created_at + timedelta(hours=2)
        )
        self.assertEqual(list(q.edited_posts()), [self.p1])

    def test_aggregates_annotations_and_subqueries(self):
        stats = q.posts_stats()
        self.assertEqual((stats["total"], stats["published"], stats["drafts"]), (3, 2, 1))
        self.assertEqual(q.average_comments_per_post(), 1.5)
        self.assertEqual(q.categories_with_post_count().first().post_count, 1)
        self.assertEqual(
            q.categories_with_published_count().get(pk=self.empty_category.pk).published_count, 0
        )
        self.assertEqual(q.top_authors()[0].published_count, 2)
        self.assertEqual(list(q.popular_tags(2)), [self.tag])
        self.assertEqual(
            q.posts_per_status(),
            [{"status": "draft", "count": 1}, {"status": "published", "count": 2}],
        )
        activity = q.users_activity().get(pk=self.author.pk)
        self.assertEqual((activity.post_count, activity.comment_count), (3, 1))
        self.assertEqual(q.search_users_by_full_name("john smi").get().full_name, "John Smith")
        self.assertEqual(sum(row["count"] for row in q.published_posts_per_month()), 2)
        self.assertEqual(q.posts_with_popularity().get(pk=self.p1.pk).popularity, "normal")
        self.assertEqual(q.posts_with_popularity().get(pk=self.p2.pk).popularity, "quiet")
        Comment.objects.bulk_create(
            [Comment(post=self.p1, author=self.author, body="extra") for _ in range(7)]
        )
        self.assertEqual(q.posts_with_popularity().get(pk=self.p1.pk).popularity, "hot")
        Comment.objects.filter(body="extra").delete()
        self.assertEqual(q.posts_with_last_comment().get(pk=self.p1.pk).last_comment, "latest")
        self.assertIsNone(q.posts_with_last_comment().get(pk=self.p2.pk).last_comment)
        self.assertEqual(list(q.posts_with_staff_comments()), [self.p1])
        self.assertEqual(list(q.users_with_draft_as_latest_post()), [self.author])
        self.assertEqual(
            q.users_with_draft_as_latest_post().get().latest_post_status, Post.Status.DRAFT
        )

    def test_related_output(self):
        self.assertEqual(
            q.published_feed(),
            ["Other | john@example.com | Uncategorized", "Python API | john@example.com | Python"],
        )
        self.assertIn("Python API: Django, Python", q.newest_posts_with_tags())
        self.assertEqual(
            q.categories_with_published_posts(), {"Empty": [], "Python": ["Python API"]}
        )

    def test_mutations(self):
        tag, created = q.get_or_create_tag("Django ORM")
        self.assertTrue(created)
        self.assertEqual(q.get_or_create_tag("django orm"), (tag, False))
        old = self.now - timedelta(days=90)
        Post.objects.filter(pk=self.draft.pk).update(created_at=old, updated_at=old)
        with self.assertNumQueries(1):
            self.assertEqual(q.publish_old_drafts(30), 1)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Post.Status.PUBLISHED)
        self.assertGreater(self.draft.updated_at, old)
        self.assertEqual(q.tag_category_posts("python", "django"), 1)
        self.assertEqual(q.tag_category_posts("python", "django"), 1)
        self.assertEqual(self.p1.tags.count(), 2)
        self.assertEqual(q.merge_categories("python", "empty"), 1)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.category_id, self.empty_category.pk)
        self.assertFalse(Category.objects.filter(pk=self.category.pk).exists())
        self.assertEqual(q.delete_inactive_users_comments(), 1)
        self.assertFalse(Comment.objects.filter(pk=self.c3.pk).exists())

    def test_merge_failure_preserves_source(self):
        with self.assertRaises(Category.DoesNotExist):
            q.merge_categories("python", "missing")
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.category_id, self.category.pk)
        with self.assertRaises(ValueError):
            q.merge_categories("python", "python")

    def test_command_safe_default_annotations_and_sql(self):
        before = (
            Post.objects.count(),
            Comment.objects.count(),
            Tag.objects.count(),
            Category.objects.count(),
        )
        output = StringIO()
        call_command("queries", stdout=output)
        text = output.getvalue()
        self.assertIn("#50 users_with_draft_as_latest_post", text)
        self.assertIn("'post_count':", text)
        for number in range(40, 45):
            self.assertNotIn(f"#{number} ", text)
        self.assertEqual(
            before,
            (
                Post.objects.count(),
                Comment.objects.count(),
                Tag.objects.count(),
                Category.objects.count(),
            ),
        )
        output = StringIO()
        call_command("queries", number=6, sql=True, stdout=output)
        self.assertIn("SELECT", output.getvalue())
        self.assertIn("1 SQL query", output.getvalue())
        with self.assertRaises(CommandError):
            call_command("queries", number=51, stdout=StringIO())


class EmptyQueryTests(TestCase):
    def test_empty_database_counts_and_defaults(self):
        args = sample_arguments()
        for number, function in q.QUERIES.items():
            if 40 <= number <= 44:
                continue
            with self.subTest(number=number), self.assertNumQueries(1):
                result = function(**args.get(number, {}))
                if isinstance(result, QuerySet):
                    list(result)
        self.assertEqual(q.average_comments_per_post(), 0.0)
        self.assertIsNone(q.posts_stats()["first_post_at"])
        call_command("queries", stdout=StringIO())


class SeedDateTests(TestCase):
    def test_seed_dates_repeat_and_superuser(self):
        admin = User.objects.create(email="admin@example.com", is_superuser=True)
        before = timezone.now()
        call_command("seed", clear=True, users=10, posts=20, comments=40, stdout=StringIO())
        after = timezone.now()
        self.assertTrue(User.objects.filter(pk=admin.pk).exists())
        dates = {}
        for post in Post.objects.all():
            self.assertGreaterEqual(post.created_at, before - timedelta(days=365))
            self.assertLessEqual(post.created_at, post.updated_at)
            self.assertLessEqual(post.updated_at, after)
            delta = post.updated_at - post.created_at
            self.assertTrue(
                delta == timedelta(0) or timedelta(days=1) <= delta <= timedelta(days=30)
            )
            dates[post.pk] = (post.created_at, post.updated_at)
        self.assertEqual(q.edited_posts().count(), 6)
        self.assertEqual(q.comments_before_post().count(), 0)
        self.assertFalse(Comment.objects.filter(created_at__gt=after).exists())
        self.assertFalse(Comment.objects.exclude(post__status=Post.Status.PUBLISHED).exists())
        call_command("seed", users=2, posts=10, comments=10, stdout=StringIO())
        self.assertEqual(Post.objects.count(), 30)
        for post in Post.objects.filter(pk__in=dates):
            self.assertEqual((post.created_at, post.updated_at), dates[post.pk])
        self.assertEqual(q.comments_before_post().count(), 0)
        with self.assertRaises(CommandError):
            call_command("seed", clear=True, users=-1, stdout=StringIO())
        self.assertEqual(Post.objects.count(), 30)
