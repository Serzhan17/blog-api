"""Run numbered ORM exercises and capture actual database work."""

from datetime import timedelta
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection
from django.db.models import Count, Model, QuerySet
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.auths.models import User
from apps.blog.constants import MUTATING_QUERY_NUMBERS, QUERY_PREVIEW_ROWS, SEED_HISTORY_DAYS
from apps.blog.models import Category, Post, Tag
from apps.blog.queries import QUERIES

# All sample arguments live here. Values marked None are filled from existing data
# before SQL measurement; input discovery is not part of an exercise's query count.
SAMPLE_ARGUMENTS: dict[int, dict[str, Any]] = {
    4: {"slug": None},
    7: {"page": 1},
    8: {"word": None},
    9: {"domain": None},
    11: {"slugs": None},
    12: {"year": None, "month": None},
    13: {"days": 30},
    14: {"start": None, "end": None},
    15: {"email": None},
    16: {"tag_slug": None},
    17: {"category_slug": None},
    21: {"first_slug": None, "second_slug": None},
    22: {"text": None},
    34: {"min_posts": 1},
    37: {"text": None},
    40: {"name": "Django ORM"},
    41: {"days": 30},
    42: {"category_slug": None, "tag_slug": None},
    43: {"source_slug": None, "target_slug": None},
}


def sample_arguments() -> dict[int, dict[str, Any]]:
    """Choose useful examples from the database, tolerating an empty database."""
    arguments = {number: values.copy() for number, values in SAMPLE_ARGUMENTS.items()}
    post = Post.objects.filter(status=Post.Status.PUBLISHED).select_related("author").first()
    post = post or Post.objects.select_related("author").first()
    user = post.author if post else User.objects.first()
    categories = list(Category.objects.annotate(n=Count("posts")).order_by("-n", "name")[:2])
    tags = list(Tag.objects.annotate(n=Count("posts")).order_by("-n", "name")[:2])
    pair_post = Post.objects.annotate(n=Count("tags")).filter(n__gte=2).first()
    pair = list(pair_post.tags.order_by("name")[:2]) if pair_post else tags
    today = timezone.localdate()
    post_date = timezone.localdate(post.created_at) if post else today
    category = categories[0].slug if categories else "python"
    tag = tags[0].slug if tags else "python"
    arguments[4]["slug"] = post.slug if post else "missing-post"
    arguments[8]["word"] = post.title.split()[0] if post and post.title.split() else "Python"
    arguments[9]["domain"] = user.email.rsplit("@", 1)[-1] if user else "example.com"
    arguments[11]["slugs"] = [item.slug for item in categories]
    arguments[12].update(year=post_date.year, month=post_date.month)
    arguments[14].update(start=today - timedelta(days=SEED_HISTORY_DAYS), end=today)
    arguments[15]["email"] = user.email if user else "missing@example.com"
    arguments[16]["tag_slug"] = tag
    arguments[17]["category_slug"] = category
    arguments[21].update(
        first_slug=pair[0].slug if pair else "python",
        second_slug=pair[1].slug if len(pair) > 1 else "django",
    )
    arguments[22]["text"] = arguments[8]["word"]
    arguments[37]["text"] = user.first_name if user else "John"
    arguments[42].update(category_slug=category, tag_slug=tag)
    arguments[43].update(
        source_slug=category,
        target_slug=categories[1].slug if len(categories) > 1 else "django",
    )
    return arguments


def format_result(result: Any) -> list[str]:
    """Evaluate lazy results and show annotations without additional relation reads."""
    annotations = tuple(result.query.annotations) if isinstance(result, QuerySet) else ()
    if isinstance(result, QuerySet):
        result = list(result)
    if isinstance(result, list):
        lines = []
        for row in result[:QUERY_PREVIEW_ROWS]:
            extra = (
                {name: getattr(row, name) for name in annotations} if isinstance(row, Model) else {}
            )
            lines.append(f"  {row}" + (f" {extra}" if extra else ""))
        lines.append(f"  ({len(result)} rows)")
        return lines
    return [f"  {result}"]


class Command(BaseCommand):
    help = "Run ORM exercises; mutations 40-44 require an explicit --number."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--number", type=int, help="One exercise number (1-50)")
        parser.add_argument("--sql", action="store_true", help="Display executed SQL")

    def handle(self, *args: Any, **options: Any) -> None:
        number = options["number"]
        if number is not None and number not in QUERIES:
            raise CommandError("Unknown query number. Choose a number from 1 to 50.")
        numbers = (
            [number]
            if number is not None
            else [item for item in QUERIES if item not in MUTATING_QUERY_NUMBERS]
        )
        samples = sample_arguments()
        for item in numbers:
            function = QUERIES[item]
            arguments = samples.get(item, {})
            try:
                with CaptureQueriesContext(connection) as context:
                    result = function(**arguments)
                    lines = format_result(result)
            except (ObjectDoesNotExist, ValueError) as error:
                raise CommandError(f"#{item}: {error}. Check the sample data/arguments.") from error
            count = len(context.captured_queries)
            self.stdout.write(
                f"#{item} {function.__name__} — {count} SQL quer{'y' if count == 1 else 'ies'}"
            )
            if arguments:
                self.stdout.write(f"  arguments: {arguments}")
            if options["sql"]:
                for query in context.captured_queries:
                    self.stdout.write(query["sql"])
            for line in lines:
                self.stdout.write(line)
