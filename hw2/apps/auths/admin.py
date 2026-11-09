from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import BooleanRadioFilter
from unfold.decorators import action, display
from unfold.forms import AdminPasswordChangeForm

from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from apps.auths.forms import CustomUserChangeForm, CustomUserCreationForm
from apps.auths.models import User
from apps.blog.constants import ADMIN_PAGE_SIZE


@admin.register(User)
class CustomUserAdmin(UserAdmin, ModelAdmin):
    model = User
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    change_password_form = AdminPasswordChangeForm
    ordering = ("email",)
    list_display = ("user_header", "active_label", "staff_label", "post_count")
    search_fields = ("email", "first_name", "last_name")
    list_filter = (("is_active", BooleanRadioFilter), ("is_staff", BooleanRadioFilter))
    list_filter_submit = True
    list_per_page = ADMIN_PAGE_SIZE
    actions = ("activate_users", "deactivate_users")
    fieldsets = (
        (
            "Personal info",
            {"classes": ("tab",), "fields": ("email", "password", "first_name", "last_name")},
        ),
        (
            "Permissions",
            {
                "classes": ("tab",),
                "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
            },
        ),
        ("Important dates", {"classes": ("tab",), "fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    readonly_fields = ("last_login", "date_joined")

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).annotate(posts_total=Count("posts", distinct=True))

    @display(description="User", header=True, ordering="email")
    def user_header(self, obj: User) -> tuple[str, str, str]:
        return obj.get_full_name(), obj.email, f"{obj.first_name[:1]}{obj.last_name[:1]}".upper()

    @display(description="Active", ordering="is_active", label={True: "success", False: "danger"})
    def active_label(self, obj: User) -> tuple[bool, str]:
        return obj.is_active, "Active" if obj.is_active else "Inactive"

    @display(description="Staff", ordering="is_staff", label={True: "info", False: "warning"})
    def staff_label(self, obj: User) -> tuple[bool, str]:
        return obj.is_staff, "Staff" if obj.is_staff else "Member"

    @display(description="Posts", ordering="posts_total")
    def post_count(self, obj: User) -> int:
        return obj.posts_total

    @action(description="Activate selected users", permissions=["change"])
    def activate_users(self, request: HttpRequest, queryset: QuerySet) -> None:
        count = queryset.update(is_active=True)
        self.message_user(request, f"Activated {count} users.", messages.SUCCESS)

    @action(description="Deactivate selected users", permissions=["change"])
    def deactivate_users(self, request: HttpRequest, queryset: QuerySet) -> None:
        # Keep the acting administrator able to log in.
        count = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(
            request, f"Deactivated {count} users (your account was preserved).", messages.SUCCESS
        )


admin.site.unregister(Group)


@admin.register(Group)
class CustomGroupAdmin(GroupAdmin, ModelAdmin):
    search_fields = ("name",)
