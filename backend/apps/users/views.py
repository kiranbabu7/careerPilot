from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import (
    GoogleAuthSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserPreferenceSerializer,
    UserSerializer,
)
from apps.users.services import AuthService, PreferenceService


def _auth_error_response(exc: Exception) -> Response:
    if isinstance(exc, AuthenticationFailed):
        detail = exc.detail
    else:
        detail = str(exc)
    return Response({"detail": detail}, status=status.HTTP_401_UNAUTHORIZED)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = AuthService().register(**serializer.validated_data)
        return Response(
            {
                "access": tokens.access,
                "refresh": tokens.refresh,
                "user": tokens.user,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tokens = AuthService().login(**serializer.validated_data)
        except AuthenticationFailed as exc:
            return _auth_error_response(exc)
        return Response(
            {
                "access": tokens.access,
                "refresh": tokens.refresh,
                "user": tokens.user,
            }
        )


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tokens = AuthService().login_with_google(**serializer.validated_data)
        except AuthenticationFailed as exc:
            return _auth_error_response(exc)
        return Response(
            {
                "access": tokens.access,
                "refresh": tokens.refresh,
                "user": tokens.user,
            }
        )


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tokens = AuthService().refresh(refresh)
        return Response(
            {
                "access": tokens.access,
                "refresh": tokens.refresh,
                "user": tokens.user,
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class PreferencesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = PreferenceService().get_preferences(request.user)
        return Response(data)

    def patch(self, request):
        writable_fields = (
            "target_roles",
            "target_locations",
            "salary_min",
            "salary_max",
            "remote_preference",
            "career_goals",
            "skills",
            "job_search_schedule_enabled",
            "job_search_schedule_interval_minutes",
        )
        filtered = {k: v for k, v in request.data.items() if k in writable_fields}
        serializer = UserPreferenceSerializer(data=filtered, partial=True)
        serializer.is_valid(raise_exception=True)
        data = PreferenceService().update_preferences(
            request.user,
            **serializer.validated_data,
        )
        return Response(data)
