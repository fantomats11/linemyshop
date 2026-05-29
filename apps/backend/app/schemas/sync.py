from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ProductSyncRequest(BaseModel):
    confirm: str | None = None


class ProductLineVisibilityRequest(BaseModel):
    confirm: str | None = None
    reason: str | None = None


class ProductSyncReadinessResponse(BaseModel):
    product_id: int
    ready: bool
    mock_mode: bool
    errors: list[str]
    warnings: list[str]


class ProductSyncPreviewResponse(BaseModel):
    product_id: int
    ready: bool
    mock_mode: bool
    action: str
    endpoint: str
    method: str
    errors: list[str]
    warnings: list[str]
    internal_payload: dict[str, Any]
    outbound_payload: dict[str, Any] | None


class ProductSyncResponse(BaseModel):
    product_id: int
    sync_job_id: int
    status: str
    mock_mode: bool
    external_product_id: str | None
    variants_synced: int
    warnings: list[str]
    message: str


class ProductLineStatusResponse(BaseModel):
    product_id: int
    sync_job_id: int | None = None
    status: str
    mock_mode: bool
    external_product_id: str
    is_display: bool | None
    message: str
    warnings: list[str] = []


class SyncJobResponse(BaseModel):
    id: int
    job_type: str
    target_type: str
    target_id: int
    status: str
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
