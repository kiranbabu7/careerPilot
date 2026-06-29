from django.utils import timezone

from apps.users.models import User, UserPreference


class UserRepository:
    def get_by_email(self, email: str) -> User | None:
        return User.objects.filter(email__iexact=email).first()

    def get_by_google_id(self, google_id: str) -> User | None:
        return User.objects.filter(google_id=google_id).first()

    def create_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
    ) -> User:
        return User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

    def create_google_user(
        self,
        *,
        email: str,
        google_id: str,
        first_name: str = "",
        last_name: str = "",
        avatar_url: str = "",
    ) -> User:
        user = User(
            email=email,
            google_id=google_id,
            first_name=first_name,
            last_name=last_name,
            avatar_url=avatar_url,
        )
        user.set_unusable_password()
        user.save()
        return user

    def update_google_profile(self, user: User, **fields) -> User:
        for key, value in fields.items():
            setattr(user, key, value)
        user.save()
        return user


class UserPreferenceRepository:
    def get_or_create_for_user(self, user: User) -> tuple[UserPreference, bool]:
        return UserPreference.objects.get_or_create(user=user)

    def update_preferences(self, user: User, **fields) -> UserPreference:
        preference, _ = self.get_or_create_for_user(user)
        if "remote_preference" in fields or "target_locations" in fields:
            fields = {**fields, "locations_configured": True}
        for key, value in fields.items():
            setattr(preference, key, value)
        preference.save()
        return preference

    def list_due_scheduled_searches(self) -> list[UserPreference]:
        now = timezone.now()
        return list(
            UserPreference.objects.filter(
                job_search_schedule_enabled=True,
                next_scheduled_run_at__isnull=False,
                next_scheduled_run_at__lte=now,
            ).select_related("user")
        )
