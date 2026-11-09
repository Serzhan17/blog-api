from rest_framework_simplejwt.views import TokenRefreshView

from django.urls import path

from apps.auths.views import EmailTokenObtainPairView

app_name = "auths"
urlpatterns = [
    path("token/", EmailTokenObtainPairView.as_view(), name="token"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]
