import pytest

from apps.providers.jobs.base import GreenhouseProvider, LeverProvider, TavilyProvider


def test_legacy_job_providers_raise_not_implemented():
    providers = [GreenhouseProvider(), LeverProvider(), TavilyProvider()]
    for provider in providers:
        assert provider.provider_name in ("greenhouse", "lever", "tavily")
        with pytest.raises(NotImplementedError):
            provider.search_jobs("engineer")
