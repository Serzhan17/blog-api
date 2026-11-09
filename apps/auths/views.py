from rest_framework_simplejwt.views import TokenObtainPairView

from apps.auths.serializers import EmailTokenObtainPairSerializer


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
