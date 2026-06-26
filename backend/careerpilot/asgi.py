"""ASGI config for CareerPilot project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "careerpilot.settings")

application = get_asgi_application()
