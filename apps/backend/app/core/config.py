from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LINE MyShop Product Master API"
    app_env: str = "local"
    database_url: str = (
        "postgresql+psycopg://app:app_password@localhost:5432/line_myshop"
    )
    line_myshop_mock_mode: bool = True
    line_myshop_base_url: str = ""
    line_myshop_api_key: str = ""
    line_myshop_api_key_header: str = "X-API-KEY"
    line_myshop_timeout_seconds: float = 15.0
    line_myshop_create_product_path: str = "/myshop/v1/products"
    line_myshop_update_product_path: str = "/myshop/v1/products/{external_product_id}"
    line_myshop_update_inventory_path: str = ""
    line_myshop_update_price_path: str = ""
    line_myshop_default_category_id: int | None = None
    line_myshop_default_brand: str = ""
    line_myshop_default_weight: int = 1
    line_myshop_separate_variant_sync: bool = False
    wordpress_base_url: str = ""
    wordpress_username: str = ""
    wordpress_application_password: str = ""
    image_generation_provider: str = "manual"
    fal_key: str = ""
    fal_image_model: str = "openai/gpt-image-2/edit"
    fal_image_quality: str = "medium"
    fal_image_size: str = "square"
    fal_image_format: str = "jpeg"
    fal_timeout_seconds: float = 180.0

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
