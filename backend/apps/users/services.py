from dataclasses import dataclass

from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.memory.services import ActivityService, MemoryService
from apps.providers.oauth.google import GoogleOAuthProvider, GoogleUserInfo
from apps.users.repositories import UserPreferenceRepository, UserRepository
from apps.users.serializers import UserPreferenceSerializer, UserSerializer


@dataclass
class AuthTokens:
    access: str
    refresh: str
    user: dict


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository | None = None,
        preference_repo: UserPreferenceRepository | None = None,
        google_provider: GoogleOAuthProvider | None = None,
    ):
        self.user_repo = user_repo or UserRepository()
        self.preference_repo = preference_repo or UserPreferenceRepository()
        self.google_provider = google_provider or GoogleOAuthProvider()

    def register(
        self,
        *,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
    ) -> AuthTokens:
        if self.user_repo.get_by_email(email):
            raise ValidationError({"email": "A user with this email already exists."})

        user = self.user_repo.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        self.preference_repo.get_or_create_for_user(user)
        return self._build_tokens(user)

    def login(self, *, email: str, password: str) -> AuthTokens:
        user = authenticate(username=email, password=password)
        if user is None:
            raise AuthenticationFailed("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationFailed("User account is disabled.")
        return self._build_tokens(user)

    def login_with_google(self, *, id_token: str) -> AuthTokens:
        google_user = self.google_provider.verify_id_token(id_token)
        user = self.user_repo.get_by_google_id(google_user.google_id)

        if user is None:
            existing = self.user_repo.get_by_email(google_user.email)
            if existing:
                user = self.user_repo.update_google_profile(
                    existing,
                    google_id=google_user.google_id,
                    avatar_url=google_user.avatar_url,
                    first_name=google_user.first_name or existing.first_name,
                    last_name=google_user.last_name or existing.last_name,
                )
            else:
                user = self.user_repo.create_google_user(
                    email=google_user.email,
                    google_id=google_user.google_id,
                    first_name=google_user.first_name,
                    last_name=google_user.last_name,
                    avatar_url=google_user.avatar_url,
                )
                self.preference_repo.get_or_create_for_user(user)
        else:
            user = self.user_repo.update_google_profile(
                user,
                avatar_url=google_user.avatar_url,
                first_name=google_user.first_name or user.first_name,
                last_name=google_user.last_name or user.last_name,
            )

        return self._build_tokens(user)

    def refresh(self, refresh_token: str) -> AuthTokens:
        try:
            token = RefreshToken(refresh_token)
            user_id = token["user_id"]
            from apps.users.models import User

            user = User.objects.get(id=user_id)
            return self._build_tokens(user)
        except Exception as exc:
            raise AuthenticationFailed("Invalid refresh token.") from exc

    def get_current_user(self, user) -> dict:
        return UserSerializer(user).data

    def _build_tokens(self, user) -> AuthTokens:
        refresh = RefreshToken.for_user(user)
        return AuthTokens(
            access=str(refresh.access_token),
            refresh=str(refresh),
            user=UserSerializer(user).data,
        )


class PreferenceService:
    def __init__(
        self,
        preference_repo: UserPreferenceRepository | None = None,
        activity_service: ActivityService | None = None,
        memory_service: MemoryService | None = None,
    ):
        self.preference_repo = preference_repo or UserPreferenceRepository()
        self.activity_service = activity_service or ActivityService()
        self.memory_service = memory_service or MemoryService()

    def get_preferences(self, user) -> dict:
        preference, _ = self.preference_repo.get_or_create_for_user(user)
        return UserPreferenceSerializer(preference).data

    def update_preferences(self, user, **fields) -> dict:
        preference = self.preference_repo.update_preferences(user, **fields)
        self.activity_service.record_preferences_updated(user)
        self.memory_service.record_preferences_context(user, preference)
        return UserPreferenceSerializer(preference).data
