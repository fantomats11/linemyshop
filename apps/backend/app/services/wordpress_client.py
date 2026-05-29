from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import Settings


class WordPressClientError(RuntimeError):
    pass


class WordPressConfigurationError(WordPressClientError):
    pass


class WordPressMediaClient:
    def __init__(
        self,
        settings: Settings,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.http_client = http_client

    def upload_media(self, file_path: Path) -> dict[str, Any]:
        self._validate_settings()
        if not file_path.exists():
            raise WordPressClientError(f"file not found: {file_path}")
        if not file_path.is_file():
            raise WordPressClientError(f"path is not a file: {file_path}")

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        url = urljoin(
            f"{self.settings.wordpress_base_url.rstrip('/')}/",
            "wp-json/wp/v2/media",
        )
        client = self.http_client or httpx.Client(timeout=60.0)
        close_client = self.http_client is None

        try:
            response = client.post(
                url,
                content=file_path.read_bytes(),
                auth=(
                    self.settings.wordpress_username,
                    self.settings.wordpress_application_password,
                ),
                headers={
                    "Content-Disposition": f'attachment; filename="{file_path.name}"',
                    "Content-Type": content_type,
                },
            )
            response_payload = self._safe_response_json(response)
            if not response.is_success:
                raise WordPressClientError(
                    f"WordPress media upload failed {response.status_code}: {response.text}"
                )
            if not response_payload.get("source_url"):
                raise WordPressClientError("WordPress media response missing source_url")
            return response_payload
        except httpx.HTTPError as exc:
            raise WordPressClientError(f"WordPress media upload failed: {exc}") from exc
        finally:
            if close_client:
                client.close()

    def _validate_settings(self) -> None:
        if not self.settings.wordpress_base_url:
            raise WordPressConfigurationError("WORDPRESS_BASE_URL is required")
        if not self.settings.wordpress_username:
            raise WordPressConfigurationError("WORDPRESS_USERNAME is required")
        if not self.settings.wordpress_application_password:
            raise WordPressConfigurationError(
                "WORDPRESS_APPLICATION_PASSWORD is required"
            )

    def _safe_response_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {"raw": response.text}
        if isinstance(data, dict):
            return data
        return {"data": data}
