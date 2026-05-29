from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


VALID_IMAGE_TYPES = {"product", "lifestyle", "detail", "size_chart", "brief"}
LINE_STOREFRONT_IMAGE_TYPES = {"product", "lifestyle", "detail", "size_chart"}
LINE_STOREFRONT_MAX_IMAGES = 7


class ProductImageResponse(BaseModel):
    id: int
    url: str
    position: int
    status: str
    image_type: str
    is_main: bool
    review_note: str | None

    model_config = ConfigDict(from_attributes=True)


class ProductImageSetResponse(BaseModel):
    product_id: int
    max_images: int
    ready: bool
    errors: list[str]
    warnings: list[str]
    images: list[ProductImageResponse]


class ImageGenerationSlotResponse(BaseModel):
    position: int
    image_type: str
    title: str
    prompt: str
    required: bool


class ProductImageGenerationBriefResponse(BaseModel):
    product_id: int
    ready: bool
    errors: list[str]
    warnings: list[str]
    reference_images: list[ProductImageResponse]
    slots: list[ImageGenerationSlotResponse]


class ImageGenerationJobResponse(BaseModel):
    id: int
    product_id: int
    status: str
    mode: str
    prompt_payload: dict
    result_payload: dict | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class RunImageGenerationJobRequest(BaseModel):
    slot_positions: list[int] | None = None
    quality: str | None = None
    image_size: str | None = None
    output_format: str | None = None
    num_images_per_slot: int = 1
    approve: bool = False
    set_main_position: int = 1


class InventoryResponse(BaseModel):
    stock_on_hand: int
    reserved_stock: int
    available_stock: int

    model_config = ConfigDict(from_attributes=True)


class ProductVariantResponse(BaseModel):
    id: int
    sku: str
    barcode: str | None
    size: str
    waist: str
    hip: str
    length: str
    price: Decimal
    sale_price: Decimal | None
    status: str
    inventory: InventoryResponse | None

    model_config = ConfigDict(from_attributes=True)


class ProductSummaryResponse(BaseModel):
    id: int
    product_group: str
    name: str
    color: str
    gender: str
    category: str
    status: str
    variant_count: int
    total_stock: int
    image_url: str | None
    created_at: datetime
    updated_at: datetime
    external_product_id: str | None = None
    sync_status: str | None = None
    last_synced_at: datetime | None = None
    is_display: bool | None = None
    line_last_refreshed_at: datetime | None = None


class ProductDetailResponse(BaseModel):
    id: int
    product_group: str
    name: str
    color: str
    gender: str
    category: str
    description: str | None
    note: str | None
    status: str
    images: list[ProductImageResponse]
    variants: list[ProductVariantResponse]
    external_product_id: str | None = None
    sync_status: str | None = None
    last_synced_at: datetime | None = None
    is_display: bool | None = None
    line_last_refreshed_at: datetime | None = None


class RejectProductRequest(BaseModel):
    reason: str


class ArchiveProductRequest(BaseModel):
    reason: str | None = None


class CreateProductImageRequest(BaseModel):
    url: str
    image_type: str
    position: int


class BulkCreateProductImagesRequest(BaseModel):
    images: list[CreateProductImageRequest]


class ReorderProductImageItem(BaseModel):
    image_id: int
    position: int
    is_main: bool = False


class ReorderProductImagesRequest(BaseModel):
    images: list[ReorderProductImageItem]


class ReviewProductImageRequest(BaseModel):
    review_note: str | None = None


class UpdateProductRequest(BaseModel):
    name: str | None = None
    color: str | None = None
    gender: str | None = None
    category: str | None = None
    description: str | None = None
    note: str | None = None


class UpdateProductVariantRequest(BaseModel):
    barcode: str | None = None
    size: str | None = None
    waist: str | None = None
    hip: str | None = None
    length: str | None = None
    price: Decimal | None = None
    sale_price: Decimal | None = None
    status: str | None = None


class UpdateInventoryRequest(BaseModel):
    stock_on_hand: int | None = None
    reserved_stock: int | None = None


class CreateProductVariantRequest(BaseModel):
    sku: str
    barcode: str | None = None
    size: str
    waist: str
    hip: str
    length: str
    price: Decimal
    sale_price: Decimal | None = None
    stock_on_hand: int = 0
    reserved_stock: int = 0
    status: str = "draft"


class CreateProductRequest(BaseModel):
    product_group: str
    name: str
    color: str
    gender: str
    category: str
    description: str | None = None
    note: str | None = None
    status: str = "draft"
    variants: list[CreateProductVariantRequest]
