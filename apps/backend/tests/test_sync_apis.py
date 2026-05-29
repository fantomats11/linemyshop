from pathlib import Path
from typing import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
import app.api.sync as sync_api
from app.commands.import_products import import_rows, read_product_rows
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.main import app
from app.models import (
    ApiLog,
    ChannelProduct,
    ChannelVariant,
    Product,
    ProductImage,
    SyncJob,
)
from app.services.line_myshop_client import LineMyShopRealClient


CSV_CONTENT = """product_group,product_name,color,gender,category,price,sale_price,size,waist,hip,length,sku,barcode,stock,image_1,image_2,image_3,description,note,status
jeans-sync,กางเกงยีนส์ Sync,ยีนส์เข้ม,หญิง,กางเกงยีนส์,1750,,M,26-28,34-36,40,SYNC-M,,5,https://example.com/sync-1.jpg,https://example.com/sync-2.jpg,,รายละเอียด Sync,note Sync,draft
jeans-sync,กางเกงยีนส์ Sync,ยีนส์เข้ม,หญิง,กางเกงยีนส์,1750,,L,28-30,36-38,40,SYNC-L,SYNC-L,3,https://example.com/sync-1.jpg,https://example.com/sync-2.jpg,,รายละเอียด Sync,note Sync,draft
"""


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("LINE_MYSHOP_MOCK_MODE", "true")
    monkeypatch.setenv("LINE_MYSHOP_BASE_URL", "")
    monkeypatch.setenv("LINE_MYSHOP_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    csv_path = tmp_path / "valid_products.csv"
    csv_path.write_text(CSV_CONTENT, encoding="utf-8")
    rows, errors = read_product_rows(csv_path)
    import_rows(db, str(csv_path), rows, errors)

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def get_product(session: Session) -> Product:
    product = session.scalar(select(Product).where(Product.product_group == "jeans-sync"))
    assert product is not None
    return product


def approve_product(session: Session) -> Product:
    product = get_product(session)
    product.status = "approved"
    session.commit()
    session.refresh(product)
    return product


def approve_first_product_image(session: Session, product: Product) -> ProductImage:
    image = product.images[0]
    image.status = "approved"
    image.image_type = "product"
    image.is_main = True
    session.commit()
    session.refresh(image)
    return image


def test_approved_product_can_sync_in_mock_mode(
    client: TestClient, session: Session
) -> None:
    product = approve_product(session)

    response = client.post(f"/products/{product.id}/sync")

    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == product.id
    assert body["status"] == "success"
    assert body["mock_mode"] is True
    assert body["external_product_id"] == f"mock_line_product_{product.id}"
    assert body["variants_synced"] == 2
    assert body["warnings"] == ["product has no approved storefront images"]


def test_draft_product_cannot_sync(client: TestClient, session: Session) -> None:
    product = get_product(session)

    response = client.post(f"/products/{product.id}/sync")

    assert response.status_code == 409
    assert response.json()["detail"] == "Only approved products can sync"


def test_rejected_product_cannot_sync(client: TestClient, session: Session) -> None:
    product = get_product(session)
    product.status = "rejected"
    session.commit()

    response = client.post(f"/products/{product.id}/sync")

    assert response.status_code == 409
    assert response.json()["detail"] == "Only approved products can sync"


def test_archived_product_cannot_sync(client: TestClient, session: Session) -> None:
    product = get_product(session)
    product.status = "archived"
    session.commit()

    response = client.post(f"/products/{product.id}/sync")

    assert response.status_code == 409
    assert response.json()["detail"] == "Only approved products can sync"


def test_sync_creates_channel_mappings_api_logs_and_sync_jobs(
    client: TestClient, session: Session
) -> None:
    product = approve_product(session)

    response = client.post(f"/products/{product.id}/sync")

    assert response.status_code == 200
    sync_job_id = response.json()["sync_job_id"]
    channel_product = session.scalar(select(ChannelProduct))
    assert channel_product is not None
    assert channel_product.external_product_id == f"mock_line_product_{product.id}"
    assert channel_product.sync_status == "success"

    channel_variants = session.scalars(select(ChannelVariant)).all()
    assert len(channel_variants) == 2
    assert {variant.sync_status for variant in channel_variants} == {"success"}
    assert {
        variant.external_variant_id for variant in channel_variants
    } == {
        f"mock_line_variant_{variant.variant_id}" for variant in channel_variants
    }

    api_logs = session.scalars(
        select(ApiLog).where(ApiLog.service == "line_myshop_mock")
    ).all()
    assert len(api_logs) == 5
    assert {log.method for log in api_logs} == {"POST", "PUT"}

    sync_job = session.get(SyncJob, sync_job_id)
    assert sync_job is not None
    assert sync_job.status == "success"
    assert sync_job.error_message is None


def test_product_summary_includes_channel_mapping_after_sync(
    client: TestClient, session: Session
) -> None:
    product = approve_product(session)

    assert client.post(f"/products/{product.id}/sync").status_code == 200
    response = client.get("/products")

    assert response.status_code == 200
    product_body = response.json()[0]
    assert product_body["external_product_id"] == f"mock_line_product_{product.id}"
    assert product_body["sync_status"] == "success"
    assert product_body["last_synced_at"] is not None


def test_refresh_line_status_updates_channel_product(
    client: TestClient, session: Session
) -> None:
    product = approve_product(session)
    assert client.post(f"/products/{product.id}/sync").status_code == 200

    response = client.post(f"/products/{product.id}/line-status/refresh")

    assert response.status_code == 200
    assert response.json()["is_display"] is False
    channel_product = session.scalar(select(ChannelProduct))
    assert channel_product is not None
    assert channel_product.is_display is False
    assert channel_product.last_refreshed_at is not None
    assert channel_product.line_payload["id"] == f"mock_line_product_{product.id}"


def test_publish_product_updates_visibility_and_creates_sync_job(
    client: TestClient, session: Session
) -> None:
    product = approve_product(session)
    assert client.post(f"/products/{product.id}/sync").status_code == 200

    response = client.post(f"/products/{product.id}/publish")

    assert response.status_code == 200
    body = response.json()
    assert body["is_display"] is True
    channel_product = session.scalar(select(ChannelProduct))
    assert channel_product is not None
    assert channel_product.is_display is True
    sync_job = session.get(SyncJob, body["sync_job_id"])
    assert sync_job is not None
    assert sync_job.job_type == "product_publish"
    assert sync_job.status == "success"


def test_hide_product_updates_visibility(
    client: TestClient, session: Session
) -> None:
    product = approve_product(session)
    assert client.post(f"/products/{product.id}/sync").status_code == 200
    assert client.post(f"/products/{product.id}/publish").status_code == 200

    response = client.post(
        f"/products/{product.id}/hide",
        json={"reason": "พักการขายชั่วคราว"},
    )

    assert response.status_code == 200
    assert response.json()["is_display"] is False
    channel_product = session.scalar(select(ChannelProduct))
    assert channel_product is not None
    assert channel_product.is_display is False


def test_publish_requires_synced_product(client: TestClient, session: Session) -> None:
    product = approve_product(session)

    response = client.post(f"/products/{product.id}/publish")

    assert response.status_code == 409
    assert response.json()["detail"] == "Product must be synced to LINE MyShop before this action"


def test_list_and_get_sync_jobs(client: TestClient, session: Session) -> None:
    product = approve_product(session)
    sync_response = client.post(f"/products/{product.id}/sync")
    sync_job_id = sync_response.json()["sync_job_id"]

    list_response = client.get("/sync-jobs")
    detail_response = client.get(f"/sync-jobs/{sync_job_id}")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == sync_job_id
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "success"


def test_sync_readiness_reports_mock_warning_for_missing_images(
    client: TestClient, session: Session
) -> None:
    product = approve_product(session)

    response = client.get(f"/products/{product.id}/sync-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["mock_mode"] is True
    assert body["errors"] == []
    assert body["warnings"] == ["product has no approved storefront images"]


def test_sync_preview_returns_internal_and_outbound_payload(
    client: TestClient, session: Session
) -> None:
    product = approve_product(session)

    response = client.post(f"/products/{product.id}/sync/preview")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["action"] == "create"
    assert body["endpoint"] == "/mock/products"
    assert body["method"] == "POST"
    assert body["internal_payload"]["product_id"] == product.id
    assert body["outbound_payload"] == body["internal_payload"]


def test_real_mode_requires_api_configuration(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = approve_product(session)
    monkeypatch.setenv("LINE_MYSHOP_MOCK_MODE", "false")
    monkeypatch.setenv("LINE_MYSHOP_BASE_URL", "")
    monkeypatch.setenv("LINE_MYSHOP_API_KEY", "")
    get_settings.cache_clear()

    response = client.post(
        f"/products/{product.id}/sync",
        json={"confirm": "CONFIRM PRODUCTION SYNC"},
    )

    assert response.status_code == 409
    assert "LINE_MYSHOP_BASE_URL is required" in response.json()["detail"]["errors"]
    assert session.scalar(select(SyncJob)) is None
    get_settings.cache_clear()


def test_real_mode_rejects_placeholder_api_base_url(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = approve_product(session)
    monkeypatch.setenv("LINE_MYSHOP_MOCK_MODE", "false")
    monkeypatch.setenv(
        "LINE_MYSHOP_BASE_URL", "https://your-line-myshop-api-base-url"
    )
    monkeypatch.setenv("LINE_MYSHOP_API_KEY", "test-key")
    get_settings.cache_clear()

    response = client.post(
        f"/products/{product.id}/sync",
        json={"confirm": "CONFIRM PRODUCTION SYNC"},
    )

    assert response.status_code == 409
    assert (
        "LINE_MYSHOP_BASE_URL must be a real LINE MyShop API base URL"
        in response.json()["detail"]["errors"]
    )
    assert session.scalar(select(SyncJob)) is None
    get_settings.cache_clear()


def test_real_mode_sync_uses_external_ids_from_client_response(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product = approve_product(session)
    approve_first_product_image(session, product)
    monkeypatch.setenv("LINE_MYSHOP_MOCK_MODE", "false")
    monkeypatch.setenv("LINE_MYSHOP_BASE_URL", "https://line.example.test")
    monkeypatch.setenv("LINE_MYSHOP_API_KEY", "test-key")
    monkeypatch.setenv("LINE_MYSHOP_DEFAULT_CATEGORY_ID", "123")
    get_settings.cache_clear()

    class FakeRealClient:
        def create_product(self, payload: dict) -> dict:
            return {
                "external_product_id": f"real_product_{payload['product_id']}",
                "variants": [
                    {
                        "variant_id": variant["id"],
                        "external_variant_id": f"real_variant_{variant['id']}",
                    }
                    for variant in payload["variants"]
                ],
            }

        def update_product(self, external_product_id: str, payload: dict) -> dict:
            return {"external_product_id": external_product_id}

        def update_inventory(self, external_variant_id: str, stock: int) -> dict:
            return {"external_variant_id": external_variant_id, "stock": stock}

        def update_price(
            self, external_variant_id: str, price, sale_price=None
        ) -> dict:
            return {"external_variant_id": external_variant_id}

    monkeypatch.setattr(
        sync_api,
        "create_line_myshop_client",
        lambda db, settings: FakeRealClient(),
    )

    response = client.post(
        f"/products/{product.id}/sync",
        json={"confirm": "CONFIRM PRODUCTION SYNC"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mock_mode"] is False
    assert body["message"] == "LINE MyShop sync completed"
    assert body["external_product_id"] == f"real_product_{product.id}"

    channel_product = session.scalar(select(ChannelProduct))
    assert channel_product is not None
    assert channel_product.external_product_id == f"real_product_{product.id}"
    assert {
        variant.external_variant_id
        for variant in session.scalars(select(ChannelVariant)).all()
    } == {
        f"real_variant_{variant.variant_id}"
        for variant in session.scalars(select(ChannelVariant)).all()
    }
    get_settings.cache_clear()


def test_real_mode_sync_requires_confirmation(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = approve_product(session)
    approve_first_product_image(session, product)
    monkeypatch.setenv("LINE_MYSHOP_MOCK_MODE", "false")
    monkeypatch.setenv("LINE_MYSHOP_BASE_URL", "https://line.example.test")
    monkeypatch.setenv("LINE_MYSHOP_API_KEY", "test-key")
    monkeypatch.setenv("LINE_MYSHOP_DEFAULT_CATEGORY_ID", "123")
    get_settings.cache_clear()

    response = client.post(f"/products/{product.id}/sync")

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Production sync requires confirm='CONFIRM PRODUCTION SYNC'"
    )
    assert session.scalar(select(SyncJob)) is None
    get_settings.cache_clear()


def test_real_mode_readiness_requires_approved_product_image(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = approve_product(session)
    monkeypatch.setenv("LINE_MYSHOP_MOCK_MODE", "false")
    monkeypatch.setenv("LINE_MYSHOP_BASE_URL", "https://line.example.test")
    monkeypatch.setenv("LINE_MYSHOP_API_KEY", "test-key")
    monkeypatch.setenv("LINE_MYSHOP_DEFAULT_CATEGORY_ID", "123")
    get_settings.cache_clear()

    response = client.get(f"/products/{product.id}/sync-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert body["errors"] == ["product must have at least one approved product image"]
    get_settings.cache_clear()


def test_real_mode_preview_returns_oaplus_payload(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    product = approve_product(session)
    approve_first_product_image(session, product)
    monkeypatch.setenv("LINE_MYSHOP_MOCK_MODE", "false")
    monkeypatch.setenv("LINE_MYSHOP_BASE_URL", "https://line.example.test")
    monkeypatch.setenv("LINE_MYSHOP_API_KEY", "test-key")
    monkeypatch.setenv("LINE_MYSHOP_DEFAULT_CATEGORY_ID", "123")
    monkeypatch.setenv("LINE_MYSHOP_DEFAULT_BRAND", "ImWalk")
    get_settings.cache_clear()

    response = client.post(f"/products/{product.id}/sync/preview")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["mock_mode"] is False
    assert body["endpoint"] == "/myshop/v1/products"
    assert body["outbound_payload"]["categoryId"] == 123
    assert body["outbound_payload"]["brand"] == "ImWalk"
    assert body["outbound_payload"]["imageUrls"] == ["https://example.com/sync-1.jpg"]
    get_settings.cache_clear()


def test_real_client_posts_with_x_api_key_and_oaplus_payload(
    session: Session,
) -> None:
    captured_headers: list[str] = []
    captured_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(request.headers["X-API-KEY"])
        captured_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "line_product_1",
                    "variants": [
                        {
                            "id": "line_variant_1",
                            "sku": "SKU-1",
                        }
                    ],
                },
            },
        )

    import json

    settings = Settings(
        line_myshop_mock_mode=False,
        line_myshop_base_url="https://line.example.test",
        line_myshop_api_key="secret-key",
        line_myshop_default_category_id=123,
        line_myshop_default_brand="ImWalk",
    )
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    real_client = LineMyShopRealClient(session, settings, http_client=http_client)

    response = real_client.create_product(
        {
            "product_id": 1,
            "product_group": "product-code-1",
            "name": "กางเกงยีนส์",
            "color": "ยีนส์เข้ม",
            "category": "กางเกงยีนส์",
            "description": "รายละเอียด",
            "images": [{"url": "https://example.com/image.jpg"}],
            "variants": [
                {
                    "id": 1,
                    "sku": "SKU-1",
                    "barcode": "BARCODE-1",
                    "size": "M",
                    "price": "1750.00",
                    "sale_price": None,
                    "available_stock": 3,
                }
            ],
        }
    )
    session.flush()

    assert response["data"]["id"] == "line_product_1"
    assert captured_headers == ["secret-key"]
    assert captured_payloads == [
        {
            "brand": "ImWalk",
            "categoryId": 123,
            "code": "product-code-1",
            "description": "รายละเอียด",
            "imageUrls": ["https://example.com/image.jpg"],
            "instantDiscount": 0,
            "name": "กางเกงยีนส์",
            "variantOptions": {
                "option1": {
                    "name": "color",
                    "data": [
                        {
                            "value": "ยีนส์เข้ม",
                            "imageUrl": "https://example.com/image.jpg",
                        }
                    ],
                },
                "option2": {"name": "size", "data": [{"value": "M"}]},
            },
            "variants": [
                {
                    "barcode": "BARCODE-1",
                    "discountedPrice": 0,
                    "onHandNumber": 3,
                    "options": [0, 0],
                    "price": 1750,
                    "sku": "SKU-1",
                    "weight": 1,
                }
            ],
        }
    ]
    api_log = session.scalar(select(ApiLog).where(ApiLog.service == "line_myshop"))
    assert api_log is not None
    assert api_log.endpoint == "/myshop/v1/products"
    assert api_log.method == "POST"
    assert api_log.status_code == 200
    assert api_log.error_message is None


def test_real_client_updates_product_with_patch(
    session: Session,
) -> None:
    captured_methods: list[str] = []
    captured_paths: list[str] = []
    captured_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_methods.append(request.method)
        captured_paths.append(request.url.path)
        captured_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"data": {"id": "line_product_1"}})

    settings = Settings(
        line_myshop_mock_mode=False,
        line_myshop_base_url="https://line.example.test",
        line_myshop_api_key="secret-key",
        line_myshop_update_product_path="/myshop/v1/products/{external_product_id}",
        line_myshop_default_category_id=123,
        line_myshop_default_brand="CO COAT",
    )
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    real_client = LineMyShopRealClient(session, settings, http_client=http_client)

    response = real_client.update_product(
        "line_product_1",
        {
            "product_id": 1,
            "product_group": "product-code-1",
            "name": "กางเกงยีนส์",
            "color": "ยีนส์เข้ม",
            "category": "กางเกงยีนส์",
            "description": "รายละเอียด",
            "images": [{"url": "https://example.com/image.jpg"}],
            "variants": [
                {
                    "id": 1,
                    "sku": "SKU-1",
                    "barcode": "BARCODE-1",
                    "size": "M",
                    "price": "1750.00",
                    "sale_price": None,
                    "available_stock": 3,
                }
            ],
        },
    )

    assert response["data"]["id"] == "line_product_1"
    assert captured_methods == ["PATCH"]
    assert captured_paths == ["/myshop/v1/products/line_product_1"]
    assert captured_payloads[0]["brand"] == "CO COAT"
    assert "variantOptions" not in captured_payloads[0]
    assert "variants" not in captured_payloads[0]


def test_real_client_requires_category_id_for_oaplus_payload(
    session: Session,
) -> None:
    settings = Settings(
        line_myshop_mock_mode=False,
        line_myshop_base_url="https://line.example.test",
        line_myshop_api_key="secret-key",
        line_myshop_default_category_id=None,
    )
    real_client = LineMyShopRealClient(session, settings)

    with pytest.raises(Exception, match="LINE_MYSHOP_DEFAULT_CATEGORY_ID"):
        real_client.create_product(
            {
                "product_id": 1,
                "product_group": "product-code-1",
                "name": "กางเกงยีนส์",
                "color": "ยีนส์เข้ม",
                "category": "กางเกงยีนส์",
                "description": "รายละเอียด",
                "images": [{"url": "https://example.com/image.jpg"}],
                "variants": [
                    {
                        "id": 1,
                        "sku": "SKU-1",
                        "barcode": "BARCODE-1",
                        "size": "M",
                        "price": "1750.00",
                        "sale_price": None,
                        "available_stock": 3,
                    }
                ],
            }
        )
