# LINE MyShop Product Master Frontend

Next.js dashboard for previewing imported products, approving or rejecting products, and reviewing import batches.

## Setup

Create local frontend environment variables:

```bash
cd apps/frontend
cp .env.example .env.local
```

Default backend URL:

```text
BACKEND_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Install dependencies:

```bash
npm install
```

Run the frontend:

```bash
npm run dev
```

Open:

```text
http://127.0.0.1:3000/products
```

## Available Pages

- `/products`: product list, search/filter/sort, batch LINE refresh, approve/reject, sync, publish/hide controls.
- `/products/new`: staff product intake form with product fields, SKU variants, stock, and reference image upload.
- `/products/[id]`: product detail, product edit, image generation brief/job, generated image upload, image review, variant price/stock edit, sync preview, publish/hide controls.
- `/imports`: CSV upload, validate, dry-run/import, import batch list.
- `/imports/[id]`: import row errors.
- `/sync-jobs`: LINE sync, publish, hide job history.
- `/sync-jobs/[id]`: sync job detail.

## Backend

Start the backend from the repository root before using the frontend:

```bash
make dev
```

The frontend includes a same-origin Next.js proxy route at `/api/backend/*`, which forwards requests to `NEXT_PUBLIC_API_BASE_URL`. This avoids browser CORS issues while keeping the backend unchanged.
The proxy prefers `BACKEND_API_BASE_URL` when set, which is better for production deploys because only the Next.js server needs to know the backend URL.

## Production Publish Checklist

Recommended Vercel setup:

- Set project root directory to `apps/frontend`.
- Set build command to `npm run build`.
- Set install command to `npm install`.
- Set environment variable `BACKEND_API_BASE_URL` to the deployed FastAPI backend URL, for example `https://api.example.com`.
- Do not add LINE, WordPress, or fal.ai API keys to the frontend project.

Before publishing:

```bash
npm run lint
npm run build
```
