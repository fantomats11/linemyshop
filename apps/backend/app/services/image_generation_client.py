from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings
from app.models import ApiLog
from sqlalchemy.orm import Session


class ImageGenerationClientError(RuntimeError):
    pass


class ImageGenerationConfigurationError(ImageGenerationClientError):
    pass


class FalImageGenerationClient:
    service_name = "fal_image_generation"

    def __init__(
        self,
        session: Session,
        settings: Settings,
        repo_root: Path,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.repo_root = repo_root
        self.http_client = http_client

    def generate_image(
        self,
        prompt: str,
        reference_urls: list[str],
        *,
        quality: str | None = None,
        image_size: str | None = None,
        output_format: str | None = None,
        num_images: int = 1,
    ) -> list[dict[str, Any]]:
        self._validate_settings()
        endpoint = f"https://fal.run/{self.settings.fal_image_model}"
        request_payload = {
            "prompt": prompt,
            "image_urls": [self._resolve_image_url(url) for url in reference_urls],
            "image_size": image_size or self.settings.fal_image_size,
            "quality": quality or self.settings.fal_image_quality,
            "num_images": num_images,
            "output_format": output_format or self.settings.fal_image_format,
        }
        client = self.http_client or httpx.Client(timeout=self.settings.fal_timeout_seconds)
        close_client = self.http_client is None

        try:
            response = client.post(
                endpoint,
                json=request_payload,
                headers={
                    "Authorization": f"Key {self.settings.fal_key}",
                    "Content-Type": "application/json",
                },
            )
            response_payload = self._safe_response_json(response)
            self._log(
                endpoint=endpoint,
                method="POST",
                request_payload={
                    "prompt": prompt,
                    "reference_count": len(reference_urls),
                    "image_size": request_payload["image_size"],
                    "quality": request_payload["quality"],
                    "num_images": num_images,
                    "output_format": request_payload["output_format"],
                    "model": self.settings.fal_image_model,
                },
                response_payload=response_payload,
                status_code=response.status_code,
                error_message=None if response.is_success else response.text,
            )
            if not response.is_success:
                raise ImageGenerationClientError(
                    f"fal.ai image generation failed {response.status_code}: {response.text}"
                )
            images = response_payload.get("images")
            if not isinstance(images, list) or not images:
                raise ImageGenerationClientError("fal.ai response missing images")
            return [image for image in images if isinstance(image, dict)]
        except httpx.HTTPError as exc:
            self._log(
                endpoint=endpoint,
                method="POST",
                request_payload={
                    "prompt": prompt,
                    "reference_count": len(reference_urls),
                    "model": self.settings.fal_image_model,
                },
                response_payload=None,
                status_code=None,
                error_message=str(exc),
            )
            raise ImageGenerationClientError(
                f"fal.ai image generation request failed: {exc}"
            ) from exc
        finally:
            if close_client:
                client.close()

    def download_image(self, url: str, destination: Path) -> None:
        client = self.http_client or httpx.Client(timeout=60.0, follow_redirects=True)
        close_client = self.http_client is None
        try:
            response = client.get(url)
            if not response.is_success:
                raise ImageGenerationClientError(
                    f"generated image download failed {response.status_code}: {response.text}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)
        except httpx.HTTPError as exc:
            raise ImageGenerationClientError(
                f"generated image download failed: {exc}"
            ) from exc
        finally:
            if close_client:
                client.close()

    def _resolve_image_url(self, url: str) -> str:
        if url.startswith(("http://", "https://", "data:")):
            return url
        path = Path(url)
        if not path.is_absolute():
            path = self.repo_root / path
        if not path.exists():
            raise ImageGenerationClientError(f"reference image not found: {url}")
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _validate_settings(self) -> None:
        if self.settings.image_generation_provider != "fal":
            raise ImageGenerationConfigurationError(
                "IMAGE_GENERATION_PROVIDER must be fal"
            )
        if not self.settings.fal_key:
            raise ImageGenerationConfigurationError("FAL_KEY is required")
        if not self.settings.fal_image_model:
            raise ImageGenerationConfigurationError("FAL_IMAGE_MODEL is required")

    def _safe_response_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {"raw": response.text}
        if isinstance(data, dict):
            return data
        return {"data": data}

    def _log(
        self,
        endpoint: str,
        method: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any] | None,
        status_code: int | None,
        error_message: str | None,
    ) -> None:
        self.session.add(
            ApiLog(
                service=self.service_name,
                endpoint=endpoint,
                method=method,
                request_payload=request_payload,
                response_payload=response_payload,
                status_code=status_code,
                error_message=error_message,
            )
        )
