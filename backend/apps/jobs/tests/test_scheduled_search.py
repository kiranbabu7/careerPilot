"""Tests for scheduled job search — incremental filter, Beat tasks, pipeline."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.jobs.scheduled_search import ScheduledJobSearchService
from apps.jobs.services import JobSearchService, _is_new_listing
from apps.jobs.tasks import check_job_search_schedules, run_scheduled_job_search
from apps.memory.models import ActivityEvent
from apps.providers.jobs.apify import (
    build_linkedin_job_search_url,
    build_linkedin_search_urls,
    linkedin_time_posted_filter,
)
from apps.providers.jobs.base import JobListing
from apps.resumes.tests.test_phase2 import user
from apps.users.models import UserPreference
from apps.users.services import PreferenceService
from apps.workflows.models import WorkflowExecution, WorkflowExecutionStatus


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def preferences(user):
    pref, _ = UserPreference.objects.get_or_create(user=user)
    pref.target_roles = ["Senior Backend Engineer"]
    pref.target_locations = ["Remote"]
    pref.remote_preference = "remote"
    pref.skills = ["Python", "Django"]
    pref.save()
    return pref


def _listing(*, posted_at: str | None, external_id: str = "job-1") -> JobListing:
    return JobListing(
        external_id=external_id,
        title="Backend Engineer",
        company="Acme",
        location="Remote",
        source="linkedin",
        posted_at=posted_at,
    )


@pytest.mark.django_db
class TestIncrementalFilter:
    def test_is_new_listing_includes_recent_posted_at(self):
        cutoff = timezone.now() - timedelta(hours=2)
        listing = _listing(posted_at=(timezone.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        assert _is_new_listing(listing, cutoff) is True

    def test_is_new_listing_excludes_old_posted_at(self):
        cutoff = timezone.now() - timedelta(hours=1)
        listing = _listing(posted_at=(timezone.now() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        assert _is_new_listing(listing, cutoff) is False

    def test_is_new_listing_excludes_missing_posted_at(self):
        cutoff = timezone.now() - timedelta(hours=1)
        assert _is_new_listing(_listing(posted_at=None), cutoff) is False

    def test_is_new_listing_includes_date_only_posted_on_same_day(self):
        cutoff = timezone.now().replace(hour=17, minute=21, second=0, microsecond=0)
        listing = _listing(posted_at=cutoff.strftime("%Y-%m-%d"))
        assert _is_new_listing(listing, cutoff) is True

    def test_is_new_listing_excludes_date_only_posted_on_earlier_day(self):
        cutoff = timezone.now()
        listing = _listing(
            posted_at=(cutoff - timedelta(days=2)).strftime("%Y-%m-%d"),
        )
        assert _is_new_listing(listing, cutoff) is False

    def test_linkedin_time_posted_filter_buckets(self):
        now = timezone.now()
        assert linkedin_time_posted_filter(now - timedelta(minutes=30)) == "r3600"
        assert linkedin_time_posted_filter(now - timedelta(hours=3)) == "r86400"
        assert linkedin_time_posted_filter(now - timedelta(days=3)) == "r604800"

    def test_build_linkedin_job_search_url_includes_f_tpr(self):
        posted_since = timezone.now() - timedelta(hours=2)
        url = build_linkedin_job_search_url(
            keywords="Python Engineer",
            location="Remote",
            work_type_filter="2",
            experience_filter="3,4",
            posted_since=posted_since,
        )
        assert "f_TPR=r86400" in url

    def test_service_filters_listings_when_posted_since_set(self, user, preferences):
        workflow = WorkflowExecution.objects.create(
            user=user,
            name="Filter test",
            goal="Find roles",
            status=WorkflowExecutionStatus.RUNNING,
        )
        mock_provider = MagicMock()
        mock_provider.api_token = "token"
        mock_provider.actor_ids = ["linkedin:actor"]
        mock_provider.search_jobs.return_value = [
            _listing(
                posted_at=(timezone.now() - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                external_id="old",
            ),
            _listing(
                posted_at=(timezone.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                external_id="new",
            ),
            _listing(posted_at=None, external_id="missing"),
        ]
        mock_tavily = MagicMock()
        mock_tavily.enrich_jobs.return_value = {}

        service = JobSearchService(
            apify_provider=mock_provider,
            tavily_provider=mock_tavily,
        )
        context = {
            "goal": "Find backend roles",
            "preferences": {
                "target_roles": preferences.target_roles,
                "target_locations": preferences.target_locations,
                "skills": preferences.skills,
                "remote_preference": preferences.remote_preference,
            },
        }
        posted_since = timezone.now() - timedelta(hours=6)
        result = service.search(user, workflow, context, posted_since=posted_since)

        assert result["total_listings"] == 1
        assert result["discovered_count"] == 1

    def test_build_linkedin_search_urls_passes_posted_since(self):
        posted_since = timezone.now() - timedelta(minutes=20)
        urls = build_linkedin_search_urls(
            roles=["Software Engineer"],
            skills=["Python"],
            location="Remote",
            remote_preference="remote",
            posted_since=posted_since,
        )
        assert urls
        assert "f_TPR=r3600" in urls[0]


@pytest.mark.django_db
class TestScheduleDueDetection:
    def test_list_due_scheduled_searches(self, user, preferences):
        now = timezone.now()
        preferences.job_search_schedule_enabled = True
        preferences.job_search_schedule_interval_minutes = 60
        preferences.next_scheduled_run_at = now - timedelta(minutes=1)
        preferences.save()

        due = UserPreference.objects.filter(
            job_search_schedule_enabled=True,
            next_scheduled_run_at__lte=now,
        )
        assert due.count() == 1

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    def test_check_job_search_schedules_enqueues_due_users(self, user, preferences):
        preferences.job_search_schedule_enabled = True
        preferences.job_search_schedule_interval_minutes = 60
        preferences.next_scheduled_run_at = timezone.now() - timedelta(minutes=1)
        preferences.save()

        with patch("apps.jobs.tasks.run_scheduled_job_search.delay") as mock_delay:
            count = check_job_search_schedules()

        assert count == 1
        mock_delay.assert_called_once_with(user.id)


@pytest.mark.django_db
class TestScheduledJobSearchService:
    def _service(self, **kwargs):
        return ScheduledJobSearchService(**kwargs)

    def test_first_run_uses_now_minus_interval_cutoff(self, user, preferences):
        preferences.job_search_schedule_enabled = True
        preferences.job_search_schedule_interval_minutes = 120
        preferences.save()

        service = self._service()
        posted_since = service._resolve_posted_since(preferences)
        assert preferences.last_job_search_at is None
        assert posted_since <= timezone.now() - timedelta(minutes=119)
        assert posted_since >= timezone.now() - timedelta(minutes=121)

    def test_skip_when_apify_not_configured(self, user, preferences):
        preferences.job_search_schedule_enabled = True
        preferences.job_search_schedule_interval_minutes = 60
        preferences.save()

        mock_apify = MagicMock()
        mock_apify.api_token = ""
        mock_apify.actor_ids = []

        result = self._service(apify_provider=mock_apify).run_for_user(user)
        assert result.status == "skipped"
        assert result.reason == "apify_not_configured"

    def test_skip_when_workflow_running(self, user, preferences):
        preferences.job_search_schedule_enabled = True
        preferences.job_search_schedule_interval_minutes = 60
        preferences.save()

        WorkflowExecution.objects.create(
            user=user,
            name="Running workflow",
            goal="Find jobs",
            status=WorkflowExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )

        mock_apify = MagicMock()
        mock_apify.api_token = "token"
        mock_apify.actor_ids = ["linkedin:actor"]

        result = self._service(apify_provider=mock_apify).run_for_user(user)
        assert result.status == "skipped"
        assert result.reason == "workflow_running"

        preferences.refresh_from_db()
        assert preferences.last_scheduled_run_at is not None
        assert "already running" in preferences.last_schedule_message.lower()

    def test_stale_running_workflow_is_cleared_before_search(
        self, user, preferences
    ):
        preferences.job_search_schedule_enabled = True
        preferences.job_search_schedule_interval_minutes = 60
        preferences.target_roles = []
        preferences.career_goals = ""
        preferences.save()

        WorkflowExecution.objects.create(
            user=user,
            name="Stale workflow",
            goal="Find jobs",
            status=WorkflowExecutionStatus.RUNNING,
            started_at=timezone.now() - timedelta(hours=3),
        )

        mock_apify = MagicMock()
        mock_apify.api_token = "token"
        mock_apify.actor_ids = ["linkedin:actor"]

        result = self._service(apify_provider=mock_apify).run_for_user(user)

        assert result.status == "skipped"
        assert result.reason == "missing_preferences"

        stale = WorkflowExecution.objects.get(name="Stale workflow")
        assert stale.status == WorkflowExecutionStatus.FAILED
        assert "timed out" in stale.error_message.lower()

    @patch.object(ScheduledJobSearchService, "_has_running_workflow", return_value=False)
    @patch("apps.jobs.scheduled_search.JobSearchAgent")
    def test_full_pipeline_creates_workflow_and_evaluates(
        self,
        mock_agent_cls,
        _mock_running,
        user,
        preferences,
    ):
        preferences.job_search_schedule_enabled = True
        preferences.job_search_schedule_interval_minutes = 60
        preferences.save()

        mock_apify = MagicMock()
        mock_apify.api_token = "token"
        mock_apify.actor_ids = ["linkedin:actor"]

        mock_agent = MagicMock()
        mock_execution = MagicMock()
        mock_execution.id = "exec-1"
        mock_agent.search.return_value = {
            "execution": mock_execution,
            "discovered_count": 2,
            "provider_summary": {"providers": {}},
            "reasoning_summary": "Found 2 roles.",
        }
        mock_agent_cls.return_value = mock_agent

        mock_workflow_service = MagicMock()
        mock_workflow_service._evaluate_discovered_opportunities.return_value = {
            "evaluated_count": 2,
            "accepted_count": 1,
            "borderline_count": 1,
            "rejected_count": 0,
            "top_match_score": 85,
            "evaluation_executions": [],
        }

        service = ScheduledJobSearchService(
            apify_provider=mock_apify,
            job_search_agent=mock_agent,
            workflow_service=mock_workflow_service,
        )
        result = service.run_for_user(user)

        assert result.status == "completed"
        assert result.discovered_count == 2
        assert result.evaluated_count == 2

        workflow = WorkflowExecution.objects.get(id=result.workflow_id)
        assert workflow.context.get("trigger") == "scheduled"
        assert workflow.status == WorkflowExecutionStatus.COMPLETED
        assert workflow.result["discovered_count"] == 2
        assert workflow.result["evaluated_count"] == 2

        preferences.refresh_from_db()
        assert preferences.last_job_search_at is not None
        assert preferences.last_scheduled_run_at is not None
        assert preferences.next_scheduled_run_at is not None

        event = ActivityEvent.objects.filter(
            user=user,
            event_type=ActivityEvent.EventType.SCHEDULED_SEARCH,
        ).first()
        assert event is not None

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    @patch.object(ScheduledJobSearchService, "run_for_user")
    def test_run_scheduled_job_search_task(self, mock_run, user, preferences):
        mock_run.return_value = MagicMock(
            status="completed",
            reason="",
            workflow_id="wf-1",
            discovered_count=1,
            evaluated_count=1,
        )

        result = run_scheduled_job_search(user.id)
        assert result["status"] == "completed"
        mock_run.assert_called_once()


@pytest.mark.django_db
class TestPreferencesScheduleApi:
    def test_preferences_round_trip_schedule_fields(self, api_client, user, preferences):
        api_client.force_authenticate(user=user)
        url = reverse("user-preferences")

        response = api_client.patch(
            url,
            {
                "job_search_schedule_enabled": True,
                "job_search_schedule_interval_minutes": 240,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["job_search_schedule_enabled"] is True
        assert response.data["job_search_schedule_interval_minutes"] == 240
        assert response.data["next_scheduled_run_at"] is not None

        preferences.refresh_from_db()
        assert preferences.next_scheduled_run_at is not None

    def test_preferences_rejects_invalid_interval(self, api_client, user):
        api_client.force_authenticate(user=user)
        url = reverse("user-preferences")

        response = api_client.patch(
            url,
            {
                "job_search_schedule_enabled": True,
                "job_search_schedule_interval_minutes": 90,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_schedule_status_endpoint(self, api_client, user, preferences):
        preferences.job_search_schedule_enabled = True
        preferences.job_search_schedule_interval_minutes = 60
        preferences.last_scheduled_run_at = timezone.now() - timedelta(hours=1)
        preferences.next_scheduled_run_at = timezone.now() + timedelta(hours=1)
        preferences.save()

        api_client.force_authenticate(user=user)
        response = api_client.get(reverse("job-schedule-status"))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["enabled"] is True
        assert response.data["interval_minutes"] == 60
        assert response.data["next_run_at"] is not None

    def test_enabling_schedule_sets_next_run_via_service(self, user, preferences):
        data = PreferenceService().update_preferences(
            user,
            job_search_schedule_enabled=True,
            job_search_schedule_interval_minutes=720,
        )
        assert data["job_search_schedule_enabled"] is True
        assert data["next_scheduled_run_at"] is not None
