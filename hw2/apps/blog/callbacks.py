import json
from typing import Any
from urllib.parse import urlencode

from django.db.models import Count, Q
from django.http import HttpRequest
from django.urls import reverse

from apps.auths.models import User
from apps.blog.constants import PERCENT, TOP_AUTHORS
from apps.blog.models import Category, Comment, Post
from settings.conf import BLOG_ENV_ID


def environment_badge(request: HttpRequest) -> tuple[str, str]:
    return ("Production", "danger") if BLOG_ENV_ID == "prod" else ("Local", "warning")


def drafts_badge(request: HttpRequest) -> str:
    return str(Post.objects.filter(status=Post.Status.DRAFT).count())


def sidebar_navigation(request: HttpRequest) -> list[dict[str, Any]]:
    content = []
    for model, title, icon in (
        ("post", "Posts", "article"),
        ("comment", "Comments", "comment"),
        ("category", "Categories", "folder"),
        ("tag", "Tags", "sell"),
    ):
        if request.user.has_perm(f"blog.view_{model}") or request.user.has_perm(
            f"blog.change_{model}"
        ):
            item = {"title": title, "icon": icon, "link": reverse(f"admin:blog_{model}_changelist")}
            if model == "post":
                item["badge"] = "apps.blog.callbacks.drafts_badge"
            content.append(item)
    result = [
        {
            "title": "Overview",
            "items": [
                {"title": "Dashboard", "icon": "dashboard", "link": reverse("admin:index")},
            ],
        }
    ]
    if content:
        result.append({"title": "Content", "items": content})
    if request.user.is_superuser:
        result.append(
            {
                "title": "Users & Access",
                "items": [
                    {
                        "title": "Users",
                        "icon": "group",
                        "link": reverse("admin:auths_user_changelist"),
                    },
                    {
                        "title": "Groups",
                        "icon": "admin_panel_settings",
                        "link": reverse("admin:auth_group_changelist"),
                    },
                ],
            }
        )
    return result


def dashboard_callback(request: HttpRequest, context: dict[str, Any]) -> dict[str, Any]:
    # Do not leak global counts to staff without access to the underlying models.
    required = ("auths.view_user", "blog.view_post", "blog.view_comment", "blog.view_category")
    if not request.user.has_perms(required):
        context["dashboard_restricted"] = True
        return context
    counts = Post.objects.aggregate(
        published=Count("pk", filter=Q(status=Post.Status.PUBLISHED)),
        drafts=Count("pk", filter=Q(status=Post.Status.DRAFT)),
    )
    total = counts["published"] + counts["drafts"]
    context["cards"] = [
        {"title": "Users", "value": User.objects.count(), "icon": "group"},
        {"title": "Published posts", "value": counts["published"], "icon": "check_circle"},
        {"title": "Draft posts", "value": counts["drafts"], "icon": "edit_note"},
        {"title": "Comments", "value": Comment.objects.count(), "icon": "comment"},
    ]
    categories = list(Category.objects.annotate(total=Count("posts")).order_by("name"))
    labels = [item.name for item in categories]
    values = [item.total for item in categories]
    labels.append("Uncategorized")
    values.append(Post.objects.filter(category__isnull=True).count())
    context["category_chart"] = json.dumps(
        {
            "labels": labels,
            "datasets": [
                {
                    "label": "Posts",
                    "data": values,
                    "backgroundColor": "#0d9488",
                    "borderRadius": 6,
                }
            ],
        }
    )
    context["chart_options"] = json.dumps(
        {
            "plugins": {"legend": {"display": False}},
            "scales": {"y": {"beginAtZero": True, "ticks": {"precision": 0}}},
        }
    )
    authors = User.objects.annotate(total=Count("posts")).order_by("-total", "email")[:TOP_AUTHORS]
    context["authors_table"] = {
        "headers": ["Author", "Email", "Posts"],
        "rows": [[author.get_full_name(), author.email, author.total] for author in authors],
    }
    context["publication_progress"] = [
        {
            "title": label,
            "value": round(counts[key] / total * PERCENT, 1) if total else 0,
            "description": f"{counts[key]} of {total} posts",
        }
        for key, label in (("published", "Published"), ("drafts", "Drafts"))
    ]
    return context


def published_link(request: HttpRequest) -> str:
    return (
        reverse("admin:blog_post_changelist")
        + "?"
        + urlencode({"status__exact": Post.Status.PUBLISHED})
    )


def drafts_link(request: HttpRequest) -> str:
    return (
        reverse("admin:blog_post_changelist")
        + "?"
        + urlencode({"status__exact": Post.Status.DRAFT})
    )
