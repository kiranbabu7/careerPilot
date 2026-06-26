"""Job and opportunity persistence."""

from apps.jobs.models import Job, Opportunity


class JobRepository:
    def get_by_dedupe_key(self, dedupe_key: str) -> Job | None:
        return Job.objects.filter(dedupe_key=dedupe_key).first()

    def get_by_source_and_external_id(self, source: str, external_id: str) -> Job | None:
        if not external_id:
            return None
        return Job.objects.filter(source=source, external_id=external_id).first()

    def create(self, **fields) -> Job:
        return Job.objects.create(**fields)

    def update(self, job: Job, **fields) -> Job:
        for key, value in fields.items():
            setattr(job, key, value)
        job.save()
        return job


class OpportunityRepository:
    def list_for_user(self, user) -> list[Opportunity]:
        return list(
            Opportunity.objects.filter(user=user)
            .select_related("job", "workflow_execution")
            .order_by("-created_at")
        )

    def get_for_user(self, user, opportunity_id) -> Opportunity | None:
        return (
            Opportunity.objects.filter(user=user, id=opportunity_id)
            .select_related("job", "workflow_execution")
            .first()
        )

    def get_for_user_job_workflow(
        self, user, job: Job, workflow
    ) -> Opportunity | None:
        return Opportunity.objects.filter(
            user=user,
            job=job,
            workflow_execution=workflow,
        ).first()

    def create(self, **fields) -> Opportunity:
        return Opportunity.objects.create(**fields)

    def count_for_workflow(self, workflow) -> int:
        return Opportunity.objects.filter(workflow_execution=workflow).count()
