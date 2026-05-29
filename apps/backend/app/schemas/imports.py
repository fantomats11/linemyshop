from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ImportBatchResponse(BaseModel):
    id: int
    source_file: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportErrorResponse(BaseModel):
    id: int
    import_batch_id: int
    row_number: int
    sku: str | None
    product_group: str | None
    error_message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CsvValidationResponse(BaseModel):
    input_file: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    total_errors: int
    total_warnings: int
    output_files: dict[str, str]


class RunImportRequest(BaseModel):
    valid_products_path: str
    dry_run: bool = False


class RunImportResponse(BaseModel):
    source_file: str
    total_rows: int
    products_created: int
    products_updated: int
    variants_created: int
    variants_updated: int
    inventory_created: int
    inventory_updated: int
    images_created: int
    errors: list[dict[str, str | int | None]]
