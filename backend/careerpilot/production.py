"""Production settings validation helpers."""

from __future__ import annotations

INSECURE_SECRET_KEY = "dev-insecure-change-me"


def validate_production_settings(
    *,
    debug: bool,
    secret_key: str,
    allowed_hosts: list[str],
    use_s3_storage: bool = False,
    s3_bucket: str = "",
) -> None:
    if debug:
        return

    if secret_key == INSECURE_SECRET_KEY:
        raise ValueError(
            "DJANGO_SECRET_KEY must be set to a secure value when DJANGO_DEBUG=False"
        )

    if not allowed_hosts:
        raise ValueError(
            "DJANGO_ALLOWED_HOSTS must be set when DJANGO_DEBUG=False"
        )

    if use_s3_storage and not s3_bucket:
        raise ValueError(
            "AWS_STORAGE_BUCKET_NAME must be set when USE_S3_STORAGE is enabled"
        )
