# LINE MyShop Product Master

Local product master system for importing apparel product briefs from CSV or Excel, validating them, previewing them, approving them, and eventually syncing approved products to LINE MyShop.

This repository is in early implementation mode. It currently includes a CSV validator, a FastAPI backend, PostgreSQL local infrastructure, product preview and approval APIs, a frontend dashboard, mock LINE MyShop sync, and a configurable LINE MyShop API client adapter for real API connection when credentials are ready.

## Project Goal

Build a local web app that supports this workflow:

```text
Brief / CSV
-> Validate
-> Import to PostgreSQL
-> Preview in dashboard
-> Approve
-> Sync to LINE MyShop mock or configured LINE MyShop API
-> Log everything
```

## Tech Stack

- Backend: FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migration: Alembic
- Frontend: Next.js + Tailwind
- Local infrastructure: Docker Compose for PostgreSQL
- LINE MyShop integration: mock client by default, real API adapter behind environment settings

## Current Scope

Created in this first task:

- Project documentation
- Folder structure
- CSV template
- Sample jeans product CSV
- CSV validator
- Minimal FastAPI backend
- PostgreSQL Docker Compose setup
- Initial SQLAlchemy models and Alembic migration
- CSV import command for validated Product Master rows
- Product preview and approval APIs
- Frontend dashboard
- Mock LINE MyShop sync backend
- Configurable LINE MyShop API client adapter

Not created yet:

- Confirmed production LINE MyShop endpoint contract
- Production API credentials

## Safety Rules

- Do not call production LINE MyShop APIs unless `LINE_MYSHOP_MOCK_MODE=false` is explicitly configured.
- Keep LINE MyShop integration in mock mode by default.
- Product data must be approved before any sync.
- Real API calls or destructive actions require explicit confirmation.
- All import, approval, and sync actions must be logged once implementation begins.

## Folder Structure

```text
.
├── apps/
│   ├── backend/
│   └── frontend/
├── data/
│   ├── input/
│   ├── output/
│   └── samples/
├── docs/
└── scripts/
```

## Documentation

- [Workflow](docs/workflow.md)
- [Product Master Spec](docs/product-master-spec.md)
- [Validation Rules](docs/validation-rules.md)
- [LINE MyShop Sync Spec](docs/line-myshop-sync-spec.md)
- [Local Dev](docs/local-dev.md)
- [Deployment Checklist](docs/deployment.md)

## Sample Files

- [Product CSV Template](data/samples/products_template.csv)
- [Sample Jeans Products](data/samples/sample_jeans_products.csv)
- [Sample Invalid Products](data/samples/sample_invalid_products.csv)

## CSV Validation

Validate a Product Master CSV file before any backend, database, or LINE MyShop sync work:

```bash
python3 scripts/validate_products_csv.py \
  --input data/samples/sample_jeans_products.csv \
  --output-dir data/output
```

Test intentionally invalid sample data:

```bash
python3 scripts/validate_products_csv.py \
  --input data/samples/sample_invalid_products.csv \
  --output-dir data/output
```

The validator writes these files to the output directory:

- `valid_products.csv`
- `invalid_products.csv`
- `validation_report.csv`
- `validation_summary.json`

## Backend Local Development

Create local environment variables:

```bash
cp .env.example .env
```

Mock LINE MyShop sync is enabled by default:

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

Install backend dependencies. This uses `uv` if available, otherwise it creates a Python virtual environment with `pip`:

```bash
make install
```

Start PostgreSQL:

```bash
make db-up
```

Run database migrations:

```bash
make migrate
```

Start FastAPI:

```bash
make dev
```

Test the health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

Run backend tests:

```bash
make test
```

Run the publish-readiness checks:

```bash
make ci
```

## Import Validated CSV

First validate the Product Master CSV and write `data/output/valid_products.csv`:

```bash
python3 scripts/validate_products_csv.py \
  --input data/samples/sample_jeans_products.csv \
  --output-dir data/output
```

Run a dry-run import from the backend directory:

```bash
cd apps/backend
python -m app.commands.import_products \
  --input ../../data/output/valid_products.csv \
  --dry-run
```

Run the real import:

```bash
cd apps/backend
python -m app.commands.import_products \
  --input ../../data/output/valid_products.csv
```

Return to the repository root and verify imported data in PostgreSQL:

```bash
cd ../..
docker compose exec postgres psql -U app -d line_myshop
```

Inside `psql`:

```sql
select count(*) from products;
select count(*) from product_variants;
select count(*) from inventory_balances;
select count(*) from product_images;
select id, source_file, total_rows, valid_rows, invalid_rows, status from import_batches order by id desc limit 5;
```

## Product Preview and Approval APIs

Start FastAPI:

```bash
make dev
```

List products:

```bash
curl http://127.0.0.1:8000/products
```

List products including archived records:

```bash
curl "http://127.0.0.1:8000/products?include_archived=true"
```

Get product detail:

```bash
curl http://127.0.0.1:8000/products/1
```

Approve a draft product:

```bash
curl -X POST http://127.0.0.1:8000/products/1/approve
```

Reject a draft or approved product:

```bash
curl -X POST http://127.0.0.1:8000/products/1/reject \
  -H "Content-Type: application/json" \
  -d '{"reason":"ข้อมูลสินค้ายังไม่พร้อม"}'
```

Archive a sample/test product without deleting history:

```bash
curl -X POST http://127.0.0.1:8000/products/1/archive \
  -H "Content-Type: application/json" \
  -d '{"reason":"sample/test data from initial CSV"}'
```

List import batches:

```bash
curl http://127.0.0.1:8000/imports
```

List import errors:

```bash
curl http://127.0.0.1:8000/imports/1/errors
```

## Mock LINE MyShop Sync

Run migrations after pulling this version:

```bash
make migrate
```

Only approved products can sync. Approve a product first if needed:

```bash
curl -X POST http://127.0.0.1:8000/products/1/approve
```

Run mock sync:

```bash
curl -X POST http://127.0.0.1:8000/products/1/sync
```

Check sync readiness:

```bash
curl http://127.0.0.1:8000/products/1/sync-readiness
```

Preview the payload before sync:

```bash
curl -X POST http://127.0.0.1:8000/products/1/sync/preview
```

List sync jobs:

```bash
curl http://127.0.0.1:8000/sync-jobs
```

Get one sync job:

```bash
curl http://127.0.0.1:8000/sync-jobs/1
```

Verify mock mappings and logs:

```bash
docker compose exec postgres psql -U app -d line_myshop
```

```sql
select * from channel_products;
select * from channel_variants;
select service, endpoint, method, status_code from api_logs order by id desc limit 10;
select id, job_type, target_type, target_id, status, error_message from sync_jobs order by id desc limit 10;
```

## Real LINE MyShop API Adapter

Mock mode is still the default. To connect the backend to the real LINE MyShop API, update `.env` only after the official endpoint contract and credentials are ready:

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
IMAGE_GENERATION_PROVIDER=fal
FAL_KEY=your-fal-api-key
FAL_IMAGE_MODEL=openai/gpt-image-2/edit
FAL_IMAGE_QUALITY=medium
FAL_IMAGE_SIZE=square
FAL_IMAGE_FORMAT=jpeg
FAL_TIMEOUT_SECONDS=180
```

Restart FastAPI after changing `.env`:

```bash
make dev
```

Before real sync, verify readiness and preview the outbound OA Plus payload:

```bash
curl http://127.0.0.1:8000/products/1/sync-readiness
```

```bash
curl -X POST http://127.0.0.1:8000/products/1/sync/preview
```

Production sync requires an explicit confirmation phrase:

```bash
curl -X POST http://127.0.0.1:8000/products/1/sync \
  -H "Content-Type: application/json" \
  -d '{"confirm":"CONFIRM PRODUCTION SYNC"}'
```

In real mode, the backend sends `X-API-KEY`, logs requests and responses to `api_logs` with `service = line_myshop`, stores returned external IDs in `channel_products` and `channel_variants`, and records each successful attempt in `sync_jobs`. Real sync readiness requires an approved product, at least one variant, at least one approved public product image URL, `LINE_MYSHOP_BASE_URL`, `LINE_MYSHOP_API_KEY`, and `LINE_MYSHOP_DEFAULT_CATEGORY_ID`.

## Manual Product Image Management

Run migrations after pulling this version:

```bash
make migrate
```

Add a product image URL. New images start as `draft`:

```bash
curl -X POST http://127.0.0.1:8000/products/3/images \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/product-image.jpg","image_type":"product","position":1}'
```

List product images:

```bash
curl http://127.0.0.1:8000/products/3/images
```

Approve a product image:

```bash
curl -X POST http://127.0.0.1:8000/product-images/1/approve \
  -H "Content-Type: application/json" \
  -d '{"review_note":"ผ่านการตรวจรูปสินค้า"}'
```

Set an approved product image as the main image:

```bash
curl -X POST http://127.0.0.1:8000/product-images/1/set-main
```

Reject an image:

```bash
curl -X POST http://127.0.0.1:8000/product-images/1/reject \
  -H "Content-Type: application/json" \
  -d '{"review_note":"รูปไม่ตรงสินค้า"}'
```

## LINE MyShop Image Set Workflow

LINE MyShop storefront images should be managed as a set:

- At most 7 images.
- Public `http` or `https` URLs only.
- Position 1 should be the approved main product image.
- Recommended image ratio is 1:1, with 640 x 640 px as a practical target.
- `brief` images are never sent to LINE.

Check the LINE-ready image set:

```bash
curl http://127.0.0.1:8000/products/3/image-set
```

Bulk register public image URLs as draft product images:

```bash
curl -X POST http://127.0.0.1:8000/products/3/images/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "images": [
      {"url":"https://example.com/01-hero.jpg","image_type":"product","position":1},
      {"url":"https://example.com/02-detail.jpg","image_type":"detail","position":2},
      {"url":"https://example.com/03-lifestyle.jpg","image_type":"lifestyle","position":3}
    ]
  }'
```

Reorder images and set the main image:

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

Upload generated local files to WordPress Media and register them back to the product:

```bash
cd apps/backend
python -m app.commands.upload_product_images_to_wordpress \
  --product-id 3 \
  --files \
    ../../data/output/generated-product-images/product-3/01-hero.png \
    ../../data/output/generated-product-images/product-3/02-detail.png \
  --image-types product detail \
  --approve \
  --set-main-index 1
```

## Frontend Local Development

Create local frontend environment variables:

```bash
cd apps/frontend
cp .env.example .env.local
```

Install frontend dependencies:

```bash
npm install
```

Start the frontend:

```bash
npm run dev
```

Open the product dashboard:

```text
http://127.0.0.1:3000/products
```

The frontend reads `NEXT_PUBLIC_API_BASE_URL` from `.env.local` and defaults to:

```text
http://127.0.0.1:8000
```
