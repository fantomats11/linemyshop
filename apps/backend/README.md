# Backend

FastAPI backend for the LINE MyShop Product Master system.

## Setup

From the repository root:

```bash
cp .env.example .env
make install
make db-up
make migrate
make dev
```

If `uv` is not available, `make install` creates `apps/backend/.venv` and installs dependencies with `pip`.

## Useful Commands

```bash
make install
make db-up
make migrate
make dev
make test
```

## Manual Dependency Commands

With `uv`:

```bash
cd apps/backend
uv sync --dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest
```

With `pip` and `venv`:

```bash
cd apps/backend
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
pytest
```

## Health Check

```bash
curl http://127.0.0.1:8000/health
```

## Import Validated Product CSV

From `apps/backend`:

```bash
python -m app.commands.import_products \
  --input ../../data/output/valid_products.csv \
  --dry-run
```

```bash
python -m app.commands.import_products \
  --input ../../data/output/valid_products.csv
```

## Product Preview and Approval APIs

```bash
curl http://127.0.0.1:8000/products
```

```bash
curl "http://127.0.0.1:8000/products?include_archived=true"
```

```bash
curl http://127.0.0.1:8000/products/1
```

```bash
curl -X POST http://127.0.0.1:8000/products/1/approve
```

```bash
curl -X POST http://127.0.0.1:8000/products/1/reject \
  -H "Content-Type: application/json" \
  -d '{"reason":"ข้อมูลสินค้ายังไม่พร้อม"}'
```

```bash
curl -X POST http://127.0.0.1:8000/products/1/archive \
  -H "Content-Type: application/json" \
  -d '{"reason":"sample/test data from initial CSV"}'
```

```bash
curl http://127.0.0.1:8000/imports
```

```bash
curl http://127.0.0.1:8000/imports/1/errors
```

## Mock LINE MyShop Sync

Mock mode is enabled by default through these settings:

```text
LINE_MYSHOP_MOCK_MODE=true
LINE_MYSHOP_BASE_URL=
LINE_MYSHOP_API_KEY=
LINE_MYSHOP_TIMEOUT_SECONDS=15
LINE_MYSHOP_CREATE_PRODUCT_PATH=/products
LINE_MYSHOP_UPDATE_PRODUCT_PATH=/products/{external_product_id}
LINE_MYSHOP_UPDATE_INVENTORY_PATH=/variants/{external_variant_id}/inventory
LINE_MYSHOP_UPDATE_PRICE_PATH=/variants/{external_variant_id}/price
```

Run migrations:

```bash
make migrate
```

Approve a product:

```bash
curl -X POST http://127.0.0.1:8000/products/1/approve
```

Sync an approved product in mock mode:

```bash
curl -X POST http://127.0.0.1:8000/products/1/sync
```

Check readiness and preview payload:

```bash
curl http://127.0.0.1:8000/products/1/sync-readiness
```

```bash
curl -X POST http://127.0.0.1:8000/products/1/sync/preview
```

List sync jobs:

```bash
curl http://127.0.0.1:8000/sync-jobs
```

Get a sync job:

```bash
curl http://127.0.0.1:8000/sync-jobs/1
```

## Real LINE MyShop API Adapter

The backend is ready to switch from mock mode to a configured LINE MyShop API adapter. Keep mock mode enabled until the official endpoint contract and real credentials are available.

Set these values in `.env`:

```text
LINE_MYSHOP_MOCK_MODE=false
LINE_MYSHOP_BASE_URL=https://developers-oaplus.line.biz
LINE_MYSHOP_API_KEY=replace-with-real-api-key
LINE_MYSHOP_API_KEY_HEADER=X-API-KEY
LINE_MYSHOP_TIMEOUT_SECONDS=15
LINE_MYSHOP_CREATE_PRODUCT_PATH=/myshop/v1/products
LINE_MYSHOP_UPDATE_PRODUCT_PATH=/myshop/v1/products/{external_product_id}
LINE_MYSHOP_UPDATE_INVENTORY_PATH=
LINE_MYSHOP_UPDATE_PRICE_PATH=
LINE_MYSHOP_DEFAULT_CATEGORY_ID=33
LINE_MYSHOP_DEFAULT_BRAND=CO COAT
LINE_MYSHOP_DEFAULT_WEIGHT=1
LINE_MYSHOP_SEPARATE_VARIANT_SYNC=false
```

Restart FastAPI, then verify readiness and preview the outbound payload:

```bash
curl http://127.0.0.1:8000/products/1/sync-readiness
```

```bash
curl -X POST http://127.0.0.1:8000/products/1/sync/preview
```

Real sync requires an explicit confirmation phrase:

```bash
curl -X POST http://127.0.0.1:8000/products/1/sync \
  -H "Content-Type: application/json" \
  -d '{"confirm":"CONFIRM PRODUCTION SYNC"}'
```

Real mode sends `X-API-KEY`, writes `api_logs.service = line_myshop`, updates `channel_products` and `channel_variants` from response external IDs, and records successful attempts in `sync_jobs`.

## LINE Status, Publish, And Hide

Refresh the storefront visibility status from LINE without changing the product:

```bash
curl -X POST http://127.0.0.1:8000/products/3/line-status/refresh
```

Publish a synced, approved product to the storefront:

```bash
curl -X POST http://127.0.0.1:8000/products/3/publish \
  -H "Content-Type: application/json" \
  -d '{"confirm":"CONFIRM PUBLISH"}'
```

Hide a synced product from the storefront:

```bash
curl -X POST http://127.0.0.1:8000/products/3/hide \
  -H "Content-Type: application/json" \
  -d '{"confirm":"CONFIRM HIDE","reason":"พักการขายชั่วคราว"}'
```

`publish` and `hide` create `sync_jobs`, write `audit_logs`, update `channel_products.is_display`, and do not change product variants, inventory, or images.

## Product Edit APIs

Create a draft product from a staff intake form:

```bash
curl -X POST http://127.0.0.1:8000/products \
  -H "Content-Type: application/json" \
  -d '{
    "product_group":"jeans-new-001",
    "name":"กางเกงยีนส์ตัวอย่าง",
    "color":"ยีนส์เข้ม",
    "gender":"หญิง",
    "category":"กางเกงยีนส์",
    "description":"รายละเอียดสินค้า",
    "note":"รอตรวจรูป",
    "variants":[
      {
        "sku":"JEANS-NEW-M",
        "size":"M",
        "waist":"26-28",
        "hip":"34-36",
        "length":"40",
        "price":"1750",
        "stock_on_hand":3
      }
    ]
  }'
```

Update product master fields:

```bash
curl -X PATCH http://127.0.0.1:8000/products/3 \
  -H "Content-Type: application/json" \
  -d '{"name":"กางเกงยีนส์ขาม้าบุขนกันหนาว","description":"รายละเอียดใหม่"}'
```

Update variant price fields:

```bash
curl -X PATCH http://127.0.0.1:8000/product-variants/1 \
  -H "Content-Type: application/json" \
  -d '{"price":"1790","sale_price":null}'
```

Update variant inventory:

```bash
curl -X PATCH http://127.0.0.1:8000/product-variants/1/inventory \
  -H "Content-Type: application/json" \
  -d '{"stock_on_hand":3,"reserved_stock":0}'
```

Upload raw/reference images for a product. These are stored as `brief` images and are not sent to LINE:

```bash
curl -X POST http://127.0.0.1:8000/products/3/reference-images \
  -F "files=@data/input/images/1779955745901.jpg"
```

Get the standard image generation brief for a product:

```bash
curl http://127.0.0.1:8000/products/3/image-generation-brief
```

Create an image generation job from that brief:

```bash
curl -X POST http://127.0.0.1:8000/products/3/image-generation-jobs
```

Run the job with `fal.ai`. The backend sends local reference images as input, downloads generated results, uploads them to WordPress Media, and registers public URLs as draft product images:

```bash
curl -X POST http://127.0.0.1:8000/image-generation-jobs/1/run \
  -H "Content-Type: application/json" \
  -d '{"quality":"medium","image_size":"square","output_format":"jpeg","num_images_per_slot":1,"approve":false}'
```

Upload generated image files for the job. The backend uploads files to WordPress Media and registers the returned public URLs as draft product images:

```bash
curl -X POST http://127.0.0.1:8000/image-generation-jobs/1/generated-images \
  -F "files=@data/output/generated-product-images/product-3/01-hero-square.png" \
  -F "files=@data/output/generated-product-images/product-3/02-detail-closeup.png" \
  -F "image_types=product" \
  -F "image_types=detail" \
  -F "approve=false"
```

After upload, review the images through `/products/{id}`, approve them, set the main image, approve the product, sync LINE, then publish.

## Import UI APIs

Validate an uploaded Product Master CSV:

```bash
curl -X POST http://127.0.0.1:8000/imports/validate-csv \
  -F "file=@data/input/line_brief_converted.csv"
```

## Docker

Build the backend image:

```bash
cd apps/backend
docker build -t line-myshop-backend .
```

Run it with local environment variables:

```bash
docker run --rm -p 8000:8000 --env-file ../../.env line-myshop-backend
```

Run migrations on the deployed backend environment before using the app:

```bash
alembic upgrade head
```

Dry-run or run import from the returned `valid_products.csv` path:

```bash
curl -X POST http://127.0.0.1:8000/imports/run \
  -H "Content-Type: application/json" \
  -d '{"valid_products_path":"/absolute/path/to/valid_products.csv","dry_run":true}'
```

## Manual Product Image Management

```bash
curl -X POST http://127.0.0.1:8000/products/3/images \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/product-image.jpg","image_type":"product","position":1}'
```

```bash
curl http://127.0.0.1:8000/products/3/images
```

```bash
curl -X POST http://127.0.0.1:8000/product-images/1/approve \
  -H "Content-Type: application/json" \
  -d '{"review_note":"ผ่านการตรวจรูปสินค้า"}'
```

```bash
curl -X POST http://127.0.0.1:8000/product-images/1/set-main
```

```bash
curl -X POST http://127.0.0.1:8000/product-images/1/reject \
  -H "Content-Type: application/json" \
  -d '{"review_note":"รูปไม่ตรงสินค้า"}'
```

## LINE MyShop Image Set Workflow

```bash
curl http://127.0.0.1:8000/products/3/image-set
```

```bash
curl -X POST http://127.0.0.1:8000/products/3/images/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "images": [
      {"url":"https://example.com/01-hero.jpg","image_type":"product","position":1},
      {"url":"https://example.com/02-detail.jpg","image_type":"detail","position":2}
    ]
  }'
```

```bash
curl -X POST http://127.0.0.1:8000/products/3/images/reorder \
  -H "Content-Type: application/json" \
  -d '{
    "images": [
      {"image_id":1,"position":1,"is_main":true},
      {"image_id":2,"position":2,"is_main":false}
    ]
  }'
```

Upload generated files to WordPress Media and register them to the product:

```bash
python -m app.commands.upload_product_images_to_wordpress \
  --product-id 3 \
  --files \
    ../../data/output/generated-product-images/product-3/01-hero.png \
    ../../data/output/generated-product-images/product-3/02-detail.png \
  --image-types product detail \
  --approve \
  --set-main-index 1
```
