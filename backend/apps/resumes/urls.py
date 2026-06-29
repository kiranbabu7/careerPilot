from django.urls import path

from apps.resumes.views import (
    ApplicationMaterialListView,
    ApplicationMaterialPdfView,
    ResumeDetailView,
    ResumeListCreateView,
    ResumeSetActiveView,
)

urlpatterns = [
    path("", ResumeListCreateView.as_view(), name="resume-list"),
    path("materials/", ApplicationMaterialListView.as_view(), name="resume-materials"),
    path(
        "materials/<uuid:material_id>/pdf/",
        ApplicationMaterialPdfView.as_view(),
        name="resume-material-pdf",
    ),
    path("<uuid:resume_id>/", ResumeDetailView.as_view(), name="resume-detail"),
    path(
        "<uuid:resume_id>/set-active/",
        ResumeSetActiveView.as_view(),
        name="resume-set-active",
    ),
]
