from rest_framework import status
from rest_framework.test import APIClient

from django.test import TestCase
from django.urls import reverse

from apps.auths.forms import CustomUserCreationForm
from apps.auths.models import User

TEST_PASSWORD = "Local-Test-Password-467!"


class UserTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="Serzhan@EXAMPLE.COM",
            password=TEST_PASSWORD,
            first_name="Serzhan",
            last_name="Abdykadyr",
        )

    def test_email_and_hashed_password(self) -> None:
        self.assertEqual(self.user.email, "serzhan@example.com")
        self.assertNotEqual(self.user.password, TEST_PASSWORD)
        self.assertTrue(self.user.check_password(TEST_PASSWORD))
        self.assertFalse(self.user.is_staff)

    def test_required_fields(self) -> None:
        with self.assertRaises(ValueError):
            User.objects.create_user("", TEST_PASSWORD)
        with self.assertRaises(ValueError):
            User.objects.create_user("missing@example.com", TEST_PASSWORD)

    def test_superuser_flags(self) -> None:
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                "admin@example.com",
                TEST_PASSWORD,
                first_name="Admin",
                last_name="User",
                is_staff=False,
            )
        admin = User.objects.create_superuser(
            "admin@example.com", TEST_PASSWORD, first_name="Admin", last_name="User"
        )
        self.assertTrue(admin.is_staff and admin.is_superuser and admin.is_active)

    def test_creation_form_hashes_password(self) -> None:
        form = CustomUserCreationForm(
            data={
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "User",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().check_password(TEST_PASSWORD))

    def test_jwt_login_refresh_and_inactive_user(self) -> None:
        client = APIClient()
        url = reverse("auths:token")
        response = client.post(
            url,
            {
                "email": "SERZHAN@example.com",
                "password": TEST_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        refreshed = client.post(
            reverse("auths:token-refresh"),
            {
                "refresh": response.data["refresh"],
            },
        )
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.user.is_active = False
        self.user.save()
        response = client.post(
            url,
            {
                "email": self.user.email,
                "password": TEST_PASSWORD,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_pages(self) -> None:
        admin = User.objects.create_superuser(
            "admin@example.com", TEST_PASSWORD, first_name="Admin", last_name="User"
        )
        self.client.force_login(admin)
        urls = [
            "admin:auths_user_changelist",
            "admin:auths_user_add",
            "admin:blog_post_changelist",
            "admin:blog_post_add",
        ]
        for url in urls:
            self.assertEqual(self.client.get(reverse(url)).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get(
                reverse("admin:auth_user_password_change", args=[self.user.pk])
            ).status_code,
            status.HTTP_200_OK,
        )
