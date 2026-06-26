"""Job provider interface and Phase 4 stubs."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobListing:
    external_id: str
    title: str
    company: str
    location: str = ""
    url: str = ""
    description: str = ""
    source: str = ""
    is_remote: bool = False
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    posted_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] = field(default_factory=dict)


class JobProvider(ABC):
    """Interface for job board providers (Greenhouse, Lever, Tavily fallback)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    def search_jobs(self, query: str, **kwargs) -> list[JobListing]:
        ...

    @abstractmethod
    def get_job(self, external_id: str) -> JobListing | None:
        ...


class GreenhouseProvider(JobProvider):
    """Greenhouse job board provider — Phase 4."""

    @property
    def provider_name(self) -> str:
        return "greenhouse"

    def search_jobs(self, query: str, **kwargs) -> list[JobListing]:
        raise NotImplementedError("Greenhouse provider available in Phase 4")

    def get_job(self, external_id: str) -> JobListing | None:
        raise NotImplementedError("Greenhouse provider available in Phase 4")


class LeverProvider(JobProvider):
    """Lever job board provider — Phase 4."""

    @property
    def provider_name(self) -> str:
        return "lever"

    def search_jobs(self, query: str, **kwargs) -> list[JobListing]:
        raise NotImplementedError("Lever provider available in Phase 4")

    def get_job(self, external_id: str) -> JobListing | None:
        raise NotImplementedError("Lever provider available in Phase 4")


class TavilyProvider(JobProvider):
    """Tavily search fallback provider — Phase 4."""

    @property
    def provider_name(self) -> str:
        return "tavily"

    def search_jobs(self, query: str, **kwargs) -> list[JobListing]:
        raise NotImplementedError("Tavily provider available in Phase 4")

    def get_job(self, external_id: str) -> JobListing | None:
        raise NotImplementedError("Tavily provider available in Phase 4")
