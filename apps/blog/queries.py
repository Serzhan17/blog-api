"""Homework 3: 50 ORM exercises; query numbers match the assignment."""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.db.models import (
    Avg,
    Case,
    CharField,
    Count,
    Exists,
    F,
    Max,
    Min,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Concat, TruncMonth
from django.utils import timezone
from django.utils.text import slugify

from apps.auths.models import User
from apps.blog.constants import (
    AVERAGE_DECIMAL_PLACES,
    EDITED_AFTER_HOURS,
    FEED_LIMIT,
    FEED_SEPARATOR,
    FIRST_PAGE,
    FULL_NAME_SEPARATOR,
    HOT_COMMENT_COUNT,
    NEWEST_POST_LIMIT,
    NORMAL_COMMENT_COUNT,
    POPULARITY_HOT,
    POPULARITY_NORMAL,
    POPULARITY_QUIET,
    POST_PAGE_SIZE,
    SINGLE_ROW,
    TAG_FEED_LIMIT,
    TAG_LINE_SEPARATOR,
    TAG_SEPARATOR,
    TOP_AUTHORS,
    UNCATEGORIZED,
)
from apps.blog.models import Category, Comment, Post, Tag


def categories_by_name() -> QuerySet[Category]:
    """1. All categories in alphabetical order."""
    return Category.objects.order_by("name")


def published_posts() -> QuerySet[Post]:
    """2. Published posts, newest first with a stable tie-breaker."""
    return Post.objects.filter(status=Post.Status.PUBLISHED).order_by("-created_at", "-pk")


def newest_published_posts() -> QuerySet[Post]:
    """3. Limit the published queryset in SQL."""
    return published_posts()[:NEWEST_POST_LIMIT]


def post_by_slug(slug: str) -> Post | None:
    """4. Get one post or None without DoesNotExist."""
    return Post.objects.filter(slug=slug).first()


def active_users_count() -> int:
    """5. Count active non-staff users in the database."""
    return User.objects.filter(is_active=True, is_staff=False).count()


def has_drafts() -> bool:
    """6. Ask whether any draft exists without fetching model rows."""
    return Post.objects.filter(status=Post.Status.DRAFT).exists()


def published_posts_page(page: int) -> QuerySet[Post]:
    """7. One-based pagination using SQL LIMIT and OFFSET."""
    if page < FIRST_PAGE:
        raise ValueError("page must be at least 1")
    start = (page - FIRST_PAGE) * POST_PAGE_SIZE
    return published_posts()[start : start + POST_PAGE_SIZE]


def posts_with_word_in_title(word: str) -> QuerySet[Post]:
    """8. Match a title fragment regardless of case."""
    return Post.objects.filter(title__icontains=word)


def users_with_email_domain(domain: str) -> QuerySet[User]:
    """9. Match the complete email domain, case-insensitively."""
    return User.objects.filter(email__iendswith=f"@{domain}")


def posts_without_category() -> QuerySet[Post]:
    """10. Posts with a NULL category foreign key."""
    return Post.objects.filter(category__isnull=True)


def categories_by_slugs(slugs: list[str]) -> QuerySet[Category]:
    """11. Match the supplied slug set; even an empty input executes one SQL."""
    # An empty __in is optimized to zero SQL by Django; this SQL predicate is
    # always false instead, preserving the assignment's exact-one-query rule.
    if not slugs:
        return Category.objects.filter(pk__isnull=True)
    return Category.objects.filter(slug__in=slugs)


def posts_in_month(year: int, month: int) -> QuerySet[Post]:
    """12. Match a calendar year and month in the active timezone."""
    return Post.objects.filter(created_at__year=year, created_at__month=month)


def posts_last_days(days: int) -> QuerySet[Post]:
    """13. Posts between the relative cutoff and now."""
    now = timezone.now()
    return Post.objects.filter(created_at__gte=now - timedelta(days=days), created_at__lte=now)


def posts_between(start: date, end: date) -> QuerySet[Post]:
    """14. Inclusive date range, including the whole last day."""
    return Post.objects.filter(created_at__date__range=(start, end))


def author_published_posts(email: str) -> QuerySet[Post]:
    """15. Published posts by an email matched without case sensitivity."""
    return published_posts().filter(author__email__iexact=email)


def posts_with_tag(tag_slug: str) -> QuerySet[Post]:
    """16. Posts connected to the uniquely identified tag."""
    return Post.objects.filter(tags__slug=tag_slug)


def comments_in_category(category_slug: str) -> QuerySet[Comment]:
    """17. Follow comment -> post -> category in SQL."""
    return Comment.objects.filter(post__category__slug=category_slug)


def users_with_published_posts() -> QuerySet[User]:
    """18. Unique authors of at least one published post."""
    return User.objects.filter(posts__status=Post.Status.PUBLISHED).distinct()


def posts_without_tags() -> QuerySet[Post]:
    """19. Posts without any many-to-many tag relation."""
    return Post.objects.filter(tags__isnull=True)


def users_without_comments() -> QuerySet[User]:
    """20. Users who have never authored a comment."""
    return User.objects.filter(comments__isnull=True)


def posts_with_both_tags(first_slug: str, second_slug: str) -> QuerySet[Post]:
    """21. Two JOIN conditions require both tags, rather than either tag."""
    return Post.objects.filter(tags__slug=first_slug).filter(tags__slug=second_slug).distinct()


def search_posts(text: str) -> QuerySet[Post]:
    """22. Search a title OR body using Q expressions."""
    return Post.objects.filter(Q(title__icontains=text) | Q(body__icontains=text))


def published_posts_missing_info() -> QuerySet[Post]:
    """23. Published posts lacking a category or tags, without duplicate rows."""
    return published_posts().filter(Q(category__isnull=True) | Q(tags__isnull=True)).distinct()


def edited_posts() -> QuerySet[Post]:
    """24. Compare timestamps on the same row with an F expression."""
    return Post.objects.filter(updated_at__gt=F("created_at") + timedelta(hours=EDITED_AFTER_HOURS))


def comments_by_post_author() -> QuerySet[Comment]:
    """25. Comments whose author also authored the parent post."""
    return Comment.objects.filter(author_id=F("post__author_id"))


def comments_before_post() -> QuerySet[Comment]:
    """26. Invalid chronology; a correctly seeded database returns no rows."""
    return Comment.objects.filter(created_at__lt=F("post__created_at"))


def published_authors_emails() -> list[str]:
    """27. Return unique, alphabetically sorted published-author emails."""
    return list(
        published_posts()
        .order_by("author__email")
        .values_list("author__email", flat=True)
        .distinct()
    )


def published_posts_overview() -> list[dict[str, Any]]:
    """28. Project three named columns with an SQL fallback for NULL categories."""
    return list(
        published_posts().values(
            "title",
            author_email=F("author__email"),
            category_name=Coalesce("category__name", Value(UNCATEGORIZED)),
        )
    )


def posts_stats() -> dict[str, Any]:
    """29. Compute all five statistics in one aggregate query."""
    return Post.objects.aggregate(
        total=Count("pk"),
        published=Count("pk", filter=Q(status=Post.Status.PUBLISHED)),
        drafts=Count("pk", filter=Q(status=Post.Status.DRAFT)),
        first_post_at=Min("created_at"),
        last_post_at=Max("created_at"),
    )


def average_comments_per_post() -> float:
    """30. Average per-post counts, retaining published posts with zero comments."""
    result = (
        published_posts()
        .annotate(comment_count=Count("comments"))
        .aggregate(average=Avg("comment_count", default=0.0))
    )
    return round(float(result["average"]), AVERAGE_DECIMAL_PLACES)


def categories_with_post_count() -> QuerySet[Category]:
    """31. Annotate each category, ranking by post count then name."""
    return Category.objects.annotate(post_count=Count("posts")).order_by("-post_count", "name")


def categories_with_published_count() -> QuerySet[Category]:
    """32. Filter inside Count so categories with zero matches survive."""
    return Category.objects.annotate(
        published_count=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED))
    ).order_by("name")


def top_authors() -> QuerySet[User]:
    """33. Rank five users by published count, with email breaking ties."""
    return User.objects.annotate(
        published_count=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED))
    ).order_by("-published_count", "email")[:TOP_AUTHORS]


def popular_tags(min_posts: int) -> QuerySet[Tag]:
    """34. Filter grouped tags by their post count (SQL HAVING)."""
    return (
        Tag.objects.annotate(post_count=Count("posts"))
        .filter(post_count__gte=min_posts)
        .order_by("-post_count", "name")
    )


def posts_per_status() -> list[dict[str, Any]]:
    """35. Group posts by status instead of by individual post."""
    return list(Post.objects.values("status").annotate(count=Count("pk")).order_by("status"))


def users_activity() -> QuerySet[User]:
    """36. Distinct counts prevent multiplication across two reverse JOINs."""
    return User.objects.annotate(
        post_count=Count("posts", distinct=True), comment_count=Count("comments", distinct=True)
    ).order_by("email")


def search_users_by_full_name(text: str) -> QuerySet[User]:
    """37. Construct and search First Last in the database."""
    return User.objects.annotate(
        full_name=Concat("first_name", Value(FULL_NAME_SEPARATOR), "last_name")
    ).filter(full_name__icontains=text)


def published_posts_per_month() -> list[dict[str, Any]]:
    """38. Group published posts by calendar month, oldest first."""
    return list(
        published_posts()
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("pk"))
        .order_by("month")
    )


def posts_with_popularity() -> QuerySet[Post]:
    """39. Assign hot/normal/quiet in SQL, testing the highest threshold first."""
    return Post.objects.annotate(comment_count=Count("comments")).annotate(
        popularity=Case(
            When(comment_count__gte=HOT_COMMENT_COUNT, then=Value(POPULARITY_HOT)),
            When(comment_count__gte=NORMAL_COMMENT_COUNT, then=Value(POPULARITY_NORMAL)),
            default=Value(POPULARITY_QUIET),
            output_field=CharField(),
        )
    )


def get_or_create_tag(name: str) -> tuple[Tag, bool]:
    """40. Use the unique slug as identity, including case-equivalent names."""
    slug = slugify(name)
    if not slug:
        raise ValueError("name must produce a non-empty slug")
    return Tag.objects.get_or_create(slug=slug, defaults={"name": name})


def publish_old_drafts(days: int) -> int:
    """41. Publish old drafts and explicitly touch updated_at in one UPDATE."""
    now = timezone.now()
    return Post.objects.filter(
        status=Post.Status.DRAFT, created_at__lt=now - timedelta(days=days)
    ).update(status=Post.Status.PUBLISHED, updated_at=now)


@transaction.atomic
def tag_category_posts(category_slug: str, tag_slug: str) -> int:
    """42. Bulk-add a tag through its reverse manager; existing links are retained."""
    tag = Tag.objects.get(slug=tag_slug)
    post_ids = Post.objects.filter(category__slug=category_slug).values_list("pk", flat=True)
    count = post_ids.count()
    tag.posts.add(*post_ids)
    return count


@transaction.atomic
def merge_categories(source_slug: str, target_slug: str) -> int:
    """43. Move posts before deleting the source, atomically."""
    if source_slug == target_slug:
        raise ValueError("Source and target categories must be different")
    source = Category.objects.get(slug=source_slug)
    target = Category.objects.get(slug=target_slug)
    moved = Post.objects.filter(category=source).update(category=target)
    source.delete()
    return moved


def delete_inactive_users_comments() -> int:
    """44. Delete comments by inactive authors and return the deleted row count."""
    deleted, _ = Comment.objects.filter(author__is_active=False).delete()
    return deleted


def published_feed() -> list[str]:
    """45. Format a feed after loading both foreign keys in the same SELECT."""
    posts = published_posts().select_related("author", "category")[:FEED_LIMIT]
    return [
        FEED_SEPARATOR.join(
            (
                post.title,
                post.author.email,
                post.category.name if post.category else UNCATEGORIZED,
            )
        )
        for post in posts
    ]


def newest_posts_with_tags() -> list[str]:
    """46. One SELECT for posts and one for all their tags, with no N+1."""
    posts = Post.objects.order_by("-created_at", "-pk").prefetch_related("tags")[:TAG_FEED_LIMIT]
    return [
        f"{post.title}{TAG_LINE_SEPARATOR}{TAG_SEPARATOR.join(tag.name for tag in post.tags.all())}"
        for post in posts
    ]


def categories_with_published_posts() -> dict[str, list[str]]:
    """47. Prefetch only published posts, retaining empty categories."""
    categories = Category.objects.order_by("name").prefetch_related(
        Prefetch("posts", queryset=published_posts(), to_attr="published_items")
    )
    return {
        category.name: [post.title for post in category.published_items] for category in categories
    }


def posts_with_last_comment() -> QuerySet[Post]:
    """48. Correlate each post with the body of its newest comment."""
    latest = Comment.objects.filter(post_id=OuterRef("pk")).order_by("-created_at", "-pk")
    return published_posts().annotate(last_comment=Subquery(latest.values("body")[:SINGLE_ROW]))


def posts_with_staff_comments() -> QuerySet[Post]:
    """49. Filter using EXISTS, without duplicate-producing result JOINs."""
    staff_comments = Comment.objects.filter(post_id=OuterRef("pk"), author__is_staff=True)
    return Post.objects.filter(Exists(staff_comments))


def users_with_draft_as_latest_post() -> QuerySet[User]:
    """50. Annotate the latest post's status, then keep users whose latest is draft."""
    latest = Post.objects.filter(author_id=OuterRef("pk")).order_by("-created_at", "-pk")
    return User.objects.annotate(
        latest_post_status=Subquery(latest.values("status")[:SINGLE_ROW])
    ).filter(latest_post_status=Post.Status.DRAFT)


QUERIES: dict[int, Callable[..., Any]] = {
    1: categories_by_name,
    2: published_posts,
    3: newest_published_posts,
    4: post_by_slug,
    5: active_users_count,
    6: has_drafts,
    7: published_posts_page,
    8: posts_with_word_in_title,
    9: users_with_email_domain,
    10: posts_without_category,
    11: categories_by_slugs,
    12: posts_in_month,
    13: posts_last_days,
    14: posts_between,
    15: author_published_posts,
    16: posts_with_tag,
    17: comments_in_category,
    18: users_with_published_posts,
    19: posts_without_tags,
    20: users_without_comments,
    21: posts_with_both_tags,
    22: search_posts,
    23: published_posts_missing_info,
    24: edited_posts,
    25: comments_by_post_author,
    26: comments_before_post,
    27: published_authors_emails,
    28: published_posts_overview,
    29: posts_stats,
    30: average_comments_per_post,
    31: categories_with_post_count,
    32: categories_with_published_count,
    33: top_authors,
    34: popular_tags,
    35: posts_per_status,
    36: users_activity,
    37: search_users_by_full_name,
    38: published_posts_per_month,
    39: posts_with_popularity,
    40: get_or_create_tag,
    41: publish_old_drafts,
    42: tag_category_posts,
    43: merge_categories,
    44: delete_inactive_users_comments,
    45: published_feed,
    46: newest_posts_with_tags,
    47: categories_with_published_posts,
    48: posts_with_last_comment,
    49: posts_with_staff_comments,
    50: users_with_draft_as_latest_post,
}
