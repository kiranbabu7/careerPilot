"""Project middleware."""

from __future__ import annotations

import uuid

from careerpilot.logging_config import clear_request_id, set_request_id


class RequestIdMiddleware:
    """Attach a request ID for tracing and structured logs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.request_id = request_id
        set_request_id(request_id)
        try:
            response = self.get_response(request)
        finally:
            clear_request_id()
        response["X-Request-ID"] = request_id
        return response
