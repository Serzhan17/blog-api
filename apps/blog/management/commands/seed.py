import random
from time import perf_counter
from typing import Any

from faker import Faker

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction
from django.utils.text import slugify

from apps.auths.models import User
from apps.blog.constants import (
    BODY_PARAGRAPHS,
    BULK_BATCH_SIZE,
    CATEGORIES,
    DEFAULT_COMMENTS,
    DEFAULT_POSTS,
    DEFAULT_USERS,
    FIRST_SUFFIX,
    INACTIVE_SHARE,
    MAX_COMMENT_SENTENCES,
    MAX_TAGS,
    MIN_COMMENT_SENTENCES,
    NO_CATEGORY_SHARE,
    PUBLISHED_SHARE,
    SEED_PASSWORD,
    STAFF_SHARE,
    TAGS,
)
from apps.blog.models import Category, Comment, Post, Tag


def unique_value(base: str, used: set[str], max_length: int) -> str:
    base = base[:max_length]
    candidate = base
    suffix = FIRST_SUFFIX
    while candidate in used:
        tail = f"-{suffix}"
        candidate = f"{base[: max_length - len(tail)]}{tail}"
        suffix += 1
    used.add(candidate)
    return candidate


class Command(BaseCommand):
    help = "Fill the database with fake data."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--users", type=int, default=DEFAULT_USERS, help="Users to create")
        parser.add_argument("--posts", type=int, default=DEFAULT_POSTS, help="Posts to create")
        parser.add_argument(
            "--comments", type=int, default=DEFAULT_COMMENTS, help="Comments to create"
        )
        parser.add_argument("--clear", action="store_true", help="Delete data, except superusers")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        started = perf_counter()
        for key in ("users", "posts", "comments"):
            if options[key] < 0:
                raise CommandError(f"--{key} cannot be negative.")
        if options["clear"]:
            Comment.objects.all().delete()
            Post.objects.all().delete()
            Tag.objects.all().delete()
            Category.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        users_created = self.create_users(options["users"])
        users = list(User.objects.all())
        if (options["posts"] or options["comments"]) and not users:
            raise CommandError("Posts/comments require users. Pass --users greater than zero.")
        category_count = self.create_taxonomy(Category, CATEGORIES)
        tag_count = self.create_taxonomy(Tag, TAGS)
        self.create_posts(options["posts"], users)
        published = list(Post.objects.filter(status=Post.Status.PUBLISHED))
        if options["comments"] and not published:
            raise CommandError("Comments require published posts. Create or publish a post first.")
        fake = Faker()
        comments = [
            Comment(
                post=random.choice(published),
                author=random.choice(users),
                body=" ".join(
                    fake.sentences(nb=random.randint(MIN_COMMENT_SENTENCES, MAX_COMMENT_SENTENCES))
                ),
            )
            for _ in range(options["comments"])
        ]
        Comment.objects.bulk_create(comments, batch_size=BULK_BATCH_SIZE)
        for label, count in (
            ("Users", users_created),
            ("Categories", category_count),
            ("Tags", tag_count),
            ("Posts", options["posts"]),
            ("Comments", len(comments)),
        ):
            self.stdout.write(f"{label + ':':<12}{count:>5} created")
        self.stdout.write(self.style.SUCCESS(f"Done in {perf_counter() - started:.2f} seconds"))

    def create_users(self, count: int) -> int:
        fake = Faker()
        used = set(User.objects.values_list("email", flat=True))
        password_hash = make_password(SEED_PASSWORD) if count else ""
        users = []
        email_limit = User._meta.get_field("email").max_length
        domain = "@example.com"
        # Reserve existing local parts so repeated runs cannot collide.
        used_local = {email[: -len(domain)] for email in used if email.endswith(domain)}
        inactive = set(random.sample(range(count), round(count * INACTIVE_SHARE)))
        staff = set(random.sample(range(count), round(count * STAFF_SHARE)))
        for index in range(count):
            first, last = fake.first_name(), fake.last_name()
            base = slugify(f"{first}.{last}") or "user"
            local = unique_value(base, used_local, email_limit - len(domain))
            users.append(
                User(
                    email=f"{local}{domain}",
                    first_name=first,
                    last_name=last,
                    password=password_hash,
                    is_active=index not in inactive,
                    is_staff=index in staff,
                )
            )
        User.objects.bulk_create(users, batch_size=BULK_BATCH_SIZE)
        return len(users)

    def create_taxonomy(self, model: type[Category] | type[Tag], names: tuple[str, ...]) -> int:
        used_names = set(model.objects.values_list("name", flat=True))
        used_slugs = set(model.objects.values_list("slug", flat=True))
        objects = [
            model(name=name, slug=slugify(name))
            for name in names
            if name not in used_names and slugify(name) not in used_slugs
        ]
        model.objects.bulk_create(objects, batch_size=BULK_BATCH_SIZE)
        return len(objects)

    def create_posts(self, count: int, users: list[User]) -> None:
        fake = Faker()
        used = set(Post.objects.values_list("slug", flat=True))
        slug_limit = Post._meta.get_field("slug").max_length
        categories, tags = list(Category.objects.all()), list(Tag.objects.all())
        published = set(random.sample(range(count), round(count * PUBLISHED_SHARE)))
        uncategorized = set(random.sample(range(count), round(count * NO_CATEGORY_SHARE)))
        posts = []
        for index in range(count):
            title = fake.sentence()
            posts.append(
                Post(
                    author=random.choice(users),
                    title=title,
                    slug=unique_value(slugify(title) or "post", used, slug_limit),
                    body="\n\n".join(fake.paragraphs(nb=BODY_PARAGRAPHS)),
                    category=None if index in uncategorized else random.choice(categories),
                    status=Post.Status.PUBLISHED if index in published else Post.Status.DRAFT,
                )
            )
        Post.objects.bulk_create(posts, batch_size=BULK_BATCH_SIZE)
        for post in posts:
            post.tags.set(random.sample(tags, random.randint(0, min(MAX_TAGS, len(tags)))))
