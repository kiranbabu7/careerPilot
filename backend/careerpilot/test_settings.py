"""Test settings — SQLite in-memory for fast local pytest without Docker."""

from careerpilot.settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
