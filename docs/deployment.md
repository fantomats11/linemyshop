# Deployment Checklist

เอกสารนี้สรุปเฉพาะสิ่งที่ต้องเช็คก่อนส่งขึ้น git และ publish website

## 1. ห้าม commit secret

ไฟล์จริงที่มี secret ต้องไม่ขึ้น git:

- `.env`
- `apps/frontend/.env.local`
- `apps/backend/.venv`
- `apps/frontend/node_modules`
- `data/input/*`
- `data/output/*`

ให้ commit เฉพาะตัวอย่าง config:

- `.env.example`
- `apps/frontend/.env.example`

## 2. Backend production env

ตั้งค่าที่ backend host เท่านั้น:

```text
DATABASE_URL=
LINE_MYSHOP_MOCK_MODE=false
LINE_MYSHOP_BASE_URL=https://developers-oaplus.line.biz
LINE_MYSHOP_API_KEY=
LINE_MYSHOP_API_KEY_HEADER=X-API-KEY
LINE_MYSHOP_DEFAULT_CATEGORY_ID=
LINE_MYSHOP_DEFAULT_BRAND=CO COAT
WORDPRESS_BASE_URL=
WORDPRESS_USERNAME=
WORDPRESS_APPLICATION_PASSWORD=
IMAGE_GENERATION_PROVIDER=fal
FAL_KEY=
FAL_IMAGE_MODEL=openai/gpt-image-2/edit
FAL_IMAGE_QUALITY=medium
FAL_IMAGE_SIZE=square
FAL_IMAGE_FORMAT=jpeg
```

### Backend Docker deploy

Backend มี Dockerfile ที่:

```text
apps/backend/Dockerfile
```

ตัวอย่าง build/run local:

```bash
cd apps/backend
docker build -t line-myshop-backend .
docker run --rm -p 8000:8000 --env-file ../../.env line-myshop-backend
```

หลัง deploy backend:

```bash
alembic upgrade head
```

เช็ค health:

```bash
curl https://YOUR_BACKEND_DOMAIN/health
```

### Self-host Docker Compose ตัวอย่าง

ถ้า deploy บน VPS หรือเครื่อง server ที่มี Docker Compose ใช้ไฟล์ตัวอย่างนี้ได้:

```bash
cp docker-compose.prod.example.yml docker-compose.prod.yml
```

สร้างไฟล์ env บน server เท่านั้น แล้วใส่ค่าจริง:

```text
POSTGRES_PASSWORD=
DATABASE_URL=postgresql+psycopg://app:YOUR_POSTGRES_PASSWORD@postgres:5432/line_myshop
LINE_MYSHOP_MOCK_MODE=false
LINE_MYSHOP_BASE_URL=https://developers-oaplus.line.biz
LINE_MYSHOP_API_KEY=
LINE_MYSHOP_DEFAULT_CATEGORY_ID=
LINE_MYSHOP_DEFAULT_BRAND=CO COAT
WORDPRESS_BASE_URL=
WORDPRESS_USERNAME=
WORDPRESS_APPLICATION_PASSWORD=
IMAGE_GENERATION_PROVIDER=fal
FAL_KEY=
```

รัน backend + database:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

รัน migration:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production exec backend alembic upgrade head
```

เช็ค health:

```bash
curl http://YOUR_SERVER_IP:8000/health
```

## 3. Frontend publish

แนะนำ deploy frontend บน Vercel โดยตั้ง project root เป็น:

```text
apps/frontend
```

ตั้ง env บน Vercel:

```text
BACKEND_API_BASE_URL=https://YOUR_BACKEND_DOMAIN
```

ไม่ต้องใส่ LINE API key, WordPress password หรือ FAL key ใน frontend

ถ้า backend อยู่คนละโดเมน ไม่ต้องเปิด CORS เพิ่ม เพราะ frontend เรียกผ่าน proxy `/api/backend/*` ใน Next.js server

ก่อน publish:

```bash
cd apps/frontend
npm run lint
npm run build
```

## 4. Smoke test หลัง publish

เปิดหน้า:

```text
https://YOUR_FRONTEND_DOMAIN/products
https://YOUR_FRONTEND_DOMAIN/products/new
https://YOUR_FRONTEND_DOMAIN/imports
https://YOUR_FRONTEND_DOMAIN/sync-jobs
```

เช็ค flow สำคัญ:

1. ดูรายการสินค้าได้
2. เปิดรายละเอียดสินค้าได้
3. อัปโหลด CSV และ validate ได้
4. อัปโหลด reference image ได้
5. สร้างรูปด้วย fal.ai ได้
6. รูปที่สร้างถูกบันทึกเป็น draft image
7. approve รูปและตั้งรูปหลักได้
8. sync LINE ได้เฉพาะสินค้าที่ approved
9. publish LINE ต้องกดยืนยันเอง

## 5. GitHub CI

ทุก push และ pull request เข้า `main` จะรัน GitHub Actions:

- Backend tests
- Frontend lint
- Frontend production build
- Backend Docker build

รันชุดเดียวกันในเครื่องก่อน push:

```bash
make ci
```
