from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import ChannelProduct, Product, ProductImage


router = APIRouter(prefix="/maintenance", tags=["maintenance"])

BACKFILL_PRODUCTS: dict[str, dict[str, Any]] = {
    "jeans-winter-flare-dark-2547": {
        "external_product_id": "1008103180",
        "is_display": False,
        "images": [
            ("https://gomall.fashion/wp-content/uploads/2026/05/01-hero-square.png", "product", 1, True),
            ("https://gomall.fashion/wp-content/uploads/2026/05/02-detail-closeup.png", "detail", 2, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/03-back-view.png", "product", 3, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/04-lifestyle-model-waist-down.png", "lifestyle", 4, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/05-size-guide.png", "size_chart", 5, False),
        ],
    },
    "jeans-winter-flare-light-2543": {
        "external_product_id": "1008103239",
        "is_display": False,
        "images": [
            ("https://gomall.fashion/wp-content/uploads/2026/05/01-hero-square-1.png", "product", 1, True),
            ("https://gomall.fashion/wp-content/uploads/2026/05/02-detail-closeup-1.png", "detail", 2, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/03-back-view-1.png", "product", 3, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/04-lifestyle-model-waist-down-1.png", "lifestyle", 4, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/05-size-guide.png", "size_chart", 5, False),
        ],
    },
    "jeans-winter-flare-dark-2555": {
        "external_product_id": "1008103281",
        "is_display": False,
        "images": [
            ("https://gomall.fashion/wp-content/uploads/2026/05/01-hero-square.png", "product", 1, True),
            ("https://gomall.fashion/wp-content/uploads/2026/05/02-detail-closeup.png", "detail", 2, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/03-back-view.png", "product", 3, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/04-lifestyle-model-waist-down.png", "lifestyle", 4, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/size-guide-jeans-hip40-length37.png", "size_chart", 5, False),
        ],
    },
    "jeans-winter-flare-dark-2551": {
        "external_product_id": "1008103282",
        "is_display": False,
        "images": [
            ("https://gomall.fashion/wp-content/uploads/2026/05/01-hero-square.png", "product", 1, True),
            ("https://gomall.fashion/wp-content/uploads/2026/05/02-detail-closeup.png", "detail", 2, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/03-back-view.png", "product", 3, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/04-lifestyle-model-waist-down.png", "lifestyle", 4, False),
            ("https://gomall.fashion/wp-content/uploads/2026/05/size-guide-jeans-hip40-length37.png", "size_chart", 5, False),
        ],
    },
}


@router.post("/backfill-existing-line-products")
def backfill_existing_line_products(db: Session = Depends(get_db)) -> dict[str, Any]:
    synced_at = datetime.now(timezone.utc)
    updated_products: list[str] = []
    created_images = 0
    updated_images = 0

    for product_group, payload in BACKFILL_PRODUCTS.items():
        product = db.scalar(select(Product).where(Product.product_group == product_group))
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product not found: {product_group}",
            )

        product.status = "approved"
        channel_product = db.scalar(
            select(ChannelProduct).where(
                ChannelProduct.product_id == product.id,
                ChannelProduct.channel == "line_myshop",
            )
        )
        if channel_product is None:
            channel_product = ChannelProduct(
                product_id=product.id,
                channel="line_myshop",
            )
            db.add(channel_product)

        channel_product.external_product_id = payload["external_product_id"]
        channel_product.sync_status = "success"
        channel_product.last_synced_at = synced_at
        channel_product.last_refreshed_at = synced_at
        channel_product.is_display = payload["is_display"]
        channel_product.line_payload = {
            "id": payload["external_product_id"],
            "isDisplay": payload["is_display"],
            "source": "production-backfill",
        }

        for url, image_type, position, is_main in payload["images"]:
            image = db.scalar(
                select(ProductImage).where(
                    ProductImage.product_id == product.id,
                    ProductImage.url == url,
                )
            )
            if image is None:
                image = ProductImage(product_id=product.id, url=url)
                db.add(image)
                created_images += 1
            else:
                updated_images += 1

            image.image_type = image_type
            image.position = position
            image.status = "approved"
            image.is_main = is_main
            image.review_note = "backfilled from existing LINE MyShop product"

        updated_products.append(product_group)

    db.commit()
    return {
        "updated_products": updated_products,
        "created_images": created_images,
        "updated_images": updated_images,
    }
