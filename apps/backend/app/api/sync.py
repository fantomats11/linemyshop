from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.core.config import get_settings
from app.models import (
    AuditLog,
    ChannelProduct,
    ChannelVariant,
    InventoryBalance,
    Product,
    ProductImage,
    ProductVariant,
    SyncJob,
)
from app.schemas.sync import (
    ProductLineStatusResponse,
    ProductLineVisibilityRequest,
    ProductSyncPreviewResponse,
    ProductSyncReadinessResponse,
    ProductSyncRequest,
    ProductSyncResponse,
    SyncJobResponse,
)
from app.schemas.products import LINE_STOREFRONT_MAX_IMAGES
from app.services.line_myshop_client import create_line_myshop_client


router = APIRouter(tags=["sync"])
CHANNEL = "line_myshop"
MOCK_CHANNEL = "line_myshop_mock"
PRODUCTION_SYNC_CONFIRMATION = "CONFIRM PRODUCTION SYNC"
PRODUCTION_PUBLISH_CONFIRMATION = "CONFIRM PUBLISH"
PRODUCTION_HIDE_CONFIRMATION = "CONFIRM HIDE"
DEFAULT_MEASUREMENT_LABELS = ("เอว", "สะโพก", "ความยาว")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def decimal_to_string(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def normalize_measurements(measurements: list[dict] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for measurement in measurements or []:
        label = str(measurement.get("label", "")).strip()
        value = str(measurement.get("value", "")).strip()
        if label and value:
            normalized.append({"label": label, "value": value})
    return normalized


def variant_measurements(variant: ProductVariant) -> list[dict[str, str]]:
    return normalize_measurements(variant.measurements) or [
        {"label": label, "value": value}
        for label, value in zip(
            DEFAULT_MEASUREMENT_LABELS,
            [variant.waist, variant.hip, variant.length],
        )
        if value
    ]


def build_product_payload(product: Product) -> dict[str, Any]:
    images = sorted(
        [
            image
            for image in product.images
            if image.status == "approved" and image.image_type != "brief"
        ],
        key=lambda image: (not image.is_main, image.position, image.id),
    )
    variants = sorted(product.variants, key=lambda variant: variant.id)
    return {
        "product_id": product.id,
        "product_group": product.product_group,
        "name": product.name,
        "color": product.color,
        "gender": product.gender,
        "category": product.category,
        "description": product.description,
        "note": product.note,
        "images": [
            {
                "id": image.id,
                "url": image.url,
                "position": image.position,
                "image_type": image.image_type,
                "is_main": image.is_main,
            }
            for image in images
        ],
        "variants": [
            {
                "id": variant.id,
                "sku": variant.sku,
                "barcode": variant.barcode,
                "size": variant.size,
                "waist": variant.waist,
                "hip": variant.hip,
                "length": variant.length,
                "measurements": variant_measurements(variant),
                "price": decimal_to_string(variant.price),
                "sale_price": decimal_to_string(variant.sale_price),
                "available_stock": (
                    variant.inventory_balance.available_stock
                    if variant.inventory_balance
                    else 0
                ),
            }
            for variant in variants
        ],
    }


def get_product_for_sync(session: Session, product_id: int) -> Product:
    product = session.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory_balance),
        )
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def get_or_create_channel_product(
    session: Session,
    product: Product,
    external_product_id: str,
    synced_at: datetime,
    channel: str,
) -> ChannelProduct:
    channel_product = session.scalar(
        select(ChannelProduct).where(
            ChannelProduct.product_id == product.id,
            ChannelProduct.channel == channel,
        )
    )
    if channel_product is None:
        channel_product = ChannelProduct(product_id=product.id, channel=channel)
        session.add(channel_product)

    channel_product.external_product_id = external_product_id
    channel_product.sync_status = "success"
    channel_product.last_synced_at = synced_at
    return channel_product


def update_channel_product_line_metadata(
    channel_product: ChannelProduct,
    line_payload: dict[str, Any],
    refreshed_at: datetime,
) -> None:
    channel_product.line_payload = line_payload
    channel_product.last_refreshed_at = refreshed_at
    is_display = extract_is_display(line_payload)
    if is_display is not None:
        channel_product.is_display = is_display


def get_or_create_channel_variant(
    session: Session,
    variant: ProductVariant,
    external_variant_id: str,
    synced_at: datetime,
    channel: str,
) -> ChannelVariant:
    channel_variant = session.scalar(
        select(ChannelVariant).where(
            ChannelVariant.variant_id == variant.id,
            ChannelVariant.channel == channel,
        )
    )
    if channel_variant is None:
        channel_variant = ChannelVariant(variant_id=variant.id, channel=channel)
        session.add(channel_variant)

    channel_variant.external_variant_id = external_variant_id
    channel_variant.external_sku = variant.sku
    channel_variant.sync_status = "success"
    channel_variant.last_synced_at = synced_at
    return channel_variant


def extract_external_product_id(response: dict[str, Any]) -> str:
    response_data = response.get("data") if isinstance(response.get("data"), dict) else {}
    external_product_id = (
        response.get("external_product_id")
        or response.get("id")
        or response.get("product_id")
        or response_data.get("id")
        or response_data.get("productId")
    )
    if not external_product_id:
        raise ValueError("LINE MyShop response does not include external product id")
    return str(external_product_id)


def extract_is_display(response: dict[str, Any]) -> bool | None:
    response_data = response.get("data") if isinstance(response.get("data"), dict) else {}
    value = response.get("isDisplay", response_data.get("isDisplay"))
    if value is None:
        value = response.get("is_display", response_data.get("is_display"))
    if isinstance(value, bool):
        return value
    return None


def extract_variant_external_ids(
    response: dict[str, Any], product_variants: list[ProductVariant]
) -> dict[int, str]:
    response_data = response.get("data") if isinstance(response.get("data"), dict) else {}
    variants = response.get("variants") or response_data.get("variants")
    if not isinstance(variants, list):
        return {}

    external_ids: dict[int, str] = {}
    sku_to_variant_id = {variant.sku: variant.id for variant in product_variants}
    for item in variants:
        if not isinstance(item, dict):
            continue
        local_variant_id = item.get("variant_id") or item.get("local_variant_id")
        external_variant_id = (
            item.get("external_variant_id")
            or item.get("id")
            or item.get("line_variant_id")
        )
        if local_variant_id is None and item.get("sku") in sku_to_variant_id:
            local_variant_id = sku_to_variant_id[item["sku"]]
        if local_variant_id is None or external_variant_id is None:
            continue
        external_ids[int(local_variant_id)] = str(external_variant_id)
    return external_ids


def get_existing_channel_variant(
    session: Session, variant: ProductVariant, channel: str
) -> ChannelVariant | None:
    return session.scalar(
        select(ChannelVariant).where(
            ChannelVariant.variant_id == variant.id,
            ChannelVariant.channel == channel,
        )
    )


def get_approved_storefront_images(product: Product) -> list[ProductImage]:
    return [
        image
        for image in product.images
        if image.status == "approved" and image.image_type != "brief"
    ]


def is_public_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def evaluate_sync_readiness(product: Product) -> tuple[list[str], list[str]]:
    settings = get_settings()
    errors: list[str] = []
    warnings: list[str] = []

    if product.status != "approved":
        errors.append("product must be approved before sync")

    if not product.variants:
        errors.append("product must have at least one variant")

    for variant in product.variants:
        if not variant.sku:
            errors.append(f"variant {variant.id} must have sku")
        if variant.price is None or variant.price <= 0:
            errors.append(f"variant {variant.sku} must have price greater than 0")
        if variant.inventory_balance is None:
            errors.append(f"variant {variant.sku} must have inventory balance")
        elif variant.inventory_balance.available_stock < 0:
            errors.append(f"variant {variant.sku} must not have negative available stock")

    approved_storefront_images = get_approved_storefront_images(product)
    if not approved_storefront_images:
        if settings.line_myshop_mock_mode:
            warnings.append("product has no approved storefront images")
        else:
            errors.append("product must have at least one approved product image")
    if len(approved_storefront_images) > LINE_STOREFRONT_MAX_IMAGES:
        errors.append("LINE MyShop supports at most 7 storefront images")
    if approved_storefront_images and not any(
        image.image_type == "product" and image.is_main
        for image in approved_storefront_images
    ):
        if settings.line_myshop_mock_mode:
            warnings.append("product has no approved main product image")
        else:
            errors.append("product must have one approved main product image")

    for image in approved_storefront_images:
        if image.position < 1 or image.position > LINE_STOREFRONT_MAX_IMAGES:
            errors.append(f"image {image.id} position must be between 1 and 7")
        if not is_public_url(image.url):
            errors.append(f"image {image.id} must be a public http or https URL")
    if approved_storefront_images:
        warnings.append("LINE MyShop images should be 1:1 square, recommended 640x640")

    if not settings.line_myshop_mock_mode:
        if not settings.line_myshop_base_url:
            errors.append("LINE_MYSHOP_BASE_URL is required")
        elif "your-line-myshop-api-base-url" in settings.line_myshop_base_url:
            errors.append("LINE_MYSHOP_BASE_URL must be a real LINE MyShop API base URL")

        if not settings.line_myshop_api_key:
            errors.append("LINE_MYSHOP_API_KEY is required")

        if settings.line_myshop_default_category_id is None:
            errors.append(
                "LINE_MYSHOP_DEFAULT_CATEGORY_ID is required for real product sync"
            )

    return errors, warnings


def get_existing_channel_product(
    session: Session, product: Product, channel: str
) -> ChannelProduct | None:
    return session.scalar(
        select(ChannelProduct).where(
            ChannelProduct.product_id == product.id,
            ChannelProduct.channel == channel,
        )
    )


def get_sync_channel() -> str:
    settings = get_settings()
    return MOCK_CHANNEL if settings.line_myshop_mock_mode else CHANNEL


def get_channel_product_or_404(session: Session, product: Product) -> ChannelProduct:
    channel_product = get_existing_channel_product(session, product, get_sync_channel())
    if channel_product is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product must be synced to LINE MyShop before this action",
        )
    return channel_product


def create_sync_job(session: Session, job_type: str, product_id: int) -> SyncJob:
    sync_job = SyncJob(
        job_type=job_type,
        target_type="product",
        target_id=product_id,
        status="running",
        started_at=now_utc(),
    )
    session.add(sync_job)
    session.commit()
    session.refresh(sync_job)
    return sync_job


def get_sync_action(session: Session, product: Product) -> tuple[str, str, str]:
    settings = get_settings()
    if settings.line_myshop_mock_mode:
        return "create", "/mock/products", "POST"

    existing_mapping = get_existing_channel_product(session, product, get_sync_channel())
    if existing_mapping is None:
        return "create", settings.line_myshop_create_product_path, "POST"
    return (
        "update",
        settings.line_myshop_update_product_path.format(
            external_product_id=existing_mapping.external_product_id
        ),
        "PATCH",
    )


def build_outbound_payload_or_none(
    session: Session, product: Product, internal_payload: dict[str, Any]
) -> dict[str, Any] | None:
    settings = get_settings()
    errors, _warnings = evaluate_sync_readiness(product)
    if errors:
        return None
    client = create_line_myshop_client(session, settings)
    return client.build_outbound_product_payload(internal_payload)


@router.get(
    "/products/{product_id}/sync-readiness",
    response_model=ProductSyncReadinessResponse,
)
def get_product_sync_readiness(
    product_id: int, db: Session = Depends(get_db)
) -> ProductSyncReadinessResponse:
    settings = get_settings()
    product = get_product_for_sync(db, product_id)
    errors, warnings = evaluate_sync_readiness(product)
    return ProductSyncReadinessResponse(
        product_id=product.id,
        ready=not errors,
        mock_mode=settings.line_myshop_mock_mode,
        errors=errors,
        warnings=warnings,
    )


@router.post(
    "/products/{product_id}/sync/preview",
    response_model=ProductSyncPreviewResponse,
)
def preview_product_sync(
    product_id: int, db: Session = Depends(get_db)
) -> ProductSyncPreviewResponse:
    settings = get_settings()
    product = get_product_for_sync(db, product_id)
    errors, warnings = evaluate_sync_readiness(product)
    internal_payload = build_product_payload(product)
    action, endpoint, method = get_sync_action(db, product)
    outbound_payload = (
        None
        if errors
        else build_outbound_payload_or_none(db, product, internal_payload)
    )
    return ProductSyncPreviewResponse(
        product_id=product.id,
        ready=not errors,
        mock_mode=settings.line_myshop_mock_mode,
        action=action,
        endpoint=endpoint,
        method=method,
        errors=errors,
        warnings=warnings,
        internal_payload=internal_payload,
        outbound_payload=outbound_payload,
    )


@router.post("/products/{product_id}/sync", response_model=ProductSyncResponse)
def sync_product(
    product_id: int,
    request: ProductSyncRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ProductSyncResponse:
    settings = get_settings()
    product = get_product_for_sync(db, product_id)

    if product.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only approved products can sync",
        )
    if not product.variants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product has no variants to sync",
        )
    if (
        not settings.line_myshop_mock_mode
        and (request is None or request.confirm != PRODUCTION_SYNC_CONFIRMATION)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Production sync requires confirm="
                f"{PRODUCTION_SYNC_CONFIRMATION!r}"
            ),
        )

    readiness_errors, warnings = evaluate_sync_readiness(product)
    if readiness_errors:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"errors": readiness_errors, "warnings": warnings},
        )

    sync_job = create_sync_job(db, "product_sync", product.id)

    external_product_id: str | None = None
    variants_synced = 0

    try:
        product = get_product_for_sync(db, product_id)
        payload = build_product_payload(product)
        client = create_line_myshop_client(db, settings)
        sync_channel = get_sync_channel()
        existing_mapping = get_existing_channel_product(db, product, sync_channel)

        if existing_mapping is None:
            product_response = client.create_product(payload)
            external_product_id = extract_external_product_id(product_response)
        else:
            product_response = client.update_product(
                existing_mapping.external_product_id, payload
            )
            external_product_id = extract_external_product_id(product_response)

        synced_at = now_utc()
        channel_product = get_or_create_channel_product(
            db, product, external_product_id, synced_at, sync_channel
        )
        update_channel_product_line_metadata(
            channel_product, product_response, synced_at
        )
        sorted_variants = sorted(product.variants, key=lambda item: item.id)
        response_variant_ids = extract_variant_external_ids(
            product_response, sorted_variants
        )

        for variant in sorted_variants:
            existing_variant_mapping = get_existing_channel_variant(
                db, variant, sync_channel
            )
            external_variant_id = (
                existing_variant_mapping.external_variant_id
                if existing_variant_mapping is not None
                else response_variant_ids.get(variant.id)
            )
            if external_variant_id is None:
                raise ValueError(
                    "LINE MyShop response does not include external variant id "
                    f"for local variant {variant.id}"
                )
            channel_variant = get_or_create_channel_variant(
                db, variant, external_variant_id, synced_at, sync_channel
            )
            available_stock = (
                variant.inventory_balance.available_stock
                if variant.inventory_balance
                else 0
            )
            if settings.line_myshop_mock_mode or settings.line_myshop_separate_variant_sync:
                client.update_inventory(
                    channel_variant.external_variant_id, available_stock
                )
                client.update_price(
                    channel_variant.external_variant_id,
                    variant.price,
                    variant.sale_price,
                )
            variants_synced += 1

        sync_job.status = "success"
        sync_job.finished_at = now_utc()
        sync_job.error_message = None
        db.commit()
    except Exception as exc:
        db.rollback()
        sync_job = db.get(SyncJob, sync_job.id)
        if sync_job is not None:
            sync_job.status = "failed"
            sync_job.finished_at = now_utc()
            sync_job.error_message = str(exc)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LINE MyShop sync failed: {exc}",
        ) from exc

    return ProductSyncResponse(
        product_id=product.id,
        sync_job_id=sync_job.id,
        status=sync_job.status,
        mock_mode=settings.line_myshop_mock_mode,
        external_product_id=external_product_id,
        variants_synced=variants_synced,
        warnings=warnings,
        message=(
            "Mock LINE MyShop sync completed"
            if settings.line_myshop_mock_mode
            else "LINE MyShop sync completed"
        ),
    )


@router.post(
    "/products/{product_id}/line-status/refresh",
    response_model=ProductLineStatusResponse,
)
def refresh_product_line_status(
    product_id: int,
    db: Session = Depends(get_db),
) -> ProductLineStatusResponse:
    settings = get_settings()
    product = get_product_for_sync(db, product_id)
    channel_product = get_channel_product_or_404(db, product)
    client = create_line_myshop_client(db, settings)
    try:
        line_payload = client.get_product(channel_product.external_product_id)
        update_channel_product_line_metadata(
            channel_product, line_payload, now_utc()
        )
        channel_product.sync_status = "success"
        db.commit()
        db.refresh(channel_product)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LINE MyShop status refresh failed: {exc}",
        ) from exc

    return ProductLineStatusResponse(
        product_id=product.id,
        status="success",
        mock_mode=settings.line_myshop_mock_mode,
        external_product_id=channel_product.external_product_id,
        is_display=channel_product.is_display,
        message="LINE MyShop status refreshed",
    )


def update_product_visibility(
    product_id: int,
    is_display: bool,
    action: str,
    confirmation: str,
    request: ProductLineVisibilityRequest | None,
    db: Session,
) -> ProductLineStatusResponse:
    settings = get_settings()
    product = get_product_for_sync(db, product_id)
    if is_display and product.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only approved products can be published",
        )
    channel_product = get_channel_product_or_404(db, product)
    if (
        not settings.line_myshop_mock_mode
        and (request is None or request.confirm != confirmation)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Production {action} requires confirm={confirmation!r}",
        )

    sync_job = create_sync_job(db, f"product_{action}", product.id)
    try:
        client = create_line_myshop_client(db, settings)
        before_is_display = channel_product.is_display
        line_payload = client.update_visibility(
            channel_product.external_product_id, is_display
        )
        updated_at = now_utc()
        channel_product.sync_status = "success"
        channel_product.last_synced_at = updated_at
        update_channel_product_line_metadata(
            channel_product, line_payload, updated_at
        )
        if channel_product.is_display is None:
            channel_product.is_display = is_display
        db.add(
            AuditLog(
                actor=None,
                action=f"product.{action}",
                target_type="product",
                target_id=product.id,
                before_payload={"is_display": before_is_display},
                after_payload={
                    "is_display": is_display,
                    "reason": request.reason if request else None,
                },
            )
        )
        sync_job.status = "success"
        sync_job.finished_at = now_utc()
        sync_job.error_message = None
        db.commit()
        db.refresh(sync_job)
        db.refresh(channel_product)
    except Exception as exc:
        db.rollback()
        sync_job = db.get(SyncJob, sync_job.id)
        if sync_job is not None:
            sync_job.status = "failed"
            sync_job.finished_at = now_utc()
            sync_job.error_message = str(exc)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LINE MyShop {action} failed: {exc}",
        ) from exc

    return ProductLineStatusResponse(
        product_id=product.id,
        sync_job_id=sync_job.id,
        status=sync_job.status,
        mock_mode=settings.line_myshop_mock_mode,
        external_product_id=channel_product.external_product_id,
        is_display=channel_product.is_display,
        message=(
            "Product published on LINE MyShop"
            if is_display
            else "Product hidden on LINE MyShop"
        ),
    )


@router.post("/products/{product_id}/publish", response_model=ProductLineStatusResponse)
def publish_product(
    product_id: int,
    request: ProductLineVisibilityRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ProductLineStatusResponse:
    return update_product_visibility(
        product_id=product_id,
        is_display=True,
        action="publish",
        confirmation=PRODUCTION_PUBLISH_CONFIRMATION,
        request=request,
        db=db,
    )


@router.post("/products/{product_id}/hide", response_model=ProductLineStatusResponse)
def hide_product(
    product_id: int,
    request: ProductLineVisibilityRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ProductLineStatusResponse:
    return update_product_visibility(
        product_id=product_id,
        is_display=False,
        action="hide",
        confirmation=PRODUCTION_HIDE_CONFIRMATION,
        request=request,
        db=db,
    )


@router.get("/sync-jobs", response_model=list[SyncJobResponse])
def list_sync_jobs(db: Session = Depends(get_db)) -> list[SyncJob]:
    return list(
        db.scalars(select(SyncJob).order_by(SyncJob.created_at.desc(), SyncJob.id.desc()))
        .all()
    )


@router.get("/sync-jobs/{sync_job_id}", response_model=SyncJobResponse)
def get_sync_job(sync_job_id: int, db: Session = Depends(get_db)) -> SyncJob:
    sync_job = db.get(SyncJob, sync_job_id)
    if sync_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync job not found",
        )
    return sync_job
