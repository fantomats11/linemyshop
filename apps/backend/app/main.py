from fastapi import FastAPI

from app.api.imports import router as imports_router
from app.api.products import (
    image_generation_router,
    image_router,
    router as products_router,
    variant_router,
)
from app.api.sync import router as sync_router
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(products_router)
app.include_router(image_router)
app.include_router(variant_router)
app.include_router(image_generation_router)
app.include_router(imports_router)
app.include_router(sync_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "line-myshop-product-master-backend"}
