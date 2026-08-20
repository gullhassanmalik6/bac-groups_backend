# CryptoPOS Backend

Enterprise FastAPI backend for Android POS card acceptance and USDT settlement orchestration.

## Architecture

```
Android POS / Website
        │
        ▼
   FastAPI (/api/v1)
        │
   Service Layer
        │
 Repository Layer
        │
   PostgreSQL
```

Payment flow:

1. POS creates payment → `PaymentGateway` adapter charges card  
2. Transaction + receipt persisted with status history  
3. `SettlementEngine` calculates fees → exchange quote → wallet transfer  
4. Settlement + transfer logs audited  

Gateways never convert fiat→USDT directly. The Settlement Engine owns that workflow.

## Stack

- Python 3.13 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2  
- PostgreSQL 17 · Redis · Celery  
- Structlog · JWT + refresh rotation · Docker Compose  

## Quick start (Docker)

```bash
cd backend
cp .env.example .env
docker compose up --build
```

API: http://localhost:8000/docs  
Health: http://localhost:8000/api/v1/health  

Default admin (seeded): `admin@cryptopos.com` / `ChangeMeNow!123`

## Local development

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Start Postgres + Redis (Docker)
docker compose up -d postgres redis

# Create schema + seed
python -m scripts.init_db

# API
uvicorn app.main:app --reload --port 8000

# Worker (optional)
celery -A app.tasks.celery_app.celery_app worker --loglevel=INFO
```

## Core endpoints

| Area | Path |
|------|------|
| Auth | `POST /api/v1/auth/register\|login\|refresh\|logout` · `GET /me` |
| Merchants | `POST /api/v1/merchants` · `GET /me` · wallets |
| Payments | `POST /api/v1/payments` · list/get/receipt · `POST /{id}/refund` · webhooks: `nowpayments`, `moyasar` |
| Website | `/api/v1/website/services\|projects\|faq\|testimonials\|contact\|newsletter` |
| Admin | `GET /api/v1/admin/dashboard` |

## Tests

```bash
pytest -q
```

## Railway (production)

See `/docs/DEPLOYMENT.md`. Service root directory: `backend`. Healthcheck: `/api/v1/health`.

Hobby plan. Postgres plugin. Domain/DNS stays on HostArmada.

Default merchant after seed: `turki.hejaili@gmail.com` / `ChangeMeOnFirstLogin!123` (change immediately).

Payment default: `sandbox` until NOWPayments verification completes. See `/docs/PAYMENT_PROVIDER_VERIFICATION.md`.

Production domain: **bacgroupsa.com** (`api.bacgroupsa.com`, `www.bacgroupsa.com`).
