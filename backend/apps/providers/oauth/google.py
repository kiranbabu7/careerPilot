"""Google OAuth token verification provider."""

from dataclasses import dataclass

from django.conf import settings
from google.auth.transport import requests
from google.oauth2 import id_token
from rest_framework.exceptions import AuthenticationFailed


@dataclass
class GoogleUserInfo:
    google_id: str
    email: str
    first_name: str = ""
    last_name: str = ""
    avatar_url: str = ""


class GoogleOAuthProvider:
    """Verifies Google ID tokens and returns normalized user info."""

    def __init__(self, client_id: str | None = None):
        self.client_id = client_id or settings.GOOGLE_OAUTH_CLIENT_ID

    def verify_id_token(self, token: str) -> GoogleUserInfo:
        if not self.client_id:
            raise AuthenticationFailed("Google OAuth is not configured.")

        try:
            payload = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                self.client_id,
            )
        except ValueError as exc:
            raise AuthenticationFailed("Invalid Google token.") from exc

        email = payload.get("email")
        google_id = payload.get("sub")
        if not email or not google_id:
            raise AuthenticationFailed("Google token missing required claims.")

        return GoogleUserInfo(
            google_id=google_id,
            email=email,
            first_name=payload.get("given_name", ""),
            last_name=payload.get("family_name", ""),
            avatar_url=payload.get("picture", ""),
        )
