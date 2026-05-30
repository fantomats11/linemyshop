from __future__ import annotations

import importlib.util
import shutil
from tempfile import TemporaryDirectory
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.commands.import_products import (
    RowImportError,
    calculate_dry_run_stats,
    import_rows,
    read_product_rows,
)
from app.core.paths import workspace_root
from app.models import ImportBatch, ImportError
from app.schemas.imports import (
    CsvValidationResponse,
    ImportBatchResponse,
    ImportErrorResponse,
    RunImportRequest,
    RunImportResponse,
)


router = APIRouter(prefix="/imports", tags=["imports"])


def repo_root() -> Path:
    return workspace_root()


def load_validator_module() -> Any:
    validator_path = Path(__file__).resolve().parents[1] / "services" / "product_csv_validator.py"
    spec = importlib.util.spec_from_file_location(
        "product_csv_validator", validator_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load CSV validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_uploaded_filename(filename: str) -> str:
    return Path(filename).name.replace(" ", "_")


def assert_path_inside_repo(path: Path) -> Path:
    root = repo_root().resolve()
    resolved = path.resolve()
    if root != resolved and root not in resolved.parents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="path must be inside project workspace",
        )
    return resolved


def validate_csv_to_outputs(
    input_path: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], dict[int, list[str]]]:
    validator = load_validator_module()
    rows, missing_columns = validator.read_rows(input_path)
    row_errors: dict[int, list[str]] = defaultdict(list)
    row_warnings: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        errors, warnings = validator.validate_row_fields(row["data"], missing_columns)
        row_errors[row["index"]].extend(errors)
        row_warnings[row["index"]].extend(warnings)
    validator.add_uniqueness_errors(rows, row_errors)
    validator.add_product_group_consistency_errors(rows, row_errors)
    summary = validator.write_outputs(
        input_path,
        output_dir,
        rows,
        row_errors,
        row_warnings,
    )
    return summary, row_errors


def row_import_errors_from_validation(
    valid_products_path: Path,
    row_errors: dict[int, list[str]],
) -> list[RowImportError]:
    validator = load_validator_module()
    rows, _missing_columns = validator.read_rows(valid_products_path)
    return [
        RowImportError(
            row_number=row["row_number"],
            sku=row["data"].get("sku") or None,
            product_group=row["data"].get("product_group") or None,
            error_message="; ".join(row_errors[row["index"]]),
        )
        for row in rows
        if row_errors[row["index"]]
    ]


@router.get("", response_model=list[ImportBatchResponse])
def list_imports(db: Session = Depends(get_db)) -> list[ImportBatch]:
    return list(
        db.scalars(
            select(ImportBatch).order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        ).all()
    )


@router.get("/{import_batch_id}/errors", response_model=list[ImportErrorResponse])
def list_import_errors(
    import_batch_id: int, db: Session = Depends(get_db)
) -> list[ImportError]:
    import_batch = db.get(ImportBatch, import_batch_id)
    if import_batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import batch not found",
        )

    return list(
        db.scalars(
            select(ImportError)
            .where(ImportError.import_batch_id == import_batch_id)
            .order_by(ImportError.row_number, ImportError.id)
        ).all()
    )


@router.post("/validate-csv", response_model=CsvValidationResponse)
def validate_import_csv(
    file: UploadFile = File(...),
) -> CsvValidationResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="CSV file is required",
        )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    with TemporaryDirectory(prefix="line-myshop-validate-") as temp_dir:
        temp_root = Path(temp_dir)
        upload_path = temp_root / f"{timestamp}_{safe_uploaded_filename(file.filename)}"
        output_dir = temp_root / "validated"

        with upload_path.open("wb") as output_file:
            shutil.copyfileobj(file.file, output_file)

        summary, _row_errors = validate_csv_to_outputs(upload_path, output_dir)
    return CsvValidationResponse(**summary)


@router.post("/run-csv", response_model=RunImportResponse)
def run_uploaded_import_csv(
    file: UploadFile = File(...),
    dry_run: bool = Form(default=False),
    db: Session = Depends(get_db),
) -> RunImportResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="CSV file is required",
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    with TemporaryDirectory(prefix="line-myshop-import-") as temp_dir:
        temp_root = Path(temp_dir)
        upload_path = temp_root / f"{timestamp}_{safe_uploaded_filename(file.filename)}"
        output_dir = temp_root / "validated"
        with upload_path.open("wb") as output_file:
            shutil.copyfileobj(file.file, output_file)

        summary, row_errors_by_index = validate_csv_to_outputs(upload_path, output_dir)
        if summary["invalid_rows"] > 0 and not dry_run:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="CSV has invalid rows; fix validation errors before importing",
            )

        valid_products_path = Path(summary["output_files"]["valid_products"])
        rows, row_errors = read_product_rows(valid_products_path)
        validation_errors = row_import_errors_from_validation(upload_path, row_errors_by_index)
        all_errors = validation_errors + row_errors
        source_file = safe_uploaded_filename(file.filename)
        if dry_run:
            stats = calculate_dry_run_stats(db, source_file, rows, all_errors)
        else:
            if db.in_transaction():
                db.rollback()
            stats = import_rows(db, source_file, rows, all_errors)

    return RunImportResponse(
        source_file=stats.source_file,
        total_rows=stats.total_rows,
        products_created=stats.products_created,
        products_updated=stats.products_updated,
        variants_created=stats.variants_created,
        variants_updated=stats.variants_updated,
        inventory_created=stats.inventory_created,
        inventory_updated=stats.inventory_updated,
        images_created=stats.images_created,
        errors=[
            {
                "row_number": error.row_number,
                "sku": error.sku,
                "product_group": error.product_group,
                "error_message": error.error_message,
            }
            for error in stats.errors
        ],
    )


@router.post("/run", response_model=RunImportResponse)
def run_validated_import(
    request: RunImportRequest,
    db: Session = Depends(get_db),
) -> RunImportResponse:
    input_path = assert_path_inside_repo(Path(request.valid_products_path))
    rows, row_errors = read_product_rows(input_path)
    if request.dry_run:
        stats = calculate_dry_run_stats(db, str(input_path), rows, row_errors)
    else:
        if db.in_transaction():
            db.rollback()
        stats = import_rows(db, str(input_path), rows, row_errors)

    return RunImportResponse(
        source_file=stats.source_file,
        total_rows=stats.total_rows,
        products_created=stats.products_created,
        products_updated=stats.products_updated,
        variants_created=stats.variants_created,
        variants_updated=stats.variants_updated,
        inventory_created=stats.inventory_created,
        inventory_updated=stats.inventory_updated,
        images_created=stats.images_created,
        errors=[
            {
                "row_number": error.row_number,
                "sku": error.sku,
                "product_group": error.product_group,
                "error_message": error.error_message,
            }
            for error in stats.errors
        ],
    )
