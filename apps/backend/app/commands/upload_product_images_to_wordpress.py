from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuditLog, Product, ProductImage
from app.schemas.products import LINE_STOREFRONT_MAX_IMAGES, VALID_IMAGE_TYPES
from app.services.wordpress_client import WordPressMediaClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload product image files to WordPress Media and register them on a product."
    )
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument(
        "--image-types",
        nargs="*",
        help="Image types for each file. Defaults to product for the first file and detail for the rest.",
    )
    parser.add_argument("--approve", action="store_true")
    parser.add_argument(
        "--set-main-index",
        type=int,
        default=1,
        help="1-based uploaded file index to set as main when --approve is used. Use 0 to skip.",
    )
    parser.add_argument("--review-note", default="uploaded to WordPress Media")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def resolve_image_types(file_count: int, image_types: list[str] | None) -> list[str]:
    if image_types:
        if len(image_types) != file_count:
            raise ValueError("--image-types must have the same count as --files")
        resolved = image_types
    else:
        resolved = ["product"] + ["detail"] * (file_count - 1)

    for image_type in resolved:
        if image_type not in VALID_IMAGE_TYPES or image_type == "brief":
            raise ValueError(
                "image types must be one of: product, lifestyle, detail, size_chart"
            )
    return resolved


def next_position(session: Session, product_id: int) -> int:
    positions = session.scalars(
        select(ProductImage.position).where(ProductImage.product_id == product_id)
    ).all()
    if not positions:
        return 1
    return max(positions) + 1


def run_upload(args: argparse.Namespace) -> None:
    file_paths = [Path(value).expanduser().resolve() for value in args.files]
    image_types = resolve_image_types(len(file_paths), args.image_types)
    if len(file_paths) > LINE_STOREFRONT_MAX_IMAGES:
        raise ValueError("LINE MyShop supports at most 7 storefront images")
    if args.set_main_index < 0 or args.set_main_index > len(file_paths):
        raise ValueError("--set-main-index must be between 0 and the number of files")

    settings = get_settings()
    client = WordPressMediaClient(settings)

    with SessionLocal() as session:
        product = session.get(Product, args.product_id)
        if product is None:
            raise ValueError(f"product not found: {args.product_id}")

        start_position = next_position(session, product.id)
        uploads: list[tuple[Path, str, str | None]] = []

        print("สรุปไฟล์ที่จะอัปโหลด")
        print(f"- product_id: {product.id}")
        for index, (file_path, image_type) in enumerate(
            zip(file_paths, image_types), start=1
        ):
            position = start_position + index - 1
            print(f"- #{index} position={position} type={image_type} file={file_path}")

        if args.dry_run:
            print("dry-run: ยังไม่อัปโหลดและยังไม่เขียน database")
            return

        for file_path, image_type in zip(file_paths, image_types):
            response = client.upload_media(file_path)
            uploads.append((file_path, image_type, response["source_url"]))

        if args.approve and args.set_main_index:
            existing_main_images = session.scalars(
                select(ProductImage)
                .where(ProductImage.product_id == product.id)
                .where(ProductImage.is_main.is_(True))
            ).all()
            for image in existing_main_images:
                image.is_main = False

        created_images: list[ProductImage] = []
        for index, (file_path, image_type, source_url) in enumerate(uploads, start=1):
            image = ProductImage(
                product_id=product.id,
                url=source_url,
                image_type=image_type,
                position=start_position + index - 1,
                status="approved" if args.approve else "draft",
                is_main=args.approve and args.set_main_index == index and image_type == "product",
                review_note=args.review_note if args.approve else None,
            )
            session.add(image)
            created_images.append(image)

        session.flush()
        session.add(
            AuditLog(
                actor=None,
                action="product_image.wordpress_upload_batch",
                target_type="product",
                target_id=product.id,
                before_payload=None,
                after_payload={
                    "images": [
                        {
                            "id": image.id,
                            "url": image.url,
                            "image_type": image.image_type,
                            "position": image.position,
                            "status": image.status,
                            "is_main": image.is_main,
                        }
                        for image in created_images
                    ]
                },
            )
        )
        session.commit()

        print("อัปโหลดและบันทึกเข้าระบบแล้ว")
        for image in created_images:
            print(
                f"- image_id={image.id} position={image.position} "
                f"type={image.image_type} main={image.is_main} url={image.url}"
            )


def main() -> None:
    args = parse_args()
    run_upload(args)


if __name__ == "__main__":
    main()
