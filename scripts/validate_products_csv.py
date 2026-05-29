#!/usr/bin/env python3
"""Validate Product Master CSV files and write validation outputs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


MASTER_COLUMNS = [
    "product_group",
    "product_name",
    "color",
    "gender",
    "category",
    "price",
    "sale_price",
    "size",
    "waist",
    "hip",
    "length",
    "sku",
    "barcode",
    "stock",
    "image_1",
    "image_2",
    "image_3",
    "description",
    "note",
    "status",
]

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

VALID_STATUSES = {"draft", "active", "inactive", "approved", "rejected", "archived"}
VALID_SIZES = {"M", "L", "XL", "XXL", "2XL", "3XL"}
GROUP_CONSISTENCY_FIELDS = [
    "product_name",
    "color",
    "gender",
    "category",
    "price",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a LINE MyShop Product Master CSV file."
    )
    parser.add_argument("--input", required=True, help="Path to input CSV file")
    parser.add_argument(
        "--output-dir", required=True, help="Directory for validation output files"
    )
    return parser.parse_args()


def trim_row(row: dict[str, Any]) -> dict[str, str]:
    trimmed: dict[str, str] = {}
    for column in MASTER_COLUMNS:
        value = row.get(column, "")
        trimmed[column] = "" if value is None else str(value).strip()
    return trimmed


def parse_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


def validate_numeric_fields(row: dict[str, str], errors: list[str]) -> None:
    price = parse_decimal(row["price"])
    if price is None:
        errors.append("price must be numeric")
    elif price <= 0:
        errors.append("price must be greater than 0")

    sale_price_value = row["sale_price"]
    if sale_price_value:
        sale_price = parse_decimal(sale_price_value)
        if sale_price is None:
            errors.append("sale_price must be numeric")
        elif price is not None and sale_price > price:
            errors.append("sale_price must be less than or equal to price")

    try:
        stock = int(row["stock"])
    except ValueError:
        errors.append("stock must be integer")
    else:
        if stock < 0:
            errors.append("stock must be greater than or equal to 0")


def validate_row_fields(
    row: dict[str, str],
    missing_columns: list[str],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for column in missing_columns:
        errors.append(f"missing column: {column}")

    for column in REQUIRED_COLUMNS:
        if not row[column]:
            errors.append(f"{column} is required")

    validate_numeric_fields(row, errors)

    if row["status"] and row["status"] not in VALID_STATUSES:
        errors.append(
            "status must be one of: draft, active, inactive, approved, rejected, archived"
        )

    if row["size"] and row["size"] not in VALID_SIZES:
        errors.append("size must be one of: M, L, XL, XXL, 2XL, 3XL")

    if not row["barcode"]:
        warnings.append("barcode empty, sku will be used")

    return errors, warnings


def add_uniqueness_errors(
    rows: list[dict[str, Any]],
    row_errors: dict[int, list[str]],
) -> None:
    sku_counts = Counter(row["data"]["sku"] for row in rows if row["data"]["sku"])
    barcode_counts = Counter(
        row["data"]["barcode"] for row in rows if row["data"]["barcode"]
    )

    for row in rows:
        index = row["index"]
        sku = row["data"]["sku"]
        barcode = row["data"]["barcode"]
        if sku and sku_counts[sku] > 1:
            row_errors[index].append("sku must be unique")
        if barcode and barcode_counts[barcode] > 1:
            row_errors[index].append("barcode must be unique")


def add_product_group_consistency_errors(
    rows: list[dict[str, Any]],
    row_errors: dict[int, list[str]],
) -> None:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        product_group = row["data"]["product_group"]
        if product_group:
            groups[product_group].append(row)

    for product_group_rows in groups.values():
        expected: dict[str, str] = {}
        for field in GROUP_CONSISTENCY_FIELDS:
            non_empty_values = [
                row["data"][field] for row in product_group_rows if row["data"][field]
            ]
            expected[field] = non_empty_values[0] if non_empty_values else ""

        for row in product_group_rows:
            for field, expected_value in expected.items():
                actual_value = row["data"][field]
                if actual_value and expected_value and actual_value != expected_value:
                    row_errors[row["index"]].append(
                        f"{field} must be consistent within product_group"
                    )


def read_rows(input_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    with input_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        missing_columns = [column for column in MASTER_COLUMNS if column not in headers]
        rows = []
        for index, row in enumerate(reader):
            rows.append(
                {
                    "index": index,
                    "row_number": index + 2,
                    "data": trim_row(row),
                }
            )
    return rows, missing_columns


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(
    input_path: Path,
    output_dir: Path,
    rows: list[dict[str, Any]],
    row_errors: dict[int, list[str]],
    row_warnings: dict[int, list[str]],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    valid_path = output_dir / "valid_products.csv"
    invalid_path = output_dir / "invalid_products.csv"
    report_path = output_dir / "validation_report.csv"
    summary_path = output_dir / "validation_summary.json"

    valid_rows: list[dict[str, str]] = []
    invalid_rows: list[dict[str, str]] = []
    report_rows: list[dict[str, str]] = []

    for row in rows:
        index = row["index"]
        data = row["data"]
        errors = row_errors[index]
        warnings = row_warnings[index]
        if errors:
            invalid_rows.append(data)
            status = "invalid"
        else:
            valid_rows.append(data)
            status = "valid"

        report_rows.append(
            {
                "row_number": str(row["row_number"]),
                "sku": data["sku"],
                "product_group": data["product_group"],
                "status": status,
                "errors": "; ".join(errors),
                "warnings": "; ".join(warnings),
            }
        )

    write_csv(valid_path, MASTER_COLUMNS, valid_rows)
    write_csv(invalid_path, MASTER_COLUMNS, invalid_rows)
    write_csv(
        report_path,
        ["row_number", "sku", "product_group", "status", "errors", "warnings"],
        report_rows,
    )

    summary = {
        "input_file": str(input_path),
        "total_rows": len(rows),
        "valid_rows": len(valid_rows),
        "invalid_rows": len(invalid_rows),
        "total_errors": sum(len(errors) for errors in row_errors.values()),
        "total_warnings": sum(len(warnings) for warnings in row_warnings.values()),
        "output_files": {
            "valid_products": str(valid_path),
            "invalid_products": str(invalid_path),
            "validation_report": str(report_path),
            "validation_summary": str(summary_path),
        },
    }

    with summary_path.open("w", encoding="utf-8") as json_file:
        json.dump(summary, json_file, ensure_ascii=False, indent=2)
        json_file.write("\n")

    return summary


def print_thai_summary(summary: dict[str, Any]) -> None:
    print("สรุปผลการตรวจสอบ CSV")
    print(f"- จำนวนแถวทั้งหมด: {summary['total_rows']}")
    print(f"- จำนวนแถวที่ถูกต้อง: {summary['valid_rows']}")
    print(f"- จำนวนแถวที่ผิด: {summary['invalid_rows']}")
    print(f"- จำนวน error: {summary['total_errors']}")
    print(f"- จำนวน warning: {summary['total_warnings']}")
    print("- ไฟล์ output:")
    for path in summary["output_files"].values():
        print(f"  - {path}")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")
    if not input_path.is_file():
        raise SystemExit(f"Input path is not a file: {input_path}")

    rows, missing_columns = read_rows(input_path)
    row_errors: dict[int, list[str]] = defaultdict(list)
    row_warnings: dict[int, list[str]] = defaultdict(list)

    for row in rows:
        errors, warnings = validate_row_fields(row["data"], missing_columns)
        row_errors[row["index"]].extend(errors)
        row_warnings[row["index"]].extend(warnings)

    add_uniqueness_errors(rows, row_errors)
    add_product_group_consistency_errors(rows, row_errors)

    summary = write_outputs(input_path, output_dir, rows, row_errors, row_warnings)
    print_thai_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
