from unittest.mock import MagicMock

import pytest

from apps.providers.jobs.company_research_synthesis import (
    CompanyResearchSynthesisProvider,
    build_research_payload,
    build_research_queries,
    collect_snippets,
    format_search_findings,
    normalize_sections,
)
from apps.providers.jobs.tavily_research import TavilyCompanyResearchProvider


class TestBuildResearchQueries:
    def test_queries_cover_business_not_only_hiring(self):
        queries = build_research_queries("YASH Technologies", "Software Engineer")
        categories = [q["category"] for q in queries]
        assert categories == ["overview", "products", "funding", "news", "hiring"]
        joined = " ".join(q["query"] for q in queries).lower()
        assert "company overview" in joined
        assert "products services" in joined
        assert "funding" in joined
        assert "recent news" in joined
        assert "company hiring news" not in joined

    def test_hiring_query_includes_role_when_provided(self):
        queries = build_research_queries("Acme Corp", "Backend Engineer")
        hiring = next(q for q in queries if q["category"] == "hiring")
        assert "Backend Engineer" in hiring["query"]
        assert "careers" in hiring["query"].lower()

    def test_empty_company_returns_no_queries(self):
        assert build_research_queries("") == []


class TestCompanyResearchSynthesis:
    def test_rule_based_fallback_maps_categories(self):
        categorized = [
            {
                "category": "overview",
                "data": {"answer": "YASH is a global IT services firm."},
            },
            {
                "category": "products",
                "data": {"answer": "They deliver digital transformation and cloud services."},
            },
            {
                "category": "funding",
                "data": {"answer": "Privately held; no recent public funding round reported."},
            },
            {
                "category": "news",
                "data": {"answer": "Announced a partnership with a major cloud vendor."},
            },
            {
                "category": "hiring",
                "data": {"answer": "Hiring software engineers across India and the US."},
            },
        ]
        provider = CompanyResearchSynthesisProvider()
        result = provider.synthesize(
            company="YASH Technologies",
            job_title="Software Engineer",
            categorized_searches=categorized,
        )
        assert result.used_fallback is True
        assert "IT services" in result.sections["summary"]
        assert "digital transformation" in result.sections["what_they_do"]
        assert "partnership" in result.sections["recent_news"]
        assert "Privately held" in result.sections["funding"]
        assert "Hiring software engineers" in result.sections["hiring_signals"]

    def test_build_research_payload_includes_structured_sections(self):
        sections = normalize_sections(
            {
                "summary": "Overview text",
                "what_they_do": "Products text",
                "recent_news": "News text",
                "funding": "Funding text",
                "hiring_signals": "Hiring text",
            }
        )
        payload = build_research_payload(
            company="Acme",
            categorized_searches=[
                {
                    "category": "news",
                    "data": {
                        "results": [
                            {
                                "title": "Acme expands",
                                "url": "https://example.com/news",
                                "content": "Acme opened a new office.",
                            }
                        ]
                    },
                }
            ],
            sections=sections,
        )
        assert payload["available"] is True
        assert payload["summary"] == "Overview text"
        assert payload["what_they_do"] == "Products text"
        assert payload["recent_news"] == "News text"
        assert payload["funding"] == "Funding text"
        assert payload["hiring_signals"] == "Hiring text"
        assert payload["snippets"][0]["category"] == "news"

    def test_format_search_findings_includes_categories(self):
        text = format_search_findings(
            [
                {
                    "category": "overview",
                    "data": {
                        "answer": "Acme builds widgets.",
                        "results": [{"title": "About Acme", "content": "Widget maker"}],
                    },
                }
            ]
        )
        assert "Overview" in text
        assert "Acme builds widgets." in text

    def test_collect_snippets_limits_total(self):
        categorized = [
            {
                "category": "overview",
                "data": {
                    "results": [
                        {"title": "A", "url": "https://a", "content": "a"},
                        {"title": "B", "url": "https://b", "content": "b"},
                        {"title": "C", "url": "https://c", "content": "c"},
                    ]
                },
            }
        ]
        snippets = collect_snippets(categorized, max_per_category=2, max_total=2)
        assert len(snippets) == 2

    def test_collect_snippets_dedupes_urls_across_categories(self):
        categorized = [
            {
                "category": "overview",
                "data": {
                    "results": [
                        {
                            "title": "About Acme",
                            "url": "https://example.com/about",
                            "content": "Overview snippet.",
                        }
                    ]
                },
            },
            {
                "category": "news",
                "data": {
                    "results": [
                        {
                            "title": "About Acme again",
                            "url": "https://example.com/about",
                            "content": "News snippet.",
                        },
                        {
                            "title": "Other news",
                            "url": "https://example.com/news",
                            "content": "Different URL.",
                        },
                    ]
                },
            },
        ]
        snippets = collect_snippets(categorized, max_per_category=2, max_total=8)
        urls = [snippet["url"] for snippet in snippets]
        assert urls == ["https://example.com/about", "https://example.com/news"]
        assert snippets[0]["category"] == "overview"


@pytest.mark.django_db
class TestTavilyCompanyResearchProviderMultiSearch:
    def _mock_search_data(self, query: str) -> dict:
        if "overview" in query:
            return {
                "answer": "YASH Technologies is a global IT services and consulting company.",
                "results": [
                    {
                        "title": "About YASH",
                        "url": "https://example.com/about",
                        "content": "Founded in 1996, YASH delivers digital solutions.",
                    }
                ],
            }
        if "products" in query:
            return {
                "answer": "Offers cloud, ERP, and application development services.",
                "results": [],
            }
        if "funding" in query:
            return {
                "answer": "Privately held company.",
                "results": [],
            }
        if "news" in query:
            return {
                "answer": "Recently expanded delivery centers in North America.",
                "results": [
                    {
                        "title": "YASH expansion",
                        "url": "https://example.com/news",
                        "content": "Opened a new delivery center.",
                    }
                ],
            }
        return {
            "answer": "Hiring software engineers for client projects.",
            "results": [
                {
                    "title": "Careers at YASH",
                    "url": "https://example.com/careers",
                    "content": "Open engineering roles.",
                }
            ],
        }

    def test_enrich_company_runs_multiple_searches(self):
        mock_client = MagicMock()
        mock_client.search.side_effect = lambda **kwargs: self._mock_search_data(
            kwargs["query"]
        )
        mock_synthesis = MagicMock()
        mock_synthesis.synthesize.return_value = MagicMock(
            sections=normalize_sections(
                {
                    "summary": "YASH is a global IT services firm.",
                    "what_they_do": "Cloud, ERP, and application development.",
                    "recent_news": "Expanded North America delivery centers.",
                    "funding": "Privately held.",
                    "hiring_signals": "Hiring software engineers.",
                }
            ),
            model_name="rule-based-fallback",
            used_fallback=True,
        )

        provider = TavilyCompanyResearchProvider(
            api_key="tvly-test",
            client=mock_client,
            synthesis_provider=mock_synthesis,
        )
        result = provider.enrich_company("YASH Technologies", job_title="Software Engineer")

        assert result["available"] is True
        assert result["company"] == "YASH Technologies"
        assert "IT services" in result["summary"]
        assert result["what_they_do"]
        assert result["recent_news"]
        assert result["funding"]
        assert result["hiring_signals"]
        assert len(result["snippets"]) >= 1
        assert mock_client.search.call_count == len(build_research_queries("YASH", "SE"))
        first_query = mock_client.search.call_args_list[0].kwargs["query"]
        assert "company overview" in first_query

    def test_partial_search_failures_still_return_research(self):
        mock_client = MagicMock()

        def side_effect(**kwargs):
            if "funding" in kwargs["query"]:
                raise RuntimeError("rate limited")
            return {
                "answer": "Business overview answer.",
                "results": [
                    {
                        "title": "Source",
                        "url": "https://example.com",
                        "content": "Snippet text.",
                    }
                ],
            }

        mock_client.search.side_effect = side_effect
        provider = TavilyCompanyResearchProvider(api_key="tvly-test", client=mock_client)
        result = provider.enrich_company("Acme Corp")
        assert result["available"] is True
        assert result["summary"]

    def test_all_searches_fail_returns_unavailable(self):
        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("401 Unauthorized")
        provider = TavilyCompanyResearchProvider(api_key="tvly-test", client=mock_client)
        result = provider.enrich_company("Acme Corp")
        assert result["available"] is False
        assert result["reason"] == "auth_error"
        assert "401" in result["error"]
        assert len(result["errors"]) >= 1

    def test_fallback_queries_used_when_primary_searches_fail(self):
        mock_client = MagicMock()

        def side_effect(**kwargs):
            if kwargs.get("search_depth") == "basic":
                return {
                    "answer": "Fallback overview for obscure startup.",
                    "results": [
                        {
                            "title": "About",
                            "url": "https://example.com/about",
                            "content": "Obscure startup building hiring tools.",
                        }
                    ],
                }
            raise RuntimeError("advanced search unavailable")

        mock_client.search.side_effect = side_effect
        mock_synthesis = MagicMock()
        mock_synthesis.synthesize.return_value = MagicMock(
            sections={
                "summary": "Fallback overview for obscure startup.",
                "what_they_do": "Hiring tools.",
                "recent_news": "",
                "funding": "",
                "hiring_signals": "",
            }
        )
        provider = TavilyCompanyResearchProvider(
            api_key="tvly-test",
            client=mock_client,
            synthesis_provider=mock_synthesis,
        )
        result = provider.enrich_company("ObscureCo")
        assert result["available"] is True
        assert result["summary"] == "Fallback overview for obscure startup."
        assert any(
            call.kwargs.get("search_depth") == "basic"
            for call in mock_client.search.call_args_list
        )

    def test_backward_compatible_summary_field(self):
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "answer": "Legacy summary only.",
            "results": [],
        }
        provider = TavilyCompanyResearchProvider(api_key="tvly-test", client=mock_client)
        mapped = provider._map_search_response(
            {"answer": "Legacy summary only.", "results": []},
            company="Acme",
            max_results=3,
        )
        assert mapped["summary"] == "Legacy summary only."
        assert mapped["available"] is True
