from __future__ import annotations

import importlib.util
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.commands.import_products import (
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
    root = repo_root()
    upload_dir = root / "data" / "input" / "uploads"
    output_dir = root / "data" / "output" / "frontend_imports" / timestamp
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"{timestamp}_{safe_uploaded_filename(file.filename)}"

    with upload_path.open("wb") as output_file:
        shutil.copyfileobj(file.file, output_file)

    validator = load_validator_module()
    rows, missing_columns = validator.read_rows(upload_path)
    row_errors: dict[int, list[str]] = defaultdict(list)
    row_warnings: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        errors, warnings = validator.validate_row_fields(row["data"], missing_columns)
        row_errors[row["index"]].extend(errors)
        row_warnings[row["index"]].extend(warnings)
    validator.add_uniqueness_errors(rows, row_errors)
    validator.add_product_group_consistency_errors(rows, row_errors)
    summary = validator.write_outputs(upload_path, output_dir, rows, row_errors, row_warnings)
    return CsvValidationResponse(**summary)


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
