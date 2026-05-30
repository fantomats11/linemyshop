from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import ApiLog


class LineMyShopClientError(RuntimeError):
    pass


class LineMyShopConfigurationError(LineMyShopClientError):
    pass


class LineMyShopMockClient:
    service_name = "line_myshop_mock"

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = {
            "external_product_id": f"mock_line_product_{payload['product_id']}",
            "variants": [
                {
                    "variant_id": variant["id"],
                    "external_variant_id": f"mock_line_variant_{variant['id']}",
                    "external_sku": variant["sku"],
                }
                for variant in payload["variants"]
            ],
        }
        self._log(
            endpoint="/mock/products",
            method="POST",
            request_payload=payload,
            response_payload=response,
            status_code=200,
        )
        return response

    def build_outbound_product_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def update_product(
        self, external_product_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        response = {
            "external_product_id": external_product_id,
            "updated": True,
        }
        self._log(
            endpoint=f"/mock/products/{external_product_id}",
            method="PUT",
            request_payload=payload,
            response_payload=response,
            status_code=200,
        )
        return response

    def get_product(self, external_product_id: str) -> dict[str, Any]:
        response = {
            "id": external_product_id,
            "isDisplay": False,
        }
        self._log(
            endpoint=f"/mock/products/{external_product_id}",
            method="GET",
            request_payload={},
            response_payload=response,
            status_code=200,
        )
        return response

    def update_visibility(
        self, external_product_id: str, is_display: bool
    ) -> dict[str, Any]:
        payload = {"isDisplay": is_display}
        response = {
            "external_product_id": external_product_id,
            "isDisplay": is_display,
            "updated": True,
        }
        self._log(
            endpoint=f"/mock/products/{external_product_id}/visibility",
            method="PATCH",
            request_payload=payload,
            response_payload=response,
            status_code=200,
        )
        return response

    def update_inventory(
        self, external_variant_id: str, stock: int
    ) -> dict[str, Any]:
        payload = {"stock": stock}
        response = {
            "external_variant_id": external_variant_id,
            "stock": stock,
            "updated": True,
        }
        self._log(
            endpoint=f"/mock/variants/{external_variant_id}/inventory",
            method="PUT",
            request_payload=payload,
            response_payload=response,
            status_code=200,
        )
        return response

    def update_price(
        self,
        external_variant_id: str,
        price: Decimal,
        sale_price: Decimal | None = None,
    ) -> dict[str, Any]:
        payload = {
            "price": str(price),
            "sale_price": str(sale_price) if sale_price is not None else None,
        }
        response = {
            "external_variant_id": external_variant_id,
            "price": str(price),
            "sale_price": str(sale_price) if sale_price is not None else None,
            "updated": True,
        }
        self._log(
            endpoint=f"/mock/variants/{external_variant_id}/price",
            method="PUT",
            request_payload=payload,
            response_payload=response,
            status_code=200,
        )
        return response

    def _log(
        self,
        endpoint: str,
        method: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any],
        status_code: int,
    ) -> None:
        self.session.add(
            ApiLog(
                service=self.service_name,
                endpoint=endpoint,
                method=method,
                request_payload=request_payload,
                response_payload=response_payload,
                status_code=status_code,
                error_message=None,
            )
        )


class LineMyShopRealClient:
    service_name = "line_myshop"

    def __init__(
        self,
        session: Session,
        settings: Settings,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.http_client = http_client

    def create_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_settings()
        return self._request(
            method="POST",
            path=self.settings.line_myshop_create_product_path,
            payload=self.build_outbound_product_payload(payload),
        )

    def update_product(
        self, external_product_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self._validate_settings()
        return self._request(
            method="PATCH",
            path=self.settings.line_myshop_update_product_path.format(
                external_product_id=external_product_id
            ),
            payload=self._to_oaplus_product_update_payload(payload),
        )

    def get_product(self, external_product_id: str) -> dict[str, Any]:
        self._validate_settings()
        response = self._request(
            method="GET",
            path=self.settings.line_myshop_create_product_path,
            payload={},
            params={"ids": external_product_id},
        )
        data = response.get("data")
        if isinstance(data, list):
            for item in data:
                if str(item.get("id")) == str(external_product_id):
                    return item
            if data:
                return data[0]
        if isinstance(data, dict):
            return data
        return response

    def update_visibility(
        self, external_product_id: str, is_display: bool
    ) -> dict[str, Any]:
        self._validate_settings()
        display_status = "onsale" if is_display else "hide"
        return self._request(
            method="POST",
            path=(
                self.settings.line_myshop_update_product_path.format(
                    external_product_id=external_product_id
                ).rstrip("/")
                + f"/display-status/{display_status}"
            ),
            payload={},
        )

    def build_outbound_product_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._to_oaplus_product_payload(payload)

    def update_inventory(
        self, external_variant_id: str, stock: int
    ) -> dict[str, Any]:
        if not self.settings.line_myshop_update_inventory_path:
            return {"external_variant_id": external_variant_id, "skipped": True}
        return self._request(
            method="PUT",
            path=self.settings.line_myshop_update_inventory_path.format(
                external_variant_id=external_variant_id
            ),
            payload={"stock": stock},
        )

    def update_price(
        self,
        external_variant_id: str,
        price: Decimal,
        sale_price: Decimal | None = None,
    ) -> dict[str, Any]:
        if not self.settings.line_myshop_update_price_path:
            return {"external_variant_id": external_variant_id, "skipped": True}
        return self._request(
            method="PUT",
            path=self.settings.line_myshop_update_price_path.format(
                external_variant_id=external_variant_id
            ),
            payload={
                "price": str(price),
                "sale_price": str(sale_price) if sale_price is not None else None,
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._validate_settings()
        url = urljoin(f"{self.settings.line_myshop_base_url.rstrip('/')}/", path.lstrip("/"))
        client = self.http_client or httpx.Client(
            timeout=self.settings.line_myshop_timeout_seconds
        )
        close_client = self.http_client is None
        try:
            response = client.request(
                method,
                url,
                json=payload,
                params=params,
                headers={
                    self.settings.line_myshop_api_key_header: (
                        self.settings.line_myshop_api_key
                    ),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            response_payload = self._safe_response_json(response)
            self._log(
                endpoint=path,
                method=method,
                request_payload={"json": payload, "params": params or {}},
                response_payload=response_payload,
                status_code=response.status_code,
                error_message=None if response.is_success else response.text,
            )
            if not response.is_success:
                raise LineMyShopClientError(
                    f"LINE MyShop API returned {response.status_code}: {response.text}"
                )
            return response_payload
        except httpx.HTTPError as exc:
            self._log(
                endpoint=path,
                method=method,
                request_payload=payload,
                response_payload=None,
                status_code=None,
                error_message=str(exc),
            )
            raise LineMyShopClientError(f"LINE MyShop API request failed: {exc}") from exc
        finally:
            if close_client:
                client.close()

    def _validate_settings(self) -> None:
        if not self.settings.line_myshop_base_url:
            raise LineMyShopConfigurationError("LINE_MYSHOP_BASE_URL is required")
        if "your-line-myshop-api-base-url" in self.settings.line_myshop_base_url:
            raise LineMyShopConfigurationError(
                "LINE_MYSHOP_BASE_URL must be a real LINE MyShop API base URL"
            )
        if not self.settings.line_myshop_api_key:
            raise LineMyShopConfigurationError("LINE_MYSHOP_API_KEY is required")

    def _to_oaplus_product_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.settings.line_myshop_default_category_id is None:
            raise LineMyShopConfigurationError(
                "LINE_MYSHOP_DEFAULT_CATEGORY_ID is required for real product sync"
            )

        image_urls = [image["url"] for image in payload["images"]]
        if not image_urls:
            raise LineMyShopConfigurationError(
                "at least one approved product image is required for real product sync"
            )

        color_values = sorted({payload["color"]})
        size_values = [variant["size"] for variant in payload["variants"]]
        option1_lookup = {value: index for index, value in enumerate(color_values)}
        option2_lookup = {value: index for index, value in enumerate(size_values)}

        return {
            "brand": self.settings.line_myshop_default_brand or payload["category"],
            "categoryId": self.settings.line_myshop_default_category_id,
            "code": payload["product_group"],
            "description": payload["description"] or "",
            "imageUrls": image_urls[:7],
            "instantDiscount": 0,
            "name": payload["name"],
            "variantOptions": {
                "option1": {
                    "name": "color",
                    "data": [
                        {
                            "value": value,
                            "imageUrl": image_urls[0],
                        }
                        for value in color_values
                    ],
                },
                "option2": {
                    "name": "size",
                    "data": [{"value": value} for value in size_values],
                },
            },
            "variants": [
                {
                    "barcode": variant["barcode"] or variant["sku"],
                    "discountedPrice": (
                        int(Decimal(variant["sale_price"]))
                        if variant["sale_price"] is not None
                        else 0
                    ),
                    "onHandNumber": variant["available_stock"],
                    "options": [
                        option1_lookup[payload["color"]],
                        option2_lookup[variant["size"]],
                    ],
                    "price": int(Decimal(variant["price"])),
                    "sku": variant["sku"],
                    "weight": self.settings.line_myshop_default_weight,
                }
                for variant in payload["variants"]
            ],
        }

    def _to_oaplus_product_update_payload(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        create_payload = self._to_oaplus_product_payload(payload)
        return {
            key: value
            for key, value in create_payload.items()
            if key not in {"variantOptions", "variants"}
        }

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


def create_line_myshop_client(
    session: Session, settings: Settings
) -> LineMyShopMockClient | LineMyShopRealClient:
    if settings.line_myshop_mock_mode:
        return LineMyShopMockClient(session)
    return LineMyShopRealClient(session, settings)
