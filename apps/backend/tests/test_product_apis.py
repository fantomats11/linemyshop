from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
import app.api.products as products_api
from app.commands.import_products import import_rows, read_product_rows
from app.core.config import get_settings
from app.db.base import Base
from app.main import app
from app.models import AuditLog, ImageGenerationJob, ImportBatch, ProductImage


CSV_CONTENT = """product_group,product_name,color,gender,category,price,sale_price,size,waist,hip,length,sku,barcode,stock,image_1,image_2,image_3,description,note,status
jeans-api,กางเกงยีนส์ API,ยีนส์เข้ม,หญิง,กางเกงยีนส์,1750,,M,26-28,34-36,40,API-M,,5,https://example.com/api-1.jpg,https://example.com/api-2.jpg,,รายละเอียด API,note API,draft
jeans-api,กางเกงยีนส์ API,ยีนส์เข้ม,หญิง,กางเกงยีนส์,1750,,L,28-30,36-38,40,API-L,API-L,3,https://example.com/api-1.jpg,https://example.com/api-2.jpg,,รายละเอียด API,note API,draft
"""


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


def test_list_products(client: TestClient) -> None:
    response = client.get("/products")

    assert response.status_code == 200
    products = response.json()
    assert len(products) == 1
    assert products[0]["product_group"] == "jeans-api"
    assert products[0]["status"] == "draft"
    assert products[0]["variant_count"] == 2
    assert products[0]["total_stock"] == 8
    assert products[0]["total_available_stock"] == 8
    assert products[0]["image_url"] is None


def test_get_product_detail(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]

    response = client.get(f"/products/{product_id}")

    assert response.status_code == 200
    product = response.json()
    assert product["product_group"] == "jeans-api"
    assert product["description"] == "รายละเอียด API"
    assert len(product["images"]) == 2
    assert product["images"][0]["status"] == "draft"
    assert product["images"][0]["image_type"] == "product"
    assert product["images"][0]["is_main"] is False
    assert len(product["variants"]) == 2
    assert product["variants"][0]["inventory"]["stock_on_hand"] in {3, 5}
    assert product["variants"][0]["measurements"] == [
        {"label": "เอว", "value": product["variants"][0]["waist"]},
        {"label": "สะโพก", "value": product["variants"][0]["hip"]},
        {"label": "ความยาว", "value": product["variants"][0]["length"]},
    ]


def test_create_product_from_frontend_intake(client: TestClient) -> None:
    response = client.post(
        "/products",
        json={
            "product_group": "jeans-intake",
            "name": "กางเกงยีนส์ Intake",
            "color": "ยีนส์เข้ม",
            "gender": "หญิง",
            "category": "กางเกงยีนส์",
            "description": "ข้อมูลจากฟอร์ม",
            "note": "รอตรวจรูป",
            "variants": [
                {
                    "sku": "INTAKE-M",
                    "size": "M",
                    "waist": "26-28",
                    "hip": "34-36",
                    "length": "40",
                    "measurements": [
                        {"label": "เอว", "value": "26-28"},
                        {"label": "สะโพก", "value": "34-36"},
                        {"label": "ความยาว", "value": "40"},
                    ],
                    "price": "1750",
                    "stock_on_hand": 3,
                }
            ],
        },
    )

    assert response.status_code == 200
    product = response.json()
    assert product["product_group"] == "jeans-intake"
    assert product["status"] == "draft"
    assert product["variants"][0]["sku"] == "INTAKE-M"
    assert product["variants"][0]["measurements"] == [
        {"label": "เอว", "value": "26-28"},
        {"label": "สะโพก", "value": "34-36"},
        {"label": "ความยาว", "value": "40"},
    ]
    assert product["variants"][0]["inventory"]["stock_on_hand"] == 3


def test_create_product_accepts_dynamic_measurements(client: TestClient) -> None:
    response = client.post(
        "/products",
        json={
            "product_group": "knit-intake",
            "name": "เสื้อไหมพรม Intake",
            "color": "ครีม",
            "gender": "หญิง",
            "category": "แฟชั่นผู้หญิง>เสื้อ",
            "variants": [
                {
                    "sku": "KNIT-M",
                    "size": "M",
                    "measurements": [
                        {"label": "รอบอก", "value": "36-38"},
                        {"label": "ไหล่", "value": "15"},
                        {"label": "ความยาว", "value": "23"},
                    ],
                    "price": "1290",
                    "stock_on_hand": 3,
                }
            ],
        },
    )

    assert response.status_code == 200
    product = response.json()
    variant = product["variants"][0]
    assert variant["measurements"] == [
        {"label": "รอบอก", "value": "36-38"},
        {"label": "ไหล่", "value": "15"},
        {"label": "ความยาว", "value": "23"},
    ]
    assert variant["waist"] == "36-38"
    assert variant["hip"] == "15"
    assert variant["length"] == "23"


def test_approve_product_creates_audit_log(
    client: TestClient, session: Session
) -> None:
    product_id = client.get("/products").json()[0]["id"]

    response = client.post(f"/products/{product_id}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    audit_log = session.scalar(
        select(AuditLog).where(AuditLog.action == "product.approve")
    )
    assert audit_log is not None
    assert audit_log.target_id == product_id
    assert audit_log.before_payload == {"status": "draft"}
    assert audit_log.after_payload == {"status": "approved"}


def test_approve_product_rejects_non_draft(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]
    assert client.post(f"/products/{product_id}/approve").status_code == 200

    response = client.post(f"/products/{product_id}/approve")

    assert response.status_code == 409
    assert response.json()["detail"] == "Only draft products can be approved"


def test_reject_product_creates_audit_log(
    client: TestClient, session: Session
) -> None:
    product_id = client.get("/products").json()[0]["id"]

    response = client.post(
        f"/products/{product_id}/reject",
        json={"reason": "ภาพสินค้าไม่ครบ"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    audit_log = session.scalar(
        select(AuditLog).where(AuditLog.action == "product.reject")
    )
    assert audit_log is not None
    assert audit_log.after_payload == {
        "status": "rejected",
        "reason": "ภาพสินค้าไม่ครบ",
    }


def test_archive_draft_product_creates_audit_log(
    client: TestClient, session: Session
) -> None:
    product_id = client.get("/products").json()[0]["id"]

    response = client.post(
        f"/products/{product_id}/archive",
        json={"reason": "sample/test data from initial CSV"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "archived"
    audit_log = session.scalar(
        select(AuditLog).where(AuditLog.action == "product.archive")
    )
    assert audit_log is not None
    assert audit_log.before_payload == {"status": "draft"}
    assert audit_log.after_payload == {
        "status": "archived",
        "reason": "sample/test data from initial CSV",
    }


def test_archive_rejected_product(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]
    assert client.post(
        f"/products/{product_id}/reject",
        json={"reason": "ข้อมูลไม่พร้อม"},
    ).status_code == 200

    response = client.post(f"/products/{product_id}/archive", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_archived_product_excluded_from_list_by_default(
    client: TestClient,
) -> None:
    product_id = client.get("/products").json()[0]["id"]
    assert client.post(f"/products/{product_id}/archive", json={}).status_code == 200

    response = client.get("/products")

    assert response.status_code == 200
    assert response.json() == []


def test_include_archived_shows_archived_product(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]
    assert client.post(f"/products/{product_id}/archive", json={}).status_code == 200

    response = client.get("/products?include_archived=true")

    assert response.status_code == 200
    products = response.json()
    assert len(products) == 1
    assert products[0]["id"] == product_id
    assert products[0]["status"] == "archived"


def test_archived_product_detail_still_works(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]
    assert client.post(f"/products/{product_id}/archive", json={}).status_code == 200

    response = client.get(f"/products/{product_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_archived_product_cannot_approve(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]
    assert client.post(f"/products/{product_id}/archive", json={}).status_code == 200

    response = client.post(f"/products/{product_id}/approve")

    assert response.status_code == 409
    assert response.json()["detail"] == "Only draft products can be approved"


def test_add_image_url(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]

    response = client.post(
        f"/products/{product_id}/images",
        json={
            "url": "https://example.com/new-product-image.jpg",
            "image_type": "product",
            "position": 1,
        },
    )

    assert response.status_code == 200
    image = response.json()
    assert image["url"] == "https://example.com/new-product-image.jpg"
    assert image["image_type"] == "product"
    assert image["status"] == "draft"
    assert image["is_main"] is False


def test_upload_reference_images_creates_brief_images(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    product_id = client.get("/products").json()[0]["id"]
    image_path = tmp_path / "reference.jpg"
    image_path.write_bytes(b"fake image bytes")

    class FakeWordPressMediaClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def upload_media(self, file_path: Path) -> dict:
            return {"source_url": f"https://cdn.example.test/{file_path.name}"}

    monkeypatch.setattr(products_api, "WordPressMediaClient", FakeWordPressMediaClient)

    with image_path.open("rb") as image_file:
        response = client.post(
            f"/products/{product_id}/reference-images",
            files={"files": ("reference.jpg", image_file, "image/jpeg")},
        )

    assert response.status_code == 200
    images = response.json()
    assert len(images) == 1
    assert images[0]["image_type"] == "brief"
    assert images[0]["status"] == "draft"
    assert images[0]["url"].startswith("https://cdn.example.test/")


def test_image_generation_brief_returns_standard_slots(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]

    response = client.get(f"/products/{product_id}/image-generation-brief")

    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == product_id
    assert body["ready"] is True
    assert len(body["slots"]) == 7
    assert body["slots"][0]["image_type"] == "product"
    assert body["slots"][4]["image_type"] == "size_chart"


def test_image_generation_brief_uses_top_garment_prompt(client: TestClient) -> None:
    response = client.post(
        "/products",
        json={
            "product_group": "knit-prompt",
            "name": "เสื้อไหมพรมคอเต่า",
            "color": "ครีม",
            "gender": "หญิง",
            "category": "แฟชั่นผู้หญิง>เสื้อ",
            "variants": [
                {
                    "sku": "KNIT-M",
                    "size": "M",
                    "measurements": [
                        {"label": "รอบอก", "value": "36-38"},
                        {"label": "ไหล่", "value": "14"},
                        {"label": "ความยาว", "value": "23"},
                    ],
                    "price": "1290",
                    "stock_on_hand": 3,
                }
            ],
        },
    )
    product_id = response.json()["id"]

    brief = client.get(f"/products/{product_id}/image-generation-brief").json()
    prompt_text = " ".join(slot["prompt"] for slot in brief["slots"])

    assert "upper-body" in prompt_text
    assert "knit texture" in prompt_text
    assert "jeans" not in prompt_text
    assert "denim" not in prompt_text
    assert "waist-down" not in prompt_text


def test_create_image_generation_job(client: TestClient, session: Session) -> None:
    product_id = client.get("/products").json()[0]["id"]

    response = client.post(f"/products/{product_id}/image-generation-jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == product_id
    assert body["status"] == "waiting_for_generated_images"
    assert len(body["prompt_payload"]["slots"]) == 7
    job = session.get(ImageGenerationJob, body["id"])
    assert job is not None
    assert job.mode == "manual_or_agent_imagegen"


def test_run_image_generation_job_creates_draft_images(
    client: TestClient,
    session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product_id = client.get("/products").json()[0]["id"]
    reference_path = tmp_path / "reference.jpg"
    reference_path.write_bytes(b"fake reference")

    class FakeFalImageGenerationClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def generate_image(self, **_kwargs) -> list[dict]:
            assert all(
                url.startswith("https://cdn.example.test/")
                for url in _kwargs["reference_urls"]
            )
            return [{"url": "https://fal.example.test/generated.jpg"}]

        def download_image(self, _url: str, destination: Path) -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"fake generated image")

    class FakeWordPressMediaClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def upload_media(self, file_path: Path) -> dict:
            return {"source_url": f"https://cdn.example.test/{file_path.name}"}

    monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "fal")
    monkeypatch.setenv("FAL_KEY", "test-fal-key")
    get_settings.cache_clear()
    monkeypatch.setattr(products_api, "FalImageGenerationClient", FakeFalImageGenerationClient)
    monkeypatch.setattr(products_api, "WordPressMediaClient", FakeWordPressMediaClient)
    with reference_path.open("rb") as reference_file:
        assert client.post(
            f"/products/{product_id}/reference-images",
            files={"files": ("reference.jpg", reference_file, "image/jpeg")},
        ).status_code == 200
    session.add(
        ProductImage(
            product_id=product_id,
            url="data/input/product-references/product-1/missing-reference.jpg",
            position=99,
            status="draft",
            image_type="brief",
            is_main=False,
        )
    )
    session.commit()
    job_id = client.post(f"/products/{product_id}/image-generation-jobs").json()["id"]

    response = client.post(
        f"/image-generation-jobs/{job_id}/run",
        json={"slot_positions": [1, 2]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["result_payload"]["provider"] == "fal"
    assert len(body["result_payload"]["images"]) == 2
    images = session.scalars(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .where(ProductImage.url.like("https://cdn.example.test/%"))
        .where(ProductImage.image_type.in_(["product", "detail"]))
    ).all()
    assert len(images) == 2
    assert {image.status for image in images} == {"draft"}
    assert {image.image_type for image in images} == {"product", "detail"}
    get_settings.cache_clear()


def test_approve_product_image_creates_audit_log(
    client: TestClient, session: Session
) -> None:
    product_id = client.get("/products").json()[0]["id"]
    image_id = client.post(
        f"/products/{product_id}/images",
        json={
            "url": "https://example.com/approve-me.jpg",
            "image_type": "product",
            "position": 1,
        },
    ).json()["id"]

    response = client.post(
        f"/product-images/{image_id}/approve",
        json={"review_note": "ผ่านการตรวจแล้ว"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    audit_log = session.scalar(
        select(AuditLog).where(AuditLog.action == "product_image.approve")
    )
    assert audit_log is not None
    assert audit_log.after_payload == {
        "status": "approved",
        "image_type": "product",
        "review_note": "ผ่านการตรวจแล้ว",
    }


def test_reject_product_image_creates_audit_log(
    client: TestClient, session: Session
) -> None:
    product_id = client.get("/products").json()[0]["id"]
    image_id = client.post(
        f"/products/{product_id}/images",
        json={
            "url": "https://example.com/reject-me.jpg",
            "image_type": "product",
            "position": 1,
        },
    ).json()["id"]

    response = client.post(
        f"/product-images/{image_id}/reject",
        json={"review_note": "รูปไม่ชัด"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    audit_log = session.scalar(
        select(AuditLog).where(AuditLog.action == "product_image.reject")
    )
    assert audit_log is not None
    assert audit_log.after_payload == {
        "status": "rejected",
        "image_type": "product",
        "review_note": "รูปไม่ชัด",
    }


def test_promote_reference_image_uploads_and_sets_main(
    client: TestClient,
    session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product_id = client.get("/products").json()[0]["id"]
    image_path = tmp_path / "reference.jpg"
    image_path.write_bytes(b"fake image bytes")

    class FakeWordPressMediaClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def upload_media(self, file_path: Path) -> dict:
            return {"source_url": f"https://cdn.example.test/{file_path.name}"}

    monkeypatch.setattr(products_api, "WordPressMediaClient", FakeWordPressMediaClient)
    with image_path.open("rb") as image_file:
        reference_image = client.post(
            f"/products/{product_id}/reference-images",
            files={"files": ("reference.jpg", image_file, "image/jpeg")},
        ).json()[0]

    response = client.post(f"/product-images/{reference_image['id']}/promote-reference")

    assert response.status_code == 200
    body = response.json()
    assert body["image_type"] == "product"
    assert body["status"] == "approved"
    assert body["is_main"] is True
    assert body["url"].startswith("https://cdn.example.test/")
    product_images = session.scalars(
        select(ProductImage).where(ProductImage.product_id == product_id)
    ).all()
    assert any(image.image_type == "brief" for image in product_images)
    assert any(image.image_type == "product" and image.is_main for image in product_images)


def test_set_approved_image_as_main(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]
    image_id = client.post(
        f"/products/{product_id}/images",
        json={
            "url": "https://example.com/main-product.jpg",
            "image_type": "product",
            "position": 1,
        },
    ).json()["id"]
    assert client.post(f"/product-images/{image_id}/approve", json={}).status_code == 200

    response = client.post(f"/product-images/{image_id}/set-main")

    assert response.status_code == 200
    assert response.json()["is_main"] is True
    products = client.get("/products").json()
    assert products[0]["image_url"] == "https://example.com/main-product.jpg"


def test_cannot_approve_brief_image(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]
    image_id = client.post(
        f"/products/{product_id}/images",
        json={
            "url": "data/input/images/brief.jpg",
            "image_type": "brief",
            "position": 1,
        },
    ).json()["id"]

    response = client.post(f"/product-images/{image_id}/approve", json={})

    assert response.status_code == 409
    assert response.json()["detail"] == "Brief images cannot be approved as product images"


def test_cannot_set_rejected_image_as_main(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]
    image_id = client.post(
        f"/products/{product_id}/images",
        json={
            "url": "https://example.com/rejected-main.jpg",
            "image_type": "product",
            "position": 1,
        },
    ).json()["id"]
    assert client.post(f"/product-images/{image_id}/reject", json={}).status_code == 200

    response = client.post(f"/product-images/{image_id}/set-main")

    assert response.status_code == 409
    assert response.json()["detail"] == "Only approved images can be set as main"


def test_product_list_excludes_brief_image_from_image_url(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]
    assert client.post(
        f"/products/{product_id}/images",
        json={
            "url": "data/input/images/brief.jpg",
            "image_type": "brief",
            "position": 1,
        },
    ).status_code == 200

    products = client.get("/products").json()

    assert products[0]["image_url"] is None


def test_get_image_set_requires_approved_main_product_image(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]
    image_id = client.post(
        f"/products/{product_id}/images",
        json={
            "url": "https://example.com/detail.jpg",
            "image_type": "detail",
            "position": 2,
        },
    ).json()["id"]
    assert client.post(f"/product-images/{image_id}/approve", json={}).status_code == 200

    response = client.get(f"/products/{product_id}/image-set")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert body["max_images"] == 7
    assert body["errors"] == ["product must have one approved main product image"]
    assert body["images"][0]["image_type"] == "detail"


def test_bulk_create_product_images(client: TestClient) -> None:
    product_id = client.get("/products").json()[0]["id"]

    response = client.post(
        f"/products/{product_id}/images/bulk",
        json={
            "images": [
                {
                    "url": "https://example.com/hero.jpg",
                    "image_type": "product",
                    "position": 1,
                },
                {
                    "url": "https://example.com/detail.jpg",
                    "image_type": "detail",
                    "position": 2,
                },
            ]
        },
    )

    assert response.status_code == 200
    images = response.json()
    assert len(images) == 2
    assert [image["position"] for image in images] == [1, 2]
    assert {image["status"] for image in images} == {"draft"}


def test_reorder_product_images_and_set_main(
    client: TestClient, session: Session
) -> None:
    product_id = client.get("/products").json()[0]["id"]
    image_1 = client.post(
        f"/products/{product_id}/images",
        json={
            "url": "https://example.com/hero.jpg",
            "image_type": "product",
            "position": 2,
        },
    ).json()["id"]
    image_2 = client.post(
        f"/products/{product_id}/images",
        json={
            "url": "https://example.com/detail.jpg",
            "image_type": "detail",
            "position": 1,
        },
    ).json()["id"]
    assert client.post(f"/product-images/{image_1}/approve", json={}).status_code == 200
    assert client.post(f"/product-images/{image_2}/approve", json={}).status_code == 200

    response = client.post(
        f"/products/{product_id}/images/reorder",
        json={
            "images": [
                {"image_id": image_1, "position": 1, "is_main": True},
                {"image_id": image_2, "position": 2, "is_main": False},
            ]
        },
    )

    assert response.status_code == 200
    images = response.json()
    reordered = {image["id"]: image for image in images}
    assert reordered[image_1]["position"] == 1
    assert reordered[image_1]["is_main"] is True
    assert reordered[image_2]["position"] == 2
    audit_log = session.scalar(
        select(AuditLog).where(AuditLog.action == "product_image.reorder")
    )
    assert audit_log is not None


def test_cannot_create_storefront_image_outside_line_position_range(
    client: TestClient,
) -> None:
    product_id = client.get("/products").json()[0]["id"]

    response = client.post(
        f"/products/{product_id}/images",
        json={
            "url": "https://example.com/too-far.jpg",
            "image_type": "product",
            "position": 8,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "position must be between 1 and 7 for storefront images"


def test_list_imports_and_errors(client: TestClient, session: Session) -> None:
    import_batch = session.scalar(select(ImportBatch))

    response = client.get("/imports")

    assert response.status_code == 200
    imports = response.json()
    assert len(imports) == 1
    assert imports[0]["total_rows"] == 2

    errors_response = client.get(f"/imports/{import_batch.id}/errors")

    assert errors_response.status_code == 200
    assert errors_response.json() == []
