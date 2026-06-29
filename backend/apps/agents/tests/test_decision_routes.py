import pytest

from apps.agents.decision_routes import resolve_decision_action_route


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (
            {
                "action_type": "material",
                "target_id": "11111111-1111-4111-8111-111111111111",
                "title": "Generate tailored resume for Senior Software Engineer at Recro",
                "route": "/opportunities/11111111-1111-4111-8111-111111111111/tailor-resume",
            },
            "/workspace?goal=Tailor%20my%20resume%20for%20Senior%20Software%20Engineer%20at%20Recro",
        ),
        (
            {
                "action_type": "opportunity",
                "target_id": "22222222-2222-4222-8222-222222222222",
                "title": "Review role",
                "route": "/opportunities/22222222-2222-4222-8222-222222222222",
            },
            "/opportunities?selected=22222222-2222-4222-8222-222222222222",
        ),
        (
            {
                "action_type": "interview",
                "target_id": "33333333-3333-4333-8333-333333333333",
                "title": "Interview prep",
                "route": "/interviews",
            },
            "/interviews?selected=33333333-3333-4333-8333-333333333333&type=prep_plan",
        ),
        (
            {
                "action_type": "workflow",
                "target_id": "44444444-4444-4444-8444-444444444444",
                "title": "Open workflow",
                "route": "/workflows/44444444-4444-4444-8444-444444444444",
            },
            "/workspace?workflow=44444444-4444-4444-8444-444444444444",
        ),
        (
            {
                "action_type": "application",
                "target_id": "55555555-5555-4555-8555-555555555555",
                "title": "Follow up",
                "route": "/applications/55555555-5555-4555-8555-555555555555",
            },
            "/applications",
        ),
    ],
)
def test_resolve_decision_action_route(action, expected):
    assert resolve_decision_action_route(action) == expected
