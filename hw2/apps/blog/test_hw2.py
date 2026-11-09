from io import StringIO
from unittest.mock import patch

from faker import Faker

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.auths.models import User
from apps.blog.callbacks import sidebar_navigation
from apps.blog.constants import SEED_PASSWORD
from apps.blog.models import Category, Comment, Post, Tag


class SeedTests(TestCase):
    def seed(self, **options: object) -> None:
        call_command("seed", stdout=StringIO(), **options)

    def test_repeat_unique_hashes_and_relations(self) -> None:
        for _ in range(2):
            self.seed(users=10, posts=20, comments=30)
        self.assertEqual(User.objects.count(), 20)
        self.assertEqual(Post.objects.count(), 40)
        self.assertEqual(Comment.objects.count(), 60)
        self.assertEqual(Category.objects.count(), 8)
        self.assertEqual(Tag.objects.count(), 20)
        self.assertTrue(User.objects.first().check_password(SEED_PASSWORD))
        self.assertFalse(Comment.objects.exclude(post__status=Post.Status.PUBLISHED).exists())
        self.assertEqual(Post.objects.filter(status=Post.Status.PUBLISHED).count(), 28)
        self.assertEqual(Post.objects.filter(category=None).count(), 4)
        for post in Post.objects.prefetch_related("tags"):
            self.assertLessEqual(len(post.tags.all()), 5)

    def test_clear_preserves_superuser(self) -> None:
        boss = User.objects.create_superuser(
            "boss@example.com", "Password-123!", first_name="A", last_name="B"
        )
        self.seed(users=3, posts=4, comments=5)
        self.seed(users=2, posts=3, comments=4, clear=True)
        self.assertTrue(User.objects.filter(pk=boss.pk, is_superuser=True).exists())
        self.assertEqual(User.objects.count(), 3)
        self.assertEqual(Post.objects.count(), 3)
        self.assertEqual(Comment.objects.count(), 4)

    def test_invalid_counts_and_missing_relations(self) -> None:
        for key in ("users", "posts", "comments"):
            values = {"users": 0, "posts": 0, "comments": 0, key: -1}
            with self.assertRaises(CommandError):
                self.seed(**values)
        with self.assertRaisesMessage(CommandError, "require users"):
            self.seed(users=0, posts=1, comments=0)
        with self.assertRaisesMessage(CommandError, "require published posts"):
            self.seed(users=1, posts=0, comments=1)
        self.assertEqual(User.objects.count(), 0)  # atomic rollback
        self.seed(users=0, posts=0, comments=0)

    def test_colliding_titles_get_suffix(self) -> None:
        fake = Faker()
        fake.sentence = lambda: "Same title"
        with patch("apps.blog.management.commands.seed.Faker", return_value=fake):
            self.seed(users=1, posts=3, comments=0)
        self.assertSetEqual(
            set(Post.objects.values_list("slug", flat=True)),
            {"same-title", "same-title-2", "same-title-3"},
        )


class AdminHW2Tests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.boss = User.objects.create_superuser(
            "boss@example.com", "Password-123!", first_name="Editor", last_name="Admin"
        )
        call_command("seed", users=10, posts=100, comments=30, stdout=StringIO())

    def setUp(self) -> None:
        self.client.force_login(self.boss)

    def action_url(self, name: str, pk: int | None = None) -> str:
        action = admin.site._registry[Post].get_unfold_action(name)
        return reverse(f"admin:{action.action_name}", args=[pk] if pk else None)

    def test_all_admin_pages_and_filters(self) -> None:
        post = Post.objects.first()
        urls = [reverse("admin:index")]
        for app, model in [
            ("blog", "post"),
            ("blog", "comment"),
            ("blog", "category"),
            ("blog", "tag"),
            ("auths", "user"),
            ("auth", "group"),
        ]:
            urls += [
                reverse(f"admin:{app}_{model}_changelist"),
                reverse(f"admin:{app}_{model}_add"),
            ]
        urls += [
            reverse("admin:blog_post_change", args=[post.pk]),
            reverse("admin:auths_user_change", args=[self.boss.pk]),
            reverse("admin:blog_post_changelist") + "?status__exact=published",
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
        dashboard = self.client.get(reverse("admin:index"))
        self.assertContains(dashboard, "Posts by category")
        self.assertContains(dashboard, "Top 5 authors")

    def test_empty_dashboard(self) -> None:
        Post.objects.all().delete()
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_actions_require_post_and_change_permission(self) -> None:
        post = Post.objects.filter(status=Post.Status.DRAFT).first()
        url = self.action_url("toggle_publication", post.pk)
        self.assertEqual(self.client.get(url).status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.DRAFT)
        self.assertEqual(self.client.post(url).status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.PUBLISHED)
        self.client.post(self.action_url("publish_all_drafts"))
        self.assertFalse(Post.objects.filter(status=Post.Status.DRAFT).exists())
        staff = User.objects.create_user(
            "viewer@example.com",
            "Password-123!",
            first_name="View",
            last_name="Only",
            is_staff=True,
        )
        staff.user_permissions.add(
            Permission.objects.get(codename="view_post", content_type__app_label="blog")
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.post(url).status_code, 403)
        request = self.client.get(reverse("admin:index")).wsgi_request
        self.assertNotIn("Users & Access", str(sidebar_navigation(request)))

    def test_csrf_required_for_publish(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.boss)
        response = client.post(self.action_url("publish_all_drafts"))
        self.assertEqual(response.status_code, 403)

    def test_save_and_publish_and_inline_pagination(self) -> None:
        post = Post.objects.first()
        Comment.objects.filter(post=post).delete()
        Comment.objects.bulk_create(
            [Comment(post=post, author=self.boss, body=f"Comment {i}") for i in range(15)]
        )
        url = reverse("admin:blog_post_change", args=[post.pk])
        response = self.client.get(url)
        formset = response.context["inline_admin_formsets"][0].formset
        self.assertEqual(len(formset.forms), 10)
        self.assertEqual(formset.paginator.count, 15)
        # Submit a different post without inline rows, to exercise actual form save.
        clean = Post.objects.create(author=self.boss, title="Before", slug="before", body="Body")
        action_name = admin.site._registry[Post].get_unfold_action("save_and_publish").action_name
        response = self.client.post(
            reverse("admin:blog_post_change", args=[clean.pk]),
            {
                "title": "After",
                "slug": "before",
                "body": "<p>Updated</p>",
                "author": self.boss.pk,
                "status": "draft",
                "category": "",
                "comments-TOTAL_FORMS": "0",
                "comments-INITIAL_FORMS": "0",
                "comments-MIN_NUM_FORMS": "0",
                "comments-MAX_NUM_FORMS": "1000",
                action_name: "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        clean.refresh_from_db()
        self.assertEqual(clean.title, "After")
        self.assertEqual(clean.status, Post.Status.PUBLISHED)

    def test_query_count_does_not_scale_with_rows(self) -> None:
        for model, url_name in [
            (Post, "admin:blog_post_changelist"),
            (Comment, "admin:blog_comment_changelist"),
        ]:
            model_admin = admin.site._registry[model]
            old = model_admin.list_per_page
            counts = []
            try:
                for size in (10, 100):
                    model_admin.list_per_page = size
                    with CaptureQueriesContext(connection) as captured:
                        response = self.client.get(reverse(url_name))
                        self.assertEqual(response.status_code, 200)
                    counts.append(len(captured))
            finally:
                model_admin.list_per_page = old
            self.assertEqual(counts[0], counts[1], (url_name, counts))
