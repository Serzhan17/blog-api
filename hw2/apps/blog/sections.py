from unfold.sections import TableSection

from apps.blog.constants import COMMENT_PREVIEW_LENGTH
from apps.blog.models import Comment


class CategoryPostsSection(TableSection):
    verbose_name = "Posts in this category"
    related_name = "posts"
    fields = ("title", "author", "status")


class PostCommentsSection(TableSection):
    verbose_name = "Comments"
    related_name = "comments"
    fields = ("author", "preview", "created_at")

    def preview(self, instance: Comment) -> str:
        return instance.body[:COMMENT_PREVIEW_LENGTH]
