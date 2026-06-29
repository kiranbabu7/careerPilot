from django.urls import path

from apps.jobs.views import CompanyListView

urlpatterns = [
    path("", CompanyListView.as_view(), name="company-list"),
]
