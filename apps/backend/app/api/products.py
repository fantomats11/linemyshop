import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.models import (
    AuditLog,
    ChannelProduct,
    ImageGenerationJob,
    InventoryBalance,
    Product,
    ProductImage,
    ProductVariant,
)
from app.schemas.products import (
    ArchiveProductRequest,
    BulkCreateProductImagesRequest,
    CreateProductRequest,
    ImageGenerationJobResponse,
    CreateProductImageRequest,
    ImageGenerationSlotResponse,
    InventoryResponse,
    LINE_STOREFRONT_IMAGE_TYPES,
    LINE_STOREFRONT_MAX_IMAGES,
    ProductDetailResponse,
    ProductImageSetResponse,
    ProductImageGenerationBriefResponse,
    ProductImageResponse,
    ProductSummaryResponse,
    ProductVariantResponse,
    RejectProductRequest,
    ReorderProductImagesRequest,
    ReviewProductImageRequest,
    RunImageGenerationJobRequest,
    UpdateInventoryRequest,
    UpdateProductRequest,
    UpdateProductVariantRequest,
    VALID_IMAGE_TYPES,
)
from app.core.config import get_settings
from app.core.paths import workspace_root
from app.services.image_generation_client import FalImageGenerationClient
from app.services.wordpress_client import WordPressMediaClient


router = APIRouter(prefix="/products", tags=["products"])
image_router = APIRouter(prefix="/product-images", tags=["product-images"])
variant_router = APIRouter(prefix="/product-variants", tags=["product-variants"])
image_generation_router = APIRouter(
    prefix="/image-generation-jobs", tags=["image-generation-jobs"]
)
LINE_CHANNEL = "line_myshop"
MOCK_LINE_CHANNEL = "line_myshop_mock"
DEFAULT_MEASUREMENT_LABELS = ("เอว", "สะโพก", "ความยาว")


def normalize_measurements(measurements: list[dict] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for measurement in measurements or []:
        label = str(measurement.get("label", "")).strip()
        value = str(measurement.get("value", "")).strip()
        if label and value:
            normalized.append({"label": label, "value": value})
    return normalized


def legacy_measurements(waist: str, hip: str, length: str) -> list[dict[str, str]]:
    values = [waist, hip, length]
    return [
        {"label": label, "value": value}
        for label, value in zip(DEFAULT_MEASUREMENT_LABELS, values)
        if value
    ]


def variant_measurements(variant: ProductVariant) -> list[dict[str, str]]:
    return normalize_measurements(variant.measurements) or legacy_measurements(
        variant.waist,
        variant.hip,
        variant.length,
    )


def legacy_dimensions_from_measurements(
    measurements: list[dict[str, str]],
    waist: str | None = None,
    hip: str | None = None,
    length: str | None = None,
) -> tuple[str, str, str]:
    values = [measurement["value"] for measurement in measurements]
    return (
        (waist or (values[0] if len(values) > 0 else "")).strip(),
        (hip or (values[1] if len(values) > 1 else "")).strip(),
        (length or (values[2] if len(values) > 2 else "")).strip(),
    )


def repo_root() -> Path:
    return workspace_root()


def safe_uploaded_filename(filename: str) -> str:
    return Path(filename).name.replace(" ", "_")


def safe_generated_filename(value: str) -> str:
    filename = "".join(
        character.lower() if character.isalnum() else "-"
        for character in value.strip()
    )
    return "-".join(part for part in filename.split("-") if part) or "image"


def is_public_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def resolve_workspace_file(value: str) -> Path:
    root = repo_root().resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="image path must be inside workspace",
        )
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="reference image file not found",
        )
    return path


def image_prompt_profile(product: Product) -> dict[str, str]:
    text = f"{product.category} {product.name}".lower()
    if "รองเท้า" in text:
        return {
            "subject": "single pair of shoes only, product centered",
            "detail": "show material texture, sole, stitching, and finish",
            "angle": "side, back, or angled view of the shoes only",
            "lifestyle_title": "Lifestyle foot-level",
            "lifestyle": "foot-level lifestyle image, focus on shoe fit and styling",
            "fit_detail": "show material, sole, and comfort detail",
        }
    if "กระเป๋า" in text:
        return {
            "subject": "single bag only, product centered",
            "detail": "show material texture, hardware, zipper, strap, and stitching",
            "angle": "front, back, or angled view of the bag only",
            "lifestyle_title": "Lifestyle carry view",
            "lifestyle": "model carrying bag lifestyle image, focus on size and styling",
            "fit_detail": "show material, hardware, strap, and pocket detail",
        }
    if any(keyword in text for keyword in ("กางเกง", "กระโปรง")):
        return {
            "subject": "single garment only, product centered",
            "detail": "show fabric texture, stitching, waistband, and fit details",
            "angle": "back or angled view of the garment only",
            "lifestyle_title": "Lifestyle model lower-body",
            "lifestyle": "lower-body model lifestyle image, modest crop, focus on fit",
            "fit_detail": "show stretch fabric and fit detail",
        }
    if any(
        keyword in text
        for keyword in ("เสื้อ", "ไหมพรม", "แจ็คเก็ต", "โค้ท", "เสื้อกันหนาว")
    ):
        return {
            "subject": "single top garment only, product centered",
            "detail": "show knit texture, collar, cuffs, seams, and fabric thickness",
            "angle": "front, back, or angled view of the top only",
            "lifestyle_title": "Lifestyle model upper-body",
            "lifestyle": (
                "upper-body model lifestyle image, modest crop, "
                "focus on neckline, sleeves, and fit"
            ),
            "fit_detail": "show knit texture, stretch, neckline, and sleeve detail",
        }
    return {
        "subject": "single product only, product centered",
        "detail": "show material texture, stitching, finish, and key details",
        "angle": "front, back, or angled view of the product only",
        "lifestyle_title": "Lifestyle product view",
        "lifestyle": "clean lifestyle image, focus on real product shape and use",
        "fit_detail": "show material and key product detail",
    }


def build_product_summary(
    product: Product,
    variant_count: int,
    total_stock: int,
    total_available_stock: int,
    image_url: str | None,
    channel_product: ChannelProduct | None = None,
) -> ProductSummaryResponse:
    return ProductSummaryResponse(
        id=product.id,
        product_group=product.product_group,
        name=product.name,
        color=product.color,
        gender=product.gender,
        category=product.category,
        status=product.status,
        variant_count=variant_count,
        total_stock=total_stock,
        total_available_stock=total_available_stock,
        image_url=image_url,
        created_at=product.created_at,
        updated_at=product.updated_at,
        external_product_id=(
            channel_product.external_product_id if channel_product else None
        ),
        sync_status=channel_product.sync_status if channel_product else None,
        last_synced_at=channel_product.last_synced_at if channel_product else None,
        is_display=channel_product.is_display if channel_product else None,
        line_last_refreshed_at=(
            channel_product.last_refreshed_at if channel_product else None
        ),
    )


def get_product_channel_mapping(
    session: Session, product_id: int
) -> ChannelProduct | None:
    return session.scalar(
        select(ChannelProduct)
        .where(ChannelProduct.product_id == product_id)
        .where(ChannelProduct.channel.in_([LINE_CHANNEL, MOCK_LINE_CHANNEL]))
        .order_by(
            (ChannelProduct.channel == LINE_CHANNEL).desc(),
            ChannelProduct.updated_at.desc(),
        )
        .limit(1)
    )


def product_summary_by_id(session: Session, product_id: int) -> ProductSummaryResponse:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    variant_count = session.scalar(
        select(func.count(ProductVariant.id)).where(ProductVariant.product_id == product.id)
    )
    total_stock = session.scalar(
        select(func.coalesce(func.sum(InventoryBalance.stock_on_hand), 0))
        .join(ProductVariant, InventoryBalance.variant_id == ProductVariant.id)
        .where(ProductVariant.product_id == product.id)
    )
    total_available_stock = session.scalar(
        select(func.coalesce(func.sum(InventoryBalance.available_stock), 0))
        .join(ProductVariant, InventoryBalance.variant_id == ProductVariant.id)
        .where(ProductVariant.product_id == product.id)
    )
    image_url = session.scalar(
        select(ProductImage.url)
        .where(ProductImage.product_id == product.id)
        .where(ProductImage.status == "approved")
        .where(ProductImage.image_type == "product")
        .order_by(ProductImage.is_main.desc(), ProductImage.position, ProductImage.id)
        .limit(1)
    )

    return build_product_summary(
        product=product,
        variant_count=variant_count or 0,
        total_stock=total_stock or 0,
        total_available_stock=total_available_stock or 0,
        image_url=image_url,
        channel_product=get_product_channel_mapping(session, product.id),
    )


def image_to_response(image: ProductImage) -> ProductImageResponse:
    return ProductImageResponse(
        id=image.id,
        url=image.url,
        position=image.position,
        status=image.status,
        image_type=image.image_type,
        is_main=image.is_main,
        review_note=image.review_note,
    )


def get_line_storefront_images(product: Product) -> list[ProductImage]:
    return sorted(
        [
            image
            for image in product.images
            if image.status == "approved"
            and image.image_type in LINE_STOREFRONT_IMAGE_TYPES
        ],
        key=lambda image: (not image.is_main, image.position, image.id),
    )


def evaluate_image_set(product: Product) -> tuple[list[str], list[str], list[ProductImage]]:
    errors: list[str] = []
    warnings: list[str] = []
    storefront_images = get_line_storefront_images(product)

    if not storefront_images:
        errors.append("product must have at least one approved storefront image")
    if len(storefront_images) > LINE_STOREFRONT_MAX_IMAGES:
        errors.append("LINE MyShop supports at most 7 storefront images")
    if storefront_images and not any(
        image.image_type == "product" and image.is_main for image in storefront_images
    ):
        errors.append("product must have one approved main product image")

    positions = [image.position for image in storefront_images]
    duplicate_positions = sorted(
        {position for position in positions if positions.count(position) > 1}
    )
    if duplicate_positions:
        warnings.append(
            "storefront image positions should be unique: "
            + ", ".join(str(position) for position in duplicate_positions)
        )

    for image in storefront_images:
        if image.position < 1 or image.position > LINE_STOREFRONT_MAX_IMAGES:
            errors.append(f"image {image.id} position must be between 1 and 7")
        if not (image.url.startswith("http://") or image.url.startswith("https://")):
            errors.append(f"image {image.id} must use a public http or https URL")

    if storefront_images:
        warnings.append("LINE MyShop images should be 1:1 square, recommended 640x640")

    return errors, warnings, storefront_images


def validate_image_request(request: CreateProductImageRequest) -> None:
    if not request.url.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="url is required",
        )
    if request.image_type not in VALID_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="image_type must be one of: product, lifestyle, detail, size_chart, brief",
        )
    if request.image_type != "brief" and (
        request.position < 1 or request.position > LINE_STOREFRONT_MAX_IMAGES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="position must be between 1 and 7 for storefront images",
        )


@router.get("", response_model=list[ProductSummaryResponse])
def list_products(
    include_archived: bool = False,
    db: Session = Depends(get_db),
) -> list[ProductSummaryResponse]:
    query = select(Product).order_by(Product.created_at.desc(), Product.id.desc())
    if not include_archived:
        query = query.where(Product.status != "archived")

    products = db.scalars(query).all()
    summaries: list[ProductSummaryResponse] = []

    for product in products:
        summaries.append(product_summary_by_id(db, product.id))

    return summaries


@router.post("", response_model=ProductDetailResponse)
def create_product(
    request: CreateProductRequest,
    db: Session = Depends(get_db),
) -> ProductDetailResponse:
    product_group = request.product_group.strip()
    if not product_group:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="product_group is required",
        )
    if not request.variants:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="variants cannot be empty",
        )
    if db.scalar(select(Product.id).where(Product.product_group == product_group)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="product_group already exists",
        )

    seen_skus: set[str] = set()
    for variant_request in request.variants:
        sku = variant_request.sku.strip()
        if not sku:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="sku is required",
            )
        if sku in seen_skus:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"duplicate sku in request: {sku}",
            )
        seen_skus.add(sku)
        if db.scalar(select(ProductVariant.id).where(ProductVariant.sku == sku)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"sku already exists: {sku}",
            )
        if variant_request.stock_on_hand < 0 or variant_request.reserved_stock < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="inventory values must be greater than or equal to 0",
            )
        if not normalize_measurements(
            [item.model_dump() for item in variant_request.measurements or []]
        ) and not (
            (variant_request.waist or "").strip()
            and (variant_request.hip or "").strip()
            and (variant_request.length or "").strip()
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="variant measurements are required",
            )

    product = Product(
        product_group=product_group,
        name=request.name.strip(),
        color=request.color.strip(),
        gender=request.gender.strip(),
        category=request.category.strip(),
        description=request.description.strip() if request.description else None,
        note=request.note.strip() if request.note else None,
        status=request.status,
    )
    db.add(product)
    db.flush()

    for variant_request in request.variants:
        measurements = normalize_measurements(
            [item.model_dump() for item in variant_request.measurements or []]
        )
        if not measurements:
            measurements = legacy_measurements(
                (variant_request.waist or "").strip(),
                (variant_request.hip or "").strip(),
                (variant_request.length or "").strip(),
            )
        waist, hip, length = legacy_dimensions_from_measurements(
            measurements,
            variant_request.waist,
            variant_request.hip,
            variant_request.length,
        )
        variant = ProductVariant(
            product_id=product.id,
            sku=variant_request.sku.strip(),
            barcode=(variant_request.barcode or variant_request.sku).strip(),
            size=variant_request.size.strip(),
            waist=waist,
            hip=hip,
            length=length,
            measurements=measurements,
            price=variant_request.price,
            sale_price=variant_request.sale_price,
            status=variant_request.status,
        )
        db.add(variant)
        db.flush()
        db.add(
            InventoryBalance(
                variant_id=variant.id,
                stock_on_hand=variant_request.stock_on_hand,
                reserved_stock=variant_request.reserved_stock,
                available_stock=(
                    variant_request.stock_on_hand - variant_request.reserved_stock
                ),
            )
        )

    db.add(
        AuditLog(
            actor=None,
            action="product.create",
            target_type="product",
            target_id=product.id,
            before_payload=None,
            after_payload={
                "product_group": product.product_group,
                "variant_count": len(request.variants),
            },
        )
    )
    db.commit()
    return get_product(product.id, db)


@router.get("/{product_id}", response_model=ProductDetailResponse)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductDetailResponse:
    product = db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory_balance),
        )
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    images = sorted(product.images, key=lambda image: (image.position, image.id))
    variants = sorted(product.variants, key=lambda variant: (variant.size, variant.id))
    channel_product = get_product_channel_mapping(db, product.id)

    return ProductDetailResponse(
        id=product.id,
        product_group=product.product_group,
        name=product.name,
        color=product.color,
        gender=product.gender,
        category=product.category,
        description=product.description,
        note=product.note,
        status=product.status,
        images=[image_to_response(image) for image in images],
        variants=[
            ProductVariantResponse(
                id=variant.id,
                sku=variant.sku,
                barcode=variant.barcode,
                size=variant.size,
                waist=variant.waist,
                hip=variant.hip,
                length=variant.length,
                measurements=variant_measurements(variant),
                price=variant.price,
                sale_price=variant.sale_price,
                status=variant.status,
                inventory=(
                    InventoryResponse(
                        stock_on_hand=variant.inventory_balance.stock_on_hand,
                        reserved_stock=variant.inventory_balance.reserved_stock,
                        available_stock=variant.inventory_balance.available_stock,
                    )
                    if variant.inventory_balance
                    else None
                ),
            )
            for variant in variants
        ],
        external_product_id=(
            channel_product.external_product_id if channel_product else None
        ),
        sync_status=channel_product.sync_status if channel_product else None,
        last_synced_at=channel_product.last_synced_at if channel_product else None,
        is_display=channel_product.is_display if channel_product else None,
        line_last_refreshed_at=(
            channel_product.last_refreshed_at if channel_product else None
        ),
    )


@router.patch("/{product_id}", response_model=ProductDetailResponse)
def update_product(
    product_id: int,
    request: UpdateProductRequest,
    db: Session = Depends(get_db),
) -> ProductDetailResponse:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    before_payload = {
        "name": product.name,
        "color": product.color,
        "gender": product.gender,
        "category": product.category,
        "description": product.description,
        "note": product.note,
    }
    updates = request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(product, key, value)

    db.add(
        AuditLog(
            actor=None,
            action="product.update",
            target_type="product",
            target_id=product.id,
            before_payload=before_payload,
            after_payload=updates,
        )
    )
    db.commit()
    return get_product(product_id, db)


@router.post("/{product_id}/approve", response_model=ProductSummaryResponse)
def approve_product(
    product_id: int, db: Session = Depends(get_db)
) -> ProductSummaryResponse:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft products can be approved",
        )

    before_payload = {"status": product.status}
    product.status = "approved"
    db.add(
        AuditLog(
            actor=None,
            action="product.approve",
            target_type="product",
            target_id=product.id,
            before_payload=before_payload,
            after_payload={"status": product.status},
        )
    )
    db.commit()
    db.refresh(product)
    return product_summary_by_id(db, product.id)


@router.get("/{product_id}/images", response_model=list[ProductImageResponse])
def list_product_images(
    product_id: int, db: Session = Depends(get_db)
) -> list[ProductImage]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    return list(
        db.scalars(
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.position, ProductImage.id)
        ).all()
    )


@router.get("/{product_id}/image-set", response_model=ProductImageSetResponse)
def get_product_image_set(
    product_id: int, db: Session = Depends(get_db)
) -> ProductImageSetResponse:
    product = db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.images))
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    errors, warnings, storefront_images = evaluate_image_set(product)
    return ProductImageSetResponse(
        product_id=product.id,
        max_images=LINE_STOREFRONT_MAX_IMAGES,
        ready=not errors,
        errors=errors,
        warnings=warnings,
        images=[image_to_response(image) for image in storefront_images],
    )


@router.post("/{product_id}/reference-images", response_model=list[ProductImageResponse])
def upload_product_reference_images(
    product_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> list[ProductImage]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="files cannot be empty",
        )

    upload_dir = (
        repo_root() / "data" / "input" / "product-references" / f"product-{product.id}"
    )
    upload_dir.mkdir(parents=True, exist_ok=True)
    created_images: list[ProductImage] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    next_position = (
        db.scalar(
            select(func.coalesce(func.max(ProductImage.position), 0))
            .where(ProductImage.product_id == product.id)
            .where(ProductImage.image_type == "brief")
        )
        or 0
    ) + 1

    for index, file in enumerate(files):
        if not file.filename:
            continue
        filename = f"{timestamp}_{index + 1}_{safe_uploaded_filename(file.filename)}"
        destination = upload_dir / filename
        with destination.open("wb") as output_file:
            shutil.copyfileobj(file.file, output_file)
        relative_path = destination.relative_to(repo_root()).as_posix()
        image = ProductImage(
            product_id=product.id,
            url=relative_path,
            position=next_position + index,
            status="draft",
            image_type="brief",
            is_main=False,
            review_note="reference image uploaded by staff",
        )
        db.add(image)
        created_images.append(image)

    db.add(
        AuditLog(
            actor=None,
            action="product_reference_images.upload",
            target_type="product",
            target_id=product.id,
            before_payload=None,
            after_payload={"image_count": len(created_images)},
        )
    )
    db.commit()
    for image in created_images:
        db.refresh(image)
    return created_images


@router.get(
    "/{product_id}/image-generation-brief",
    response_model=ProductImageGenerationBriefResponse,
)
def get_product_image_generation_brief(
    product_id: int,
    db: Session = Depends(get_db),
) -> ProductImageGenerationBriefResponse:
    product = db.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.images), selectinload(Product.variants))
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    reference_images = sorted(
        [image for image in product.images if image.image_type == "brief"],
        key=lambda image: (image.position, image.id),
    )
    errors: list[str] = []
    warnings: list[str] = []
    if not reference_images:
        warnings.append("ควรอัปโหลด reference images ก่อนสร้างรูปสินค้า")
    if not product.variants:
        errors.append("product must have variants before image generation")

    size_values = ", ".join(sorted({variant.size for variant in product.variants}))
    base_context = (
        f"{product.name}, สี {product.color}, หมวด {product.category}, "
        f"ไซซ์ {size_values or '-'}"
    )
    profile = image_prompt_profile(product)
    slots = [
        ImageGenerationSlotResponse(
            position=1,
            image_type="product",
            title="Main product image",
            prompt=(
                "1:1 clean ecommerce product photo for LINE MyShop, "
                f"{base_context}, {profile['subject']}, no multiple copies, "
                "white studio background, accurate color and material, no text"
            ),
            required=True,
        ),
        ImageGenerationSlotResponse(
            position=2,
            image_type="detail",
            title="Detail close-up",
            prompt=(
                f"1:1 close-up detail photo, {base_context}, {profile['detail']}, "
                "premium catalog lighting"
            ),
            required=True,
        ),
        ImageGenerationSlotResponse(
            position=3,
            image_type="product",
            title="Back or angle view",
            prompt=(
                f"1:1 ecommerce product angle view, {base_context}, "
                f"{profile['angle']}, no multiple copies, "
                "consistent with reference images, clean background"
            ),
            required=True,
        ),
        ImageGenerationSlotResponse(
            position=4,
            image_type="lifestyle",
            title=profile["lifestyle_title"],
            prompt=(
                f"1:1 {profile['lifestyle']}, {base_context}, "
                "clean fashion styling"
            ),
            required=False,
        ),
        ImageGenerationSlotResponse(
            position=5,
            image_type="size_chart",
            title="Size guide",
            prompt=(
                f"1:1 Thai size guide graphic for {product.name}, "
                "readable typography, sizes and measurements from variants, "
                "clean table layout"
            ),
            required=True,
        ),
        ImageGenerationSlotResponse(
            position=6,
            image_type="detail",
            title="Fabric or fit detail",
            prompt=(
                f"1:1 detail composition, {base_context}, "
                f"{profile['fit_detail']}, premium ecommerce style"
            ),
            required=False,
        ),
        ImageGenerationSlotResponse(
            position=7,
            image_type="lifestyle",
            title="Optional lifestyle flatlay",
            prompt=f"1:1 styled flatlay, {base_context}, minimal accessories, premium marketplace presentation",
            required=False,
        ),
    ]

    return ProductImageGenerationBriefResponse(
        product_id=product.id,
        ready=not errors,
        errors=errors,
        warnings=warnings,
        reference_images=[image_to_response(image) for image in reference_images],
        slots=slots,
    )


def image_generation_brief_payload(
    product_id: int, db: Session
) -> ProductImageGenerationBriefResponse:
    return get_product_image_generation_brief(product_id, db)


@router.post(
    "/{product_id}/image-generation-jobs",
    response_model=ImageGenerationJobResponse,
)
def create_image_generation_job(
    product_id: int,
    db: Session = Depends(get_db),
) -> ImageGenerationJob:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    brief = image_generation_brief_payload(product_id, db)
    if not brief.ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"errors": brief.errors, "warnings": brief.warnings},
        )

    job = ImageGenerationJob(
        product_id=product.id,
        status="waiting_for_generated_images",
        mode="manual_or_agent_imagegen",
        prompt_payload=brief.model_dump(mode="json"),
        result_payload=None,
        error_message=None,
    )
    db.add(job)
    db.flush()
    db.add(
        AuditLog(
            actor=None,
            action="image_generation_job.create",
            target_type="product",
            target_id=product.id,
            before_payload=None,
            after_payload={
                "image_generation_job_id": job.id,
                "slot_count": len(brief.slots),
            },
        )
    )
    db.commit()
    db.refresh(job)
    return job


@image_generation_router.get(
    "/{job_id}",
    response_model=ImageGenerationJobResponse,
)
def get_image_generation_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> ImageGenerationJob:
    job = db.get(ImageGenerationJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image generation job not found",
        )
    return job


@image_generation_router.post(
    "/{job_id}/run",
    response_model=ImageGenerationJobResponse,
)
def run_image_generation_job(
    job_id: int,
    request: RunImageGenerationJobRequest | None = None,
    db: Session = Depends(get_db),
) -> ImageGenerationJob:
    request = request or RunImageGenerationJobRequest()
    if request.num_images_per_slot < 1 or request.num_images_per_slot > 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="num_images_per_slot must be between 1 and 4",
        )

    job = db.get(ImageGenerationJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image generation job not found",
        )
    if job.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Image generation job is already running",
        )
    if job.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Image generation job is already completed",
        )

    product = db.scalar(
        select(Product)
        .where(Product.id == job.product_id)
        .options(selectinload(Product.images))
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    reference_images = sorted(
        [image for image in product.images if image.image_type == "brief"],
        key=lambda image: (image.position, image.id),
    )
    if not reference_images:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="reference images are required before running image generation",
        )

    slots = job.prompt_payload.get("slots", [])
    if not isinstance(slots, list) or not slots:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="image generation job has no prompt slots",
        )
    selected_positions = set(request.slot_positions or [])
    selected_slots = [
        slot
        for slot in slots
        if isinstance(slot, dict)
        and (not selected_positions or slot.get("position") in selected_positions)
    ]
    if not selected_slots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="slot_positions did not match any image generation slots",
        )

    settings = get_settings()
    image_client = FalImageGenerationClient(db, settings, repo_root())
    wordpress_client = WordPressMediaClient(settings)
    reference_urls = [image.url for image in reference_images]
    generated_dir = (
        repo_root()
        / "data"
        / "output"
        / "generated-product-images"
        / f"product-{product.id}"
        / f"job-{job.id}"
    )
    generated_dir.mkdir(parents=True, exist_ok=True)

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.error_message = None
    db.commit()

    created_images: list[ProductImage] = []
    result_items: list[dict] = []
    try:
        if request.approve:
            existing_main_images = db.scalars(
                select(ProductImage)
                .where(ProductImage.product_id == product.id)
                .where(ProductImage.is_main.is_(True))
            ).all()
            for image in existing_main_images:
                image.is_main = False

        for slot in selected_slots:
            slot_position = int(slot.get("position") or 1)
            image_type = str(slot.get("image_type") or "product")
            if image_type not in LINE_STOREFRONT_IMAGE_TYPES:
                image_type = "product"
            prompt = str(slot.get("prompt") or "")
            title = str(slot.get("title") or f"image-{slot_position}")
            generated_images = image_client.generate_image(
                prompt=prompt,
                reference_urls=reference_urls,
                quality=request.quality,
                image_size=request.image_size,
                output_format=request.output_format,
                num_images=request.num_images_per_slot,
            )
            for generated_index, generated in enumerate(generated_images, start=1):
                generated_url = generated.get("url")
                if not generated_url:
                    raise RuntimeError("generated image is missing url")
                extension = (
                    "jpg"
                    if (request.output_format or settings.fal_image_format) == "jpeg"
                    else (request.output_format or settings.fal_image_format)
                )
                local_path = generated_dir / (
                    f"{slot_position:02d}-"
                    f"{safe_generated_filename(title)}-"
                    f"{generated_index}.{extension}"
                )
                image_client.download_image(str(generated_url), local_path)
                media_response = wordpress_client.upload_media(local_path)
                image = ProductImage(
                    product_id=product.id,
                    url=media_response["source_url"],
                    position=slot_position,
                    status="approved" if request.approve else "draft",
                    image_type=image_type,
                    is_main=(
                        request.approve
                        and request.set_main_position == slot_position
                        and image_type == "product"
                    ),
                    review_note=(
                        "generated by fal.ai image generation workflow"
                        if request.approve
                        else None
                    ),
                )
                db.add(image)
                created_images.append(image)
                result_items.append(
                    {
                        "slot_position": slot_position,
                        "image_type": image_type,
                        "fal_url": generated_url,
                        "local_path": local_path.relative_to(repo_root()).as_posix(),
                        "wordpress_url": image.url,
                        "status": image.status,
                        "is_main": image.is_main,
                    }
                )

        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        job.result_payload = {
            "provider": "fal",
            "model": settings.fal_image_model,
            "quality": request.quality or settings.fal_image_quality,
            "image_size": request.image_size or settings.fal_image_size,
            "output_format": request.output_format or settings.fal_image_format,
            "images": result_items,
        }
        db.add(
            AuditLog(
                actor=None,
                action="image_generation_job.run",
                target_type="product",
                target_id=product.id,
                before_payload=None,
                after_payload={
                    "image_generation_job_id": job.id,
                    "provider": "fal",
                    "image_count": len(created_images),
                },
            )
        )
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:
        db.rollback()
        job = db.get(ImageGenerationJob, job_id)
        if job is not None:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"image generation failed: {exc}",
        ) from exc


@image_generation_router.post(
    "/{job_id}/generated-images",
    response_model=list[ProductImageResponse],
)
def upload_generated_images_for_job(
    job_id: int,
    files: list[UploadFile] = File(...),
    image_types: list[str] | None = Form(default=None),
    approve: bool = Form(default=False),
    set_main_index: int = Form(default=1),
    db: Session = Depends(get_db),
) -> list[ProductImage]:
    job = db.get(ImageGenerationJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image generation job not found",
        )
    product = db.get(Product, job.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="files cannot be empty",
        )
    slots = job.prompt_payload.get("slots", [])
    default_image_types = [
        slot.get("image_type", "product")
        for slot in slots[: len(files)]
    ]
    resolved_image_types = image_types or default_image_types
    if len(resolved_image_types) != len(files):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="image_types must match uploaded file count",
        )
    for image_type in resolved_image_types:
        if image_type not in VALID_IMAGE_TYPES or image_type == "brief":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="image_types must be one of: product, lifestyle, detail, size_chart",
            )

    temp_dir = repo_root() / "data" / "output" / "generated-upload-temp" / f"job-{job.id}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    wordpress_client = WordPressMediaClient(settings)
    start_position = (
        db.scalar(
            select(func.coalesce(func.max(ProductImage.position), 0)).where(
                ProductImage.product_id == product.id
            )
        )
        or 0
    ) + 1
    created_images: list[ProductImage] = []

    try:
        if approve and set_main_index:
            existing_main_images = db.scalars(
                select(ProductImage)
                .where(ProductImage.product_id == product.id)
                .where(ProductImage.is_main.is_(True))
            ).all()
            for image in existing_main_images:
                image.is_main = False

        for index, (file, image_type) in enumerate(zip(files, resolved_image_types), start=1):
            if not file.filename:
                continue
            destination = temp_dir / f"{index}_{safe_uploaded_filename(file.filename)}"
            with destination.open("wb") as output_file:
                shutil.copyfileobj(file.file, output_file)
            media_response = wordpress_client.upload_media(destination)
            image = ProductImage(
                product_id=product.id,
                url=media_response["source_url"],
                position=start_position + index - 1,
                status="approved" if approve else "draft",
                image_type=image_type,
                is_main=approve and set_main_index == index and image_type == "product",
                review_note=(
                    "generated image uploaded through image generation workflow"
                    if approve
                    else None
                ),
            )
            db.add(image)
            created_images.append(image)

        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        job.result_payload = {
            "images": [
                {
                    "url": image.url,
                    "image_type": image.image_type,
                    "position": image.position,
                    "status": image.status,
                    "is_main": image.is_main,
                }
                for image in created_images
            ]
        }
        db.add(
            AuditLog(
                actor=None,
                action="image_generation_job.generated_images_upload",
                target_type="product",
                target_id=product.id,
                before_payload=None,
                after_payload={
                    "image_generation_job_id": job.id,
                    "image_count": len(created_images),
                },
            )
        )
        db.commit()
        for image in created_images:
            db.refresh(image)
        return created_images
    except Exception as exc:
        db.rollback()
        job = db.get(ImageGenerationJob, job_id)
        if job is not None:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"generated image upload failed: {exc}",
        ) from exc


@router.post("/{product_id}/images", response_model=ProductImageResponse)
def create_product_image(
    product_id: int,
    request: CreateProductImageRequest,
    db: Session = Depends(get_db),
) -> ProductImage:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    validate_image_request(request)

    image = ProductImage(
        product_id=product.id,
        url=request.url.strip(),
        image_type=request.image_type,
        position=request.position,
        status="draft",
        is_main=False,
        review_note=None,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image


@router.post("/{product_id}/images/bulk", response_model=list[ProductImageResponse])
def bulk_create_product_images(
    product_id: int,
    request: BulkCreateProductImagesRequest,
    db: Session = Depends(get_db),
) -> list[ProductImage]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not request.images:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="images cannot be empty",
        )
    if len(request.images) > LINE_STOREFRONT_MAX_IMAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="LINE MyShop supports at most 7 storefront images",
        )

    images: list[ProductImage] = []
    for image_request in request.images:
        validate_image_request(image_request)
        image = ProductImage(
            product_id=product.id,
            url=image_request.url.strip(),
            image_type=image_request.image_type,
            position=image_request.position,
            status="draft",
            is_main=False,
            review_note=None,
        )
        db.add(image)
        images.append(image)

    db.commit()
    for image in images:
        db.refresh(image)
    return images


@router.post("/{product_id}/images/reorder", response_model=list[ProductImageResponse])
def reorder_product_images(
    product_id: int,
    request: ReorderProductImagesRequest,
    db: Session = Depends(get_db),
) -> list[ProductImage]:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not request.images:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="images cannot be empty",
        )
    if sum(1 for item in request.images if item.is_main) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="only one image can be main",
        )

    images_by_id = {
        image.id: image
        for image in db.scalars(
            select(ProductImage).where(ProductImage.product_id == product.id)
        ).all()
    }
    for item in request.images:
        image = images_by_id.get(item.image_id)
        if image is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product image {item.image_id} not found",
            )
        if item.position < 1 or item.position > LINE_STOREFRONT_MAX_IMAGES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="position must be between 1 and 7",
            )
        if item.is_main and (image.status != "approved" or image.image_type != "product"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only approved product images can be set as main",
            )

    before_payload = [
        {
            "id": image.id,
            "position": image.position,
            "is_main": image.is_main,
        }
        for image in images_by_id.values()
    ]

    should_update_main = any(item.is_main for item in request.images)
    if should_update_main:
        for image in images_by_id.values():
            image.is_main = False
    for item in request.images:
        image = images_by_id[item.image_id]
        image.position = item.position
        if item.is_main:
            image.is_main = True

    after_payload = [
        {
            "id": image.id,
            "position": image.position,
            "is_main": image.is_main,
        }
        for image in images_by_id.values()
    ]
    db.add(
        AuditLog(
            actor=None,
            action="product_image.reorder",
            target_type="product",
            target_id=product.id,
            before_payload={"images": before_payload},
            after_payload={"images": after_payload},
        )
    )
    db.commit()

    return list(
        db.scalars(
            select(ProductImage)
            .where(ProductImage.product_id == product.id)
            .order_by(ProductImage.position, ProductImage.id)
        ).all()
    )


def get_product_image_or_404(db: Session, image_id: int) -> ProductImage:
    image = db.get(ProductImage, image_id)
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product image not found",
        )
    return image


@image_router.post("/{image_id}/promote-reference", response_model=ProductImageResponse)
def promote_reference_image_to_product(
    image_id: int,
    db: Session = Depends(get_db),
) -> ProductImage:
    reference_image = get_product_image_or_404(db, image_id)
    if reference_image.image_type != "brief":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only brief images can be promoted to product images",
        )
    if reference_image.status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rejected reference images cannot be promoted",
        )
    product = db.get(Product, reference_image.product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    settings = get_settings()
    try:
        product_image_url = reference_image.url
        if not is_public_url(reference_image.url):
            source_path = resolve_workspace_file(reference_image.url)
            product_image_url = WordPressMediaClient(settings).upload_media(source_path)[
                "source_url"
            ]

        existing_main_images = db.scalars(
            select(ProductImage)
            .where(ProductImage.product_id == product.id)
            .where(ProductImage.is_main.is_(True))
        ).all()
        for image in existing_main_images:
            image.is_main = False

        promoted_image = ProductImage(
            product_id=product.id,
            url=product_image_url,
            position=1,
            status="approved",
            image_type="product",
            is_main=True,
            review_note=f"promoted from reference image #{reference_image.id}",
        )
        db.add(promoted_image)
        db.add(
            AuditLog(
                actor=None,
                action="product_image.promote_reference",
                target_type="product_image",
                target_id=reference_image.id,
                before_payload={
                    "url": reference_image.url,
                    "status": reference_image.status,
                    "image_type": reference_image.image_type,
                },
                after_payload={
                    "url": product_image_url,
                    "status": promoted_image.status,
                    "image_type": promoted_image.image_type,
                    "is_main": promoted_image.is_main,
                },
            )
        )
        db.commit()
        db.refresh(promoted_image)
        return promoted_image
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"reference image promotion failed: {exc}",
        ) from exc


@image_router.post("/{image_id}/approve", response_model=ProductImageResponse)
def approve_product_image(
    image_id: int,
    request: ReviewProductImageRequest | None = None,
    db: Session = Depends(get_db),
) -> ProductImage:
    image = get_product_image_or_404(db, image_id)
    if image.image_type == "brief":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Brief images cannot be approved as product images",
        )

    before_payload = {"status": image.status, "image_type": image.image_type}
    image.status = "approved"
    image.review_note = request.review_note if request else image.review_note
    db.add(
        AuditLog(
            actor=None,
            action="product_image.approve",
            target_type="product_image",
            target_id=image.id,
            before_payload=before_payload,
            after_payload={
                "status": image.status,
                "image_type": image.image_type,
                "review_note": image.review_note,
            },
        )
    )
    db.commit()
    db.refresh(image)
    return image


@image_router.post("/{image_id}/reject", response_model=ProductImageResponse)
def reject_product_image(
    image_id: int,
    request: ReviewProductImageRequest | None = None,
    db: Session = Depends(get_db),
) -> ProductImage:
    image = get_product_image_or_404(db, image_id)
    before_payload = {"status": image.status, "image_type": image.image_type}
    image.status = "rejected"
    image.is_main = False
    image.review_note = request.review_note if request else image.review_note
    db.add(
        AuditLog(
            actor=None,
            action="product_image.reject",
            target_type="product_image",
            target_id=image.id,
            before_payload=before_payload,
            after_payload={
                "status": image.status,
                "image_type": image.image_type,
                "review_note": image.review_note,
            },
        )
    )
    db.commit()
    db.refresh(image)
    return image


@image_router.post("/{image_id}/set-main", response_model=ProductImageResponse)
def set_main_product_image(
    image_id: int, db: Session = Depends(get_db)
) -> ProductImage:
    image = get_product_image_or_404(db, image_id)
    if image.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only approved images can be set as main",
        )
    if image.image_type != "product":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only approved product images can be set as main",
        )

    before_payload = {
        "status": image.status,
        "image_type": image.image_type,
        "is_main": image.is_main,
    }
    existing_main_images = db.scalars(
        select(ProductImage)
        .where(ProductImage.product_id == image.product_id)
        .where(ProductImage.is_main.is_(True))
    ).all()
    for existing_image in existing_main_images:
        existing_image.is_main = False
    image.is_main = True
    db.add(
        AuditLog(
            actor=None,
            action="product_image.set_main",
            target_type="product_image",
            target_id=image.id,
            before_payload=before_payload,
            after_payload={
                "status": image.status,
                "image_type": image.image_type,
                "is_main": image.is_main,
            },
        )
    )
    db.commit()
    db.refresh(image)
    return image


def variant_to_response(variant: ProductVariant) -> ProductVariantResponse:
    return ProductVariantResponse(
        id=variant.id,
        sku=variant.sku,
        barcode=variant.barcode,
        size=variant.size,
        waist=variant.waist,
        hip=variant.hip,
        length=variant.length,
        measurements=variant_measurements(variant),
        price=variant.price,
        sale_price=variant.sale_price,
        status=variant.status,
        inventory=(
            InventoryResponse(
                stock_on_hand=variant.inventory_balance.stock_on_hand,
                reserved_stock=variant.inventory_balance.reserved_stock,
                available_stock=variant.inventory_balance.available_stock,
            )
            if variant.inventory_balance
            else None
        ),
    )


@variant_router.patch("/{variant_id}", response_model=ProductVariantResponse)
def update_product_variant(
    variant_id: int,
    request: UpdateProductVariantRequest,
    db: Session = Depends(get_db),
) -> ProductVariantResponse:
    variant = db.scalar(
        select(ProductVariant)
        .where(ProductVariant.id == variant_id)
        .options(selectinload(ProductVariant.inventory_balance))
    )
    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product variant not found",
        )

    before_payload = {
        "barcode": variant.barcode,
        "size": variant.size,
        "waist": variant.waist,
        "hip": variant.hip,
        "length": variant.length,
        "measurements": variant_measurements(variant),
        "price": str(variant.price),
        "sale_price": str(variant.sale_price) if variant.sale_price is not None else None,
        "status": variant.status,
    }
    updates = request.model_dump(exclude_unset=True)
    if "measurements" in updates:
        updates["measurements"] = normalize_measurements(updates["measurements"])
        if updates["measurements"]:
            waist, hip, length = legacy_dimensions_from_measurements(
                updates["measurements"],
                updates.get("waist"),
                updates.get("hip"),
                updates.get("length"),
            )
            updates.setdefault("waist", waist)
            updates.setdefault("hip", hip)
            updates.setdefault("length", length)
    for key, value in updates.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(variant, key, value)

    db.add(
        AuditLog(
            actor=None,
            action="product_variant.update",
            target_type="product_variant",
            target_id=variant.id,
            before_payload=before_payload,
            after_payload={
                key: str(value) if key in {"price", "sale_price"} and value is not None else value
                for key, value in updates.items()
            },
        )
    )
    db.commit()
    db.refresh(variant)
    return variant_to_response(variant)


@variant_router.patch("/{variant_id}/inventory", response_model=InventoryResponse)
def update_variant_inventory(
    variant_id: int,
    request: UpdateInventoryRequest,
    db: Session = Depends(get_db),
) -> InventoryResponse:
    variant = db.scalar(
        select(ProductVariant)
        .where(ProductVariant.id == variant_id)
        .options(selectinload(ProductVariant.inventory_balance))
    )
    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product variant not found",
        )
    inventory = variant.inventory_balance
    if inventory is None:
        inventory = InventoryBalance(
            variant_id=variant.id,
            stock_on_hand=0,
            reserved_stock=0,
            available_stock=0,
        )
        db.add(inventory)
        db.flush()

    before_payload = {
        "stock_on_hand": inventory.stock_on_hand,
        "reserved_stock": inventory.reserved_stock,
        "available_stock": inventory.available_stock,
    }
    updates = request.model_dump(exclude_unset=True)
    if "stock_on_hand" in updates:
        inventory.stock_on_hand = updates["stock_on_hand"]
    if "reserved_stock" in updates:
        inventory.reserved_stock = updates["reserved_stock"]
    if inventory.stock_on_hand < 0 or inventory.reserved_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="inventory values must be greater than or equal to 0",
        )
    inventory.available_stock = inventory.stock_on_hand - inventory.reserved_stock
    db.add(
        AuditLog(
            actor=None,
            action="inventory.update",
            target_type="product_variant",
            target_id=variant.id,
            before_payload=before_payload,
            after_payload={
                "stock_on_hand": inventory.stock_on_hand,
                "reserved_stock": inventory.reserved_stock,
                "available_stock": inventory.available_stock,
            },
        )
    )
    db.commit()
    db.refresh(inventory)
    return InventoryResponse(
        stock_on_hand=inventory.stock_on_hand,
        reserved_stock=inventory.reserved_stock,
        available_stock=inventory.available_stock,
    )


@router.post("/{product_id}/reject", response_model=ProductSummaryResponse)
def reject_product(
    product_id: int,
    request: RejectProductRequest,
    db: Session = Depends(get_db),
) -> ProductSummaryResponse:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if product.status not in {"draft", "approved"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft or approved products can be rejected",
        )

    before_payload = {"status": product.status}
    product.status = "rejected"
    db.add(
        AuditLog(
            actor=None,
            action="product.reject",
            target_type="product",
            target_id=product.id,
            before_payload=before_payload,
            after_payload={"status": product.status, "reason": request.reason},
        )
    )
    db.commit()
    db.refresh(product)
    return product_summary_by_id(db, product.id)


@router.post("/{product_id}/archive", response_model=ProductSummaryResponse)
def archive_product(
    product_id: int,
    request: ArchiveProductRequest | None = None,
    db: Session = Depends(get_db),
) -> ProductSummaryResponse:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if product.status == "archived":
        return product_summary_by_id(db, product.id)

    before_payload = {"status": product.status}
    reason = request.reason if request else None
    product.status = "archived"
    db.add(
        AuditLog(
            actor=None,
            action="product.archive",
            target_type="product",
            target_id=product.id,
            before_payload=before_payload,
            after_payload={"status": product.status, "reason": reason},
        )
    )
    db.commit()
    db.refresh(product)
    return product_summary_by_id(db, product.id)
