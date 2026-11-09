from typing import Any

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.auths.models import User


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        attrs["email"] = User.objects.normalize_email(attrs["email"])
        return super().validate(attrs)
