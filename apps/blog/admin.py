from typing import Any
from urllib.parse import urlencode

from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import (
    AutocompleteSelectFilter,
    ChoicesDropdownFilter,
    MultipleRelatedDropdownFilter,
    RangeDateTimeFilter,
    RelatedDropdownFilter,
)
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.decorators import action, display

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Count, Prefetch, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator

from apps.blog.constants import ADMIN_PAGE_SIZE, COMMENT_PREVIEW_LENGTH, INLINE_PAGE_SIZE
from apps.blog.models import Category, Comment, Post, Tag
from apps.blog.sections import CategoryPostsSection, PostCommentsSection


class TaxonomyAdmin(ModelAdmin):
    list_display = ("name", "slug", "post_count")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).annotate(posts_total=Count("posts", distinct=True))

    @display(description="Posts", ordering="posts_total")
    def post_count(self, obj: Category | Tag) -> int:
        return obj.posts_total


@admin.register(Category)
class CategoryAdmin(TaxonomyAdmin):
    list_sections = (CategoryPostsSection,)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super()
            .get_queryset(request)
            .prefetch_related(Prefetch("posts", queryset=Post.objects.select_related("author")))
        )


@admin.register(Tag)
class TagAdmin(TaxonomyAdmin):
    pass


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = ("post", "author", "body_preview", "created_at")
    list_filter = (
        ("post", AutocompleteSelectFilter),
        ("author", AutocompleteSelectFilter),
        ("created_at", RangeDateTimeFilter),
    )
    list_filter_submit = True
    search_fields = ("body", "post__title", "author__email")
    autocomplete_fields = ("post", "author")
    list_select_related = ("post", "author")
    list_per_page = ADMIN_PAGE_SIZE

    @display(description="Comment")
    def body_preview(self, obj: Comment) -> str:
        return Truncator(obj.body).chars(COMMENT_PREVIEW_LENGTH)


class CommentInline(TabularInline):
    model = Comment
    tab = True
    per_page = INLINE_PAGE_SIZE
    extra = 0
    fields = ("author", "body", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("author",)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related("author")


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = (
        "post_header",
        "status_label",
        "category",
        "tag_dropdown",
        "comment_count",
        "created_at",
    )
    list_filter = (
        ("status", ChoicesDropdownFilter),
        ("category", RelatedDropdownFilter),
        ("tags", MultipleRelatedDropdownFilter),
        ("author", AutocompleteSelectFilter),
        ("created_at", RangeDateTimeFilter),
    )
    list_filter_submit = True
    list_filter_sheet = False
    list_per_page = ADMIN_PAGE_SIZE
    search_fields = ("title", "body", "author__email")
    autocomplete_fields = ("author", "category", "tags")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("author", "category")
    list_sections = (PostCommentsSection,)
    inlines = (CommentInline,)
    warn_unsaved_form = True
    formfield_overrides = {models.TextField: {"widget": WysiwygWidget}}
    fieldsets = (
        ("Content", {"classes": ("tab",), "fields": ("title", "slug", "body")}),
        ("Classification", {"classes": ("tab",), "fields": ("category", "tags", "status")}),
        ("Meta", {"classes": ("tab",), "fields": ("author", "created_at", "updated_at")}),
    )
    actions = ("publish_selected", "move_to_drafts")
    actions_row = ("toggle_publication",)
    actions_list = ("publish_all_drafts",)
    actions_detail = ("open_comments",)
    actions_submit_line = ("save_and_publish",)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super()
            .get_queryset(request)
            .select_related("author", "category")
            .annotate(comments_total=Count("comments", distinct=True))
            .prefetch_related(
                "tags", Prefetch("comments", queryset=Comment.objects.select_related("author"))
            )
        )

    @display(description="Post", header=True, ordering="title")
    def post_header(self, obj: Post) -> tuple[str, str]:
        return obj.title, obj.author.get_full_name() or obj.author.email

    @display(
        description="Status", ordering="status", label={"published": "success", "draft": "warning"}
    )
    def status_label(self, obj: Post) -> tuple[str, str]:
        return obj.status, obj.get_status_display()

    @display(description="Tags", dropdown=True)
    def tag_dropdown(self, obj: Post) -> dict[str, Any]:
        tags = list(obj.tags.all())
        return {
            "title": f"{len(tags)} tags",
            "items": [
                {"title": tag.name, "link": reverse("admin:blog_tag_change", args=[tag.pk])}
                for tag in tags
            ],
        }

    @display(description="Comments", ordering="comments_total")
    def comment_count(self, obj: Post) -> int:
        return obj.comments_total

    @action(description="Publish selected", permissions=["change"])
    def publish_selected(self, request: HttpRequest, queryset: QuerySet) -> None:
        count = queryset.update(status=Post.Status.PUBLISHED, updated_at=timezone.now())
        self.message_user(request, f"Published {count} posts.", messages.SUCCESS)

    @action(description="Move to drafts", permissions=["change"])
    def move_to_drafts(self, request: HttpRequest, queryset: QuerySet) -> None:
        count = queryset.update(status=Post.Status.DRAFT, updated_at=timezone.now())
        self.message_user(request, f"Moved {count} posts to drafts.", messages.SUCCESS)

    def confirm_action(self, request: HttpRequest, title: str) -> TemplateResponse:
        return TemplateResponse(
            request,
            "admin/blog/confirm_action.html",
            {
                **self.admin_site.each_context(request),
                "title": title,
                "opts": self.model._meta,
                "back_url": reverse("admin:blog_post_changelist"),
            },
        )

    @action(description="Publish / unpublish", permissions=["change"], icon="swap_horiz")
    def toggle_publication(self, request: HttpRequest, object_id: str) -> HttpResponse:
        obj = get_object_or_404(self.get_queryset(request), pk=object_id)
        if not self.has_change_permission(request, obj):
            raise PermissionDenied
        target = Post.Status.DRAFT if obj.status == Post.Status.PUBLISHED else Post.Status.PUBLISHED
        if request.method != "POST":
            return self.confirm_action(request, f"Set ‘{obj.title}’ to {target}?")
        Post.objects.filter(pk=obj.pk).update(status=target, updated_at=timezone.now())
        self.message_user(request, f"Post is now {target}.", messages.SUCCESS)
        return redirect("admin:blog_post_changelist")

    @action(description="Publish all drafts", permissions=["change"], icon="publish")
    def publish_all_drafts(self, request: HttpRequest) -> HttpResponse:
        if request.method != "POST":
            return self.confirm_action(request, "Publish all draft posts?")
        self.publish_selected(request, self.get_queryset(request).filter(status=Post.Status.DRAFT))
        return redirect("admin:blog_post_changelist")

    @action(description="Open comments", permissions=["view"], icon="comment")
    def open_comments(self, request: HttpRequest, object_id: str) -> HttpResponse:
        get_object_or_404(self.get_queryset(request), pk=object_id)
        query = urlencode({"post__id__exact": object_id})
        return redirect(f"{reverse('admin:blog_comment_changelist')}?{query}")

    @action(description="Save & publish", permissions=["change"], icon="publish")
    def save_and_publish(self, request: HttpRequest, obj: Post) -> None:
        obj.status = Post.Status.PUBLISHED
        obj.save(update_fields=["status", "updated_at"])
        self.message_user(request, "Post saved and published.", messages.SUCCESS)
