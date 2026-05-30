from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    ImportBatch,
    ImportError,
    InventoryBalance,
    Product,
    ProductImage,
    ProductVariant,
)


REQUIRED_COLUMNS = [
    "product_group",
    "product_name",
    "color",
    "gender",
    "category",
    "price",
    "size",
    "waist",
    "hip",
    "length",
    "sku",
    "stock",
    "image_1",
    "status",
]

OPTIONAL_COLUMNS = [
    "sale_price",
    "barcode",
    "image_2",
    "image_3",
    "description",
    "note",
]

CSV_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
IMAGE_COLUMNS = ["image_1", "image_2", "image_3"]
DEFAULT_MEASUREMENT_LABELS = ("เอว", "สะโพก", "ความยาว")


@dataclass
class ProductRow:
    row_number: int
    product_group: str
    product_name: str
    color: str
    gender: str
    category: str
    price: Decimal
    sale_price: Decimal | None
    size: str
    waist: str
    hip: str
    length: str
    sku: str
    barcode: str
    stock: int
    image_1: str
    image_2: str
    image_3: str
    description: str | None
    note: str | None
    status: str


@dataclass
class RowImportError:
    row_number: int
    sku: str | None
    product_group: str | None
    error_message: str


@dataclass
class ImportStats:
    source_file: str
    total_rows: int = 0
    products_created: int = 0
    products_updated: int = 0
    variants_created: int = 0
    variants_updated: int = 0
    inventory_created: int = 0
    inventory_updated: int = 0
    images_created: int = 0
    errors: list[RowImportError] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import validated Product Master CSV rows into PostgreSQL."
    )
    parser.add_argument("--input", required=True, help="Path to validated CSV file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and summarize the import without writing to the database",
    )
    return parser.parse_args()


def parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("price fields must be numeric") from exc


def read_product_rows(input_path: Path) -> tuple[list[ProductRow], list[RowImportError]]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")

    product_rows: list[ProductRow] = []
    errors: list[RowImportError] = []

    with input_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        missing_columns = [column for column in CSV_COLUMNS if column not in headers]
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"CSV missing required Product Master columns: {missing}")

        for index, raw_row in enumerate(reader):
            row_number = index + 2
            row = {
                column: (raw_row.get(column) or "").strip() for column in CSV_COLUMNS
            }
            row_errors = validate_minimal_row(row)
            if row_errors:
                errors.append(
                    RowImportError(
                        row_number=row_number,
                        sku=row.get("sku") or None,
                        product_group=row.get("product_group") or None,
                        error_message="; ".join(row_errors),
                    )
                )
                continue

            try:
                product_rows.append(
                    ProductRow(
                        row_number=row_number,
                        product_group=row["product_group"],
                        product_name=row["product_name"],
                        color=row["color"],
                        gender=row["gender"],
                        category=row["category"],
                        price=parse_decimal(row["price"]),
                        sale_price=(
                            parse_decimal(row["sale_price"])
                            if row["sale_price"]
                            else None
                        ),
                        size=row["size"],
                        waist=row["waist"],
                        hip=row["hip"],
                        length=row["length"],
                        sku=row["sku"],
                        barcode=row["barcode"] or row["sku"],
                        stock=int(row["stock"]),
                        image_1=row["image_1"],
                        image_2=row["image_2"],
                        image_3=row["image_3"],
                        description=row["description"] or None,
                        note=row["note"] or None,
                        status=row["status"],
                    )
                )
            except ValueError as exc:
                errors.append(
                    RowImportError(
                        row_number=row_number,
                        sku=row.get("sku") or None,
                        product_group=row.get("product_group") or None,
                        error_message=str(exc),
                    )
                )

    return product_rows, errors


def validate_minimal_row(row: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for column in REQUIRED_COLUMNS:
        if not row[column]:
            errors.append(f"{column} is required")

    if row["price"]:
        try:
            parse_decimal(row["price"])
        except ValueError:
            errors.append("price must be numeric")

    if row["sale_price"]:
        try:
            parse_decimal(row["sale_price"])
        except ValueError:
            errors.append("sale_price must be numeric")

    if row["stock"]:
        try:
            int(row["stock"])
        except ValueError:
            errors.append("stock must be integer")

    return errors


def group_by_product(rows: Iterable[ProductRow]) -> dict[str, list[ProductRow]]:
    grouped: dict[str, list[ProductRow]] = defaultdict(list)
    for row in rows:
        grouped[row.product_group].append(row)
    return grouped


def unique_image_values(rows: Iterable[ProductRow]) -> list[tuple[str, int]]:
    seen: set[str] = set()
    images: list[tuple[str, int]] = []
    for row in rows:
        for position, column in enumerate(IMAGE_COLUMNS, start=1):
            url = getattr(row, column)
            if url and url not in seen:
                seen.add(url)
                images.append((url, position))
    return images


def calculate_dry_run_stats(
    session: Session,
    source_file: str,
    rows: list[ProductRow],
    row_errors: list[RowImportError],
) -> ImportStats:
    stats = ImportStats(
        source_file=source_file,
        total_rows=len(rows) + len(row_errors),
        errors=list(row_errors),
    )
    grouped_rows = group_by_product(rows)

    for product_group, product_rows in grouped_rows.items():
        product = session.scalar(
            select(Product).where(Product.product_group == product_group)
        )
        if product is None:
            stats.products_created += 1
            existing_image_urls: set[str] = set()
        else:
            stats.products_updated += 1
            existing_image_urls = set(
                session.scalars(
                    select(ProductImage.url).where(ProductImage.product_id == product.id)
                ).all()
            )

        for url, _position in unique_image_values(product_rows):
            if url not in existing_image_urls:
                stats.images_created += 1

    for row in rows:
        variant = session.scalar(select(ProductVariant).where(ProductVariant.sku == row.sku))
        if variant is None:
            stats.variants_created += 1
            stats.inventory_created += 1
            continue

        stats.variants_updated += 1
        inventory = session.scalar(
            select(InventoryBalance).where(InventoryBalance.variant_id == variant.id)
        )
        if inventory is None:
            stats.inventory_created += 1
        else:
            stats.inventory_updated += 1

    return stats


def upsert_product(session: Session, product_group: str, rows: list[ProductRow]) -> Product:
    first_row = rows[0]
    product = session.scalar(select(Product).where(Product.product_group == product_group))
    if product is None:
        product = Product(product_group=product_group)
        session.add(product)

    product.name = first_row.product_name
    product.color = first_row.color
    product.gender = first_row.gender
    product.category = first_row.category
    product.description = first_row.description
    product.note = first_row.note
    product.status = first_row.status
    return product


def upsert_images(session: Session, product: Product, rows: list[ProductRow]) -> int:
    existing_images = {
        image.url: image
        for image in session.scalars(
            select(ProductImage).where(ProductImage.product_id == product.id)
        ).all()
    }
    images_created = 0

    for url, position in unique_image_values(rows):
        image = existing_images.get(url)
        if image is None:
            session.add(ProductImage(product_id=product.id, url=url, position=position))
            images_created += 1
        else:
            image.position = position

    return images_created


def upsert_variant(session: Session, product: Product, row: ProductRow) -> ProductVariant:
    variant = session.scalar(select(ProductVariant).where(ProductVariant.sku == row.sku))
    if variant is None:
        variant = ProductVariant(sku=row.sku)
        session.add(variant)

    variant.product_id = product.id
    variant.size = row.size
    variant.waist = row.waist
    variant.hip = row.hip
    variant.length = row.length
    variant.measurements = [
        {"label": label, "value": value}
        for label, value in zip(
            DEFAULT_MEASUREMENT_LABELS,
            [row.waist, row.hip, row.length],
        )
        if value
    ]
    variant.barcode = row.barcode
    variant.price = row.price
    variant.sale_price = row.sale_price
    variant.status = row.status
    return variant


def upsert_inventory(session: Session, variant: ProductVariant, stock: int) -> InventoryBalance:
    inventory = session.scalar(
        select(InventoryBalance).where(InventoryBalance.variant_id == variant.id)
    )
    if inventory is None:
        inventory = InventoryBalance(
            variant_id=variant.id,
            stock_on_hand=stock,
            reserved_stock=0,
            available_stock=stock,
        )
        session.add(inventory)
        return inventory

    inventory.stock_on_hand = stock
    inventory.available_stock = stock - inventory.reserved_stock
    return inventory


def import_rows(
    session: Session,
    source_file: str,
    rows: list[ProductRow],
    row_errors: list[RowImportError],
) -> ImportStats:
    stats = ImportStats(
        source_file=source_file,
        total_rows=len(rows) + len(row_errors),
        errors=list(row_errors),
    )

    with session.begin():
        import_batch = ImportBatch(
            source_file=source_file,
            total_rows=stats.total_rows,
            valid_rows=len(rows),
            invalid_rows=len(row_errors),
            status="running",
        )
        session.add(import_batch)
        session.flush()

        for row_error in row_errors:
            session.add(
                ImportError(
                    import_batch_id=import_batch.id,
                    row_number=row_error.row_number,
                    sku=row_error.sku,
                    product_group=row_error.product_group,
                    error_message=row_error.error_message,
                )
            )

        for product_group, product_rows in group_by_product(rows).items():
            product_exists = session.scalar(
                select(Product.id).where(Product.product_group == product_group)
            )
            product = upsert_product(session, product_group, product_rows)
            session.flush()

            if product_exists is None:
                stats.products_created += 1
            else:
                stats.products_updated += 1

            stats.images_created += upsert_images(session, product, product_rows)

            for row in product_rows:
                try:
                    variant_exists = session.scalar(
                        select(ProductVariant.id).where(ProductVariant.sku == row.sku)
                    )
                    variant = upsert_variant(session, product, row)
                    session.flush()

                    if variant_exists is None:
                        stats.variants_created += 1
                    else:
                        stats.variants_updated += 1

                    inventory_exists = session.scalar(
                        select(InventoryBalance.id).where(
                            InventoryBalance.variant_id == variant.id
                        )
                    )
                    upsert_inventory(session, variant, row.stock)
                    if inventory_exists is None:
                        stats.inventory_created += 1
                    else:
                        stats.inventory_updated += 1
                except ValueError as exc:
                    row_error = RowImportError(
                        row_number=row.row_number,
                        sku=row.sku,
                        product_group=row.product_group,
                        error_message=str(exc),
                    )
                    stats.errors.append(row_error)
                    import_batch.invalid_rows += 1
                    import_batch.valid_rows -= 1
                    session.add(
                        ImportError(
                            import_batch_id=import_batch.id,
                            row_number=row_error.row_number,
                            sku=row_error.sku,
                            product_group=row_error.product_group,
                            error_message=row_error.error_message,
                        )
                    )

        import_batch.status = "completed_with_errors" if stats.errors else "completed"

    return stats


def print_thai_summary(stats: ImportStats, dry_run: bool) -> None:
    mode_label = "dry-run" if dry_run else "import"
    print(f"สรุปผล CSV {mode_label}")
    print(f"- source file: {stats.source_file}")
    print(f"- total rows: {stats.total_rows}")
    print(f"- products created: {stats.products_created}")
    print(f"- products updated: {stats.products_updated}")
    print(f"- variants created: {stats.variants_created}")
    print(f"- variants updated: {stats.variants_updated}")
    print(f"- inventory created: {stats.inventory_created}")
    print(f"- inventory updated: {stats.inventory_updated}")
    print(f"- images created: {stats.images_created}")
    print(f"- errors: {len(stats.errors)}")
    for error in stats.errors:
        print(
            f"  - row {error.row_number}, sku={error.sku or '-'}, "
            f"product_group={error.product_group or '-'}: {error.error_message}"
        )


def run_import(input_path: Path, dry_run: bool) -> int:
    rows, row_errors = read_product_rows(input_path)
    source_file = str(input_path)

    try:
        with SessionLocal() as session:
            if dry_run:
                stats = calculate_dry_run_stats(session, source_file, rows, row_errors)
            else:
                stats = import_rows(session, source_file, rows, row_errors)
    except SQLAlchemyError as exc:
        print("เกิด fatal error ระหว่าง import และ transaction ถูก rollback แล้ว")
        print(f"error: {exc}")
        return 1

    print_thai_summary(stats, dry_run=dry_run)
    return 0 if not stats.errors else 1


def main() -> int:
    args = parse_args()
    try:
        return run_import(Path(args.input), dry_run=args.dry_run)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
