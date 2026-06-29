"""Media storage configuration (local filesystem vs S3)."""

from __future__ import annotations

import os
from typing import Any


def use_s3_storage(*, debug: bool) -> bool:
    """Return True when uploaded files should use S3."""
    explicit = os.environ.get("USE_S3_STORAGE")
    if explicit is not None:
        return explicit.lower() in ("1", "true", "yes", "on")
    bucket = os.environ.get("AWS_STORAGE_BUCKET_NAME", "").strip()
    if bucket:
        return True
    return False


def s3_bucket_name() -> str:
    return os.environ.get("AWS_STORAGE_BUCKET_NAME", "").strip()


def build_default_storage(*, debug: bool) -> dict[str, Any]:
    if not use_s3_storage(debug=debug):
        return {"BACKEND": "django.core.files.storage.FileSystemStorage"}

    bucket = s3_bucket_name()
    if not bucket:
        raise ValueError(
            "USE_S3_STORAGE is enabled but AWS_STORAGE_BUCKET_NAME is not set"
        )

    options: dict[str, Any] = {
        "bucket_name": bucket,
        "location": os.environ.get("AWS_S3_MEDIA_PREFIX", "media").strip(" /") or "media",
        "file_overwrite": False,
        "default_acl": None,
        "querystring_auth": True,
        "signature_version": "s3v4",
    }

    custom_domain = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "").strip()
    if custom_domain:
        options["custom_domain"] = custom_domain

    endpoint_url = os.environ.get("AWS_S3_ENDPOINT_URL", "").strip()
    if endpoint_url:
        options["endpoint_url"] = endpoint_url

    return {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": options,
    }
