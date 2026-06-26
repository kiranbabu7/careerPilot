from django.urls import path

from apps.users.views import PreferencesView

urlpatterns = [
    path("preferences/", PreferencesView.as_view(), name="user-preferences"),
]
