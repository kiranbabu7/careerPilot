"""Job and opportunity persistence."""

from django.db.models import Q

from apps.jobs.evaluation import BORDERLINE_MATCH_THRESHOLD, HIGH_MATCH_THRESHOLD
from apps.workflows.models import WorkflowExecution, WorkflowExecutionStatus
from apps.jobs.models import Job, Opportunity, OpportunityStatus
from apps.providers.jobs.base import JobListing
from apps.providers.jobs.normalization import (
    build_dedupe_key,
    build_title_company_location_key,
    normalize_apply_url,
)


class JobRepository:
    def get_by_dedupe_key(self, dedupe_key: str) -> Job | None:
        return Job.objects.filter(dedupe_key=dedupe_key).first()

    def get_by_source_and_external_id(self, source: str, external_id: str) -> Job | None:
        if not external_id:
            return None
        return Job.objects.filter(source=source, external_id=external_id).first()

    def get_by_apply_url(self, url: str) -> Job | None:
        normalized = normalize_apply_url(url)
        if not normalized:
            return None
        for job in Job.objects.exclude(apply_url="").iterator():
            if normalize_apply_url(job.apply_url) == normalized:
                return job
        return None

    def get_by_title_company_location(
        self, title: str, company: str, location: str
    ) -> Job | None:
        key = build_title_company_location_key(title, company, location)
        if not key:
            return None
        for job in Job.objects.iterator():
            job_key = build_title_company_location_key(
                job.title, job.company, job.location
            )
            if job_key == key:
                return job
        return None

    def find_existing(self, listing: JobListing) -> Job | None:
        """Resolve an existing job by dedupe key, external id, URL, or title+company+location."""
        dedupe_key = build_dedupe_key(listing)
        job = self.get_by_dedupe_key(dedupe_key)
        if job:
            return job

        if listing.external_id and listing.source:
            job = self.get_by_source_and_external_id(listing.source, listing.external_id)
            if job:
                return job

        if listing.url:
            job = self.get_by_apply_url(listing.url)
            if job:
                return job

        return self.get_by_title_company_location(
            listing.title, listing.company, listing.location
        )

    def create(self, **fields) -> Job:
        return Job.objects.create(**fields)

    def update(self, job: Job, **fields) -> Job:
        for key, value in fields.items():
            setattr(job, key, value)
        job.save()
        return job


class OpportunityRepository:
    def list_for_user(
        self,
        user,
        *,
        include_rejected: bool = False,
        include_low_match: bool = False,
        high_match_threshold: int | None = None,
    ) -> list[Opportunity]:
        threshold = (
            high_match_threshold
            if high_match_threshold is not None
            else HIGH_MATCH_THRESHOLD
        )
        qs = (
            Opportunity.objects.filter(user=user)
            .select_related("job", "workflow_execution")
            .order_by("-created_at")
        )
        qs = qs.filter(match_score__isnull=False)

        worthwhile = (
            Q(match_score__gte=threshold)
            | Q(status__in=[OpportunityStatus.SAVED, OpportunityStatus.APPLIED])
            | Q(
                status=OpportunityStatus.DISCOVERED,
                match_score__gte=BORDERLINE_MATCH_THRESHOLD,
            )
        )
        if include_rejected:
            worthwhile |= Q(status=OpportunityStatus.REJECTED)

        if not include_low_match:
            qs = qs.filter(worthwhile)
        elif not include_rejected:
            qs = qs.exclude(status=OpportunityStatus.REJECTED)

        return list(qs)

    def list_for_workflow_refinement(
        self,
        user,
        workflow,
        *,
        include_rejected: bool = False,
        include_borderline: bool = False,
        high_match_threshold: int | None = None,
    ) -> list[Opportunity]:
        """Opportunities linked to a workflow with refinement filter controls."""
        qs = (
            Opportunity.objects.filter(user=user, workflow_execution=workflow)
            .select_related("job")
            .filter(match_score__isnull=False)
            .order_by("-match_score", "-created_at")
        )
        threshold = (
            high_match_threshold
            if high_match_threshold is not None
            else HIGH_MATCH_THRESHOLD
        )

        if include_rejected and include_borderline:
            return list(qs)

        filters = Q(match_score__gte=threshold) | Q(
            status__in=[OpportunityStatus.SAVED, OpportunityStatus.APPLIED]
        )
        if include_borderline:
            filters |= Q(
                status=OpportunityStatus.DISCOVERED,
                match_score__gte=BORDERLINE_MATCH_THRESHOLD,
                match_score__lt=threshold,
            )
        if include_rejected:
            filters |= Q(status=OpportunityStatus.REJECTED)

        return list(qs.filter(filters))

    def get_last_search_summary(self, user) -> dict | None:
        """Latest completed workflow search/evaluation stats for empty-state messaging."""
        workflow = (
            WorkflowExecution.objects.filter(
                user=user,
                status=WorkflowExecutionStatus.COMPLETED,
            )
            .order_by("-completed_at", "-created_at")
            .first()
        )
        if workflow is None:
            return None

        result = workflow.result or {}
        discovered = int(result.get("discovered_count") or 0)
        evaluated = int(result.get("evaluated_count") or 0)
        accepted = int(result.get("accepted_count") or 0)
        borderline = int(result.get("borderline_count") or 0)
        rejected = int(result.get("rejected_count") or 0)
        top_score = int(result.get("top_match_score") or 0)

        if not any([discovered, evaluated, accepted, borderline, rejected, top_score]):
            return None

        return {
            "workflow_id": str(workflow.id),
            "discovered_count": discovered,
            "evaluated_count": evaluated,
            "accepted_count": accepted,
            "borderline_count": borderline,
            "rejected_count": rejected,
            "top_match_score": top_score,
            "high_match_threshold": HIGH_MATCH_THRESHOLD,
            "borderline_match_threshold": BORDERLINE_MATCH_THRESHOLD,
            "completed_at": workflow.completed_at,
        }

    def get_for_user(self, user, opportunity_id) -> Opportunity | None:
        return (
            Opportunity.objects.filter(user=user, id=opportunity_id)
            .select_related("job", "workflow_execution")
            .first()
        )

    def get_for_user_job(self, user, job: Job) -> Opportunity | None:
        return (
            Opportunity.objects.filter(user=user, job=job)
            .order_by("-created_at")
            .first()
        )

    def get_for_user_equivalent_job(
        self, user, title: str, company: str, location: str
    ) -> Opportunity | None:
        """User opportunity matching normalized title + company + location."""
        key = build_title_company_location_key(title, company, location)
        if not key:
            return None
        for opportunity in (
            Opportunity.objects.filter(user=user).select_related("job").iterator()
        ):
            job_key = build_title_company_location_key(
                opportunity.job.title,
                opportunity.job.company,
                opportunity.job.location,
            )
            if job_key == key:
                return opportunity
        return None

    def get_for_user_job_workflow(
        self, user, job: Job, workflow
    ) -> Opportunity | None:
        return Opportunity.objects.filter(
            user=user,
            job=job,
            workflow_execution=workflow,
        ).first()

    def get_or_create_for_user_job(
        self,
        user,
        job: Job,
        *,
        workflow=None,
        defaults: dict | None = None,
    ) -> tuple[Opportunity, bool]:
        defaults = defaults or {}
        if workflow is not None and "workflow_execution" not in defaults:
            defaults = {**defaults, "workflow_execution": workflow}
        return Opportunity.objects.get_or_create(
            user=user,
            job=job,
            defaults=defaults,
        )

    def create(self, **fields) -> Opportunity:
        return Opportunity.objects.create(**fields)

    def count_for_workflow(self, workflow) -> int:
        return Opportunity.objects.filter(workflow_execution=workflow).count()

    def list_for_workflow(self, workflow, *, limit: int | None = None) -> list[Opportunity]:
        qs = (
            Opportunity.objects.filter(workflow_execution=workflow)
            .select_related("job")
            .order_by("created_at")
        )
        if limit is not None:
            qs = qs[:limit]
        return list(qs)

    def count_unevaluated_for_user(self, user) -> int:
        return Opportunity.objects.filter(user=user, match_score__isnull=True).count()

    def list_unevaluated_for_user(self, user) -> list[Opportunity]:
        return list(
            Opportunity.objects.filter(user=user, match_score__isnull=True)
            .select_related("job")
            .order_by("created_at")
        )

    def list_unevaluated_for_workflow(self, workflow) -> list[Opportunity]:
        return list(
            Opportunity.objects.filter(
                workflow_execution=workflow,
                match_score__isnull=True,
            )
            .select_related("job")
            .order_by("created_at")
        )

    def update_status(self, opportunity: Opportunity, status: str) -> Opportunity:
        opportunity.status = status
        opportunity.save(update_fields=["status", "updated_at"])
        return opportunity

    def update_evaluation(
        self,
        opportunity: Opportunity,
        *,
        match_score: int,
        evaluation: dict,
    ) -> Opportunity:
        opportunity.match_score = match_score
        opportunity.evaluation = evaluation
        opportunity.save(update_fields=["match_score", "evaluation", "updated_at"])
        return opportunity

    def list_companies_for_user(self, user) -> list[dict]:
        """Aggregate unique companies from evaluated, non-rejected opportunities."""
        opportunities = (
            Opportunity.objects.filter(user=user, match_score__isnull=False)
            .exclude(status=OpportunityStatus.REJECTED)
            .select_related("job")
            .order_by("-created_at")
        )
        companies: dict[str, dict] = {}
        for opp in opportunities:
            company_name = (opp.job.company or "").strip()
            if not company_name:
                continue
            key = company_name.lower()
            if key not in companies:
                companies[key] = {
                    "name": company_name,
                    "opportunity_count": 0,
                    "opportunity_ids": [],
                    "latest_research": opp.job.company_research or {},
                    "has_research": bool(
                        (opp.job.company_research or {}).get("available")
                    ),
                }
            entry = companies[key]
            entry["opportunity_count"] += 1
            entry["opportunity_ids"].append(str(opp.id))
            research = opp.job.company_research or {}
            if research.get("available") and not entry["has_research"]:
                entry["latest_research"] = research
                entry["has_research"] = True
        return sorted(companies.values(), key=lambda c: c["name"].lower())
