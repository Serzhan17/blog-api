from django.http import HttpRequest
from django.urls import reverse_lazy

from settings.conf import config


def published_link(request: HttpRequest) -> str:
    from apps.blog.callbacks import published_link as link

    return link(request)


def drafts_link(request: HttpRequest) -> str:
    from apps.blog.callbacks import drafts_link as link

    return link(request)


UNFOLD = {
    "SITE_TITLE": "Blog Studio",
    "SITE_HEADER": "Blog Studio",
    "SITE_SUBHEADER": "Content & community",
    "SITE_SYMBOL": "edit_square",
    "SITE_URL": "/admin/",
    "ENVIRONMENT": "apps.blog.callbacks.environment_badge",
    "COLORS": {
        "primary": {
            "50": "#f0fdfa",
            "100": "#ccfbf1",
            "200": "#99f6e4",
            "300": "#5eead4",
            "400": "#2dd4bf",
            "500": "#14b8a6",
            "600": "#0d9488",
            "700": "#0f766e",
            "800": "#115e59",
            "900": "#134e4a",
            "950": "#042f2e",
        }
    },
    "SITE_DROPDOWN": [
        {
            "title": "GitHub repository",
            "icon": "code",
            "link": config("BLOG_REPOSITORY_URL", default="https://github.com/Serzhan17/blog-api"),
        },
        {
            "title": "Unfold documentation",
            "icon": "menu_book",
            "link": "https://unfoldadmin.com/docs/",
        },
    ],
    "COMMAND": {"search_models": True, "show_history": True},
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": "apps.blog.callbacks.sidebar_navigation",
    },
    "TABS": [
        {
            "models": ["blog.post"],
            "items": [
                {"title": "All", "link": reverse_lazy("admin:blog_post_changelist")},
                {"title": "Published", "link": published_link},
                {"title": "Drafts", "link": drafts_link},
            ],
        }
    ],
    "DASHBOARD_CALLBACK": "apps.blog.callbacks.dashboard_callback",
}
