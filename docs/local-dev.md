# Local Dev

This document describes the local development setup.

## Requirements

- macOS development machine.
- Python for FastAPI backend.
- Docker Desktop for PostgreSQL.
- PostgreSQL container via Docker Compose.
- `uv` is preferred for backend dependency management. If `uv` is not installed, the Makefile falls back to `python3 -m venv` and `pip`.

## Backend

Location:

```text
apps/backend
```

Tools:

- FastAPI
- SQLAlchemy
- Alembic
- Pydantic settings
- pytest

Current backend support:

- `GET /health`
- SQLAlchemy models for product master, import, sync, API log, and audit log tables.
- Alembic migration for the initial database schema.

Future backend support:

- CSV / Excel import.
- Validation.
- Product and variant persistence.
- Approval workflow.
- Mock LINE MyShop sync.
- Audit logs.

## Planned Frontend

Location:

```text
apps/frontend
```

Planned tools:

- Next.js
- Tailwind CSS

The frontend should eventually support:

- Import screen.
- Validation result screen.
- Product dashboard.
- Product detail preview.
- Approval controls.
- Mock sync controls.
- Sync and audit log views.

## Planned Data Folders

```text
data/input
data/output
data/samples
```

Usage:

- `data/samples`: example templates and sample product briefs.
- `data/input`: local import files provided by the product owner.
- `data/output`: generated exports, reports, or sync logs if needed.

## First Manual Check

After this scaffold task, confirm the expected files exist:

```bash
find . -maxdepth 3 -type f | sort
```

Preview the sample CSV:

```bash
column -s, -t < data/samples/sample_jeans_products.csv
```

## Backend Commands

From the repository root:

```bash
cp .env.example .env
make install
make db-up
make migrate
make dev
```

In another terminal, check the backend:

```bash
curl http://127.0.0.1:8000/health
```

Run tests:

```bash
make test
```

Stop PostgreSQL:

```bash
make db-down
```

## Import Validated CSV

Generate validated CSV output from the repository root:

```bash
python3 scripts/validate_products_csv.py \
  --input data/samples/sample_jeans_products.csv \
  --output-dir data/output
```

Dry-run import:

```bash
cd apps/backend
python -m app.commands.import_products \
  --input ../../data/output/valid_products.csv \
  --dry-run
```

Real import:

```bash
cd apps/backend
python -m app.commands.import_products \
  --input ../../data/output/valid_products.csv
```

Return to the repository root and verify data:

```bash
cd ../..
docker compose exec postgres psql -U app -d line_myshop
```

```sql
select count(*) from products;
select count(*) from product_variants;
select count(*) from inventory_balances;
select count(*) from product_images;
```

## Mock LINE MyShop Sync

Mock sync is enabled by default and does not call the real LINE MyShop API:

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

Run the latest migrations:

```bash
make migrate
```

Approve and sync a product:

```bash
curl -X POST http://127.0.0.1:8000/products/1/approve
curl -X POST http://127.0.0.1:8000/products/1/sync
```

Inspect sync jobs:

```bash
curl http://127.0.0.1:8000/sync-jobs
curl http://127.0.0.1:8000/sync-jobs/1
```

## Real LINE MyShop API Adapter

The backend can switch to real API mode by environment settings. Keep mock mode enabled until the official endpoint contract and real credentials are available.

```text
LINE_MYSHOP_MOCK_MODE=false
LINE_MYSHOP_BASE_URL=https://api.example.line-myshop.com
LINE_MYSHOP_API_KEY=replace-with-real-api-key
LINE_MYSHOP_TIMEOUT_SECONDS=15
LINE_MYSHOP_CREATE_PRODUCT_PATH=/products
LINE_MYSHOP_UPDATE_PRODUCT_PATH=/products/{external_product_id}
LINE_MYSHOP_UPDATE_INVENTORY_PATH=/variants/{external_variant_id}/inventory
LINE_MYSHOP_UPDATE_PRICE_PATH=/variants/{external_variant_id}/price
```

Restart FastAPI after changing `.env`:

```bash
make dev
```

Run sync with the same endpoint:

```bash
curl -X POST http://127.0.0.1:8000/products/1/sync
```

Real mode logs request and response rows in `api_logs` with `service = line_myshop`.

## Manual Product Image Management

Add, approve, and set main image URLs before using them for storefront or mock LINE sync payloads:

```bash
curl -X POST http://127.0.0.1:8000/products/3/images \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/product-image.jpg","image_type":"product","position":1}'
```

```bash
curl -X POST http://127.0.0.1:8000/product-images/1/approve \
  -H "Content-Type: application/json" \
  -d '{"review_note":"ผ่านการตรวจรูปสินค้า"}'
```

```bash
curl -X POST http://127.0.0.1:8000/product-images/1/set-main
```

## Archive Sample Products

Archived products are hidden from `GET /products` by default, but remain available in product detail and history tables.

```bash
curl -X POST http://127.0.0.1:8000/products/1/archive \
  -H "Content-Type: application/json" \
  -d '{"reason":"sample/test data from initial CSV"}'
```

```bash
curl "http://127.0.0.1:8000/products?include_archived=true"
```
