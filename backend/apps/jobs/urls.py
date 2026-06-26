from django.urls import path

from apps.jobs.views import OpportunityDetailView, OpportunityListView

urlpatterns = [
    path("", OpportunityListView.as_view(), name="opportunity-list"),
    path("<uuid:opportunity_id>/", OpportunityDetailView.as_view(), name="opportunity-detail"),
]
