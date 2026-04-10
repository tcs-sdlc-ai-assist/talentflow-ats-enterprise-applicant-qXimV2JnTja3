# TalentFlow ATS — Deployment Guide

## Overview

TalentFlow ATS is a Python FastAPI application designed for serverless deployment on Vercel. This guide covers environment setup, database configuration, Vercel deployment, CI/CD integration, and troubleshooting.

---

## Prerequisites

- Python 3.11+
- A Vercel account ([vercel.com](https://vercel.com))
- Vercel CLI installed (`npm i -g vercel`)
- A PostgreSQL database (recommended: [Neon](https://neon.tech), [Supabase](https://supabase.com), or [Railway](https://railway.app))
- Git repository connected to Vercel

---

## Environment Variables

Configure the following environment variables in the Vercel dashboard under **Settings → Environment Variables**. All variables must be set for **Production**, **Preview**, and **Development** environments unless noted otherwise.

### Required Variables

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `SECRET_KEY` | JWT signing key (min 32 chars, random) | `openssl rand -hex 32` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL in minutes | `30` |

### Optional Variables

| Variable | Description | Default |
|---|---|---|
| `ENVIRONMENT` | Runtime environment identifier | `production` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `*` |
| `LOG_LEVEL` | Python logging level | `INFO` |
| `SENTRY_DSN` | Sentry error tracking DSN | _(none)_ |

### Generating a Secret Key

```bash
# Option 1: OpenSSL
openssl rand -hex 32

# Option 2: Python
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Security Note:** Never commit secrets to version control. Use Vercel's encrypted environment variables exclusively.

---

## Database Configuration

### Recommended Providers

| Provider | Free Tier | Connection Pooling | Notes |
|---|---|---|---|
| **Neon** | 0.5 GB | Built-in | Best for serverless (auto-suspend) |
| **Supabase** | 500 MB | PgBouncer included | Full Postgres with extras |
| **Railway** | $5 credit | Manual setup | Simple provisioning |

### Connection String Format

TalentFlow uses SQLAlchemy with `asyncpg` as the async driver. Your `DATABASE_URL` must use the `postgresql+asyncpg://` scheme:

```
postgresql+asyncpg://username:password@hostname:5432/database_name?sslmode=require
```

If your provider gives you a `postgres://` or `postgresql://` URL, replace the scheme prefix:

```
# Provider gives you:
postgres://user:pass@host:5432/db

# You configure:
postgresql+asyncpg://user:pass@host:5432/db?sslmode=require
```

### Connection Pooling for Serverless

Serverless functions spin up and down frequently. Configure pool settings to avoid exhausting database connections:

```python
# These are configured in app/core/database.py
# Recommended settings for serverless:
pool_size = 5
max_overflow = 10
pool_timeout = 30
pool_recycle = 300
pool_pre_ping = True
```

If your provider offers an external connection pooler (e.g., Neon's pooled endpoint or Supabase's PgBouncer port 6543), prefer that endpoint for serverless deployments.

### Running Migrations

Before the first deployment and after any model changes, run database migrations:

```bash
# Set DATABASE_URL locally or in your shell
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db"

# Run Alembic migrations (if configured)
alembic upgrade head

# Or use the built-in table creation (development only)
python -c "
import asyncio
from app.core.database import engine, Base
from app.models import *

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init())
"
```

---

## Vercel Configuration

### vercel.json Explained

```json
{
  "version": 2,
  "builds": [
    {
      "src": "app/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/static/(.*)",
      "dest": "/app/static/$1"
    },
    {
      "src": "/(.*)",
      "dest": "app/main.py"
    }
  ]
}
```

| Key | Purpose |
|---|---|
| `version` | Vercel platform version (always `2`) |
| `builds[0].src` | Entry point for the Python serverless function |
| `builds[0].use` | Vercel builder — `@vercel/python` handles pip install and ASGI wrapping |
| `routes[0]` | Serves static files (CSS, JS, images) directly without hitting the Python function |
| `routes[1]` | Catch-all route — sends all other requests to the FastAPI application |

### How Vercel Runs FastAPI

1. Vercel detects `@vercel/python` and installs dependencies from `requirements.txt`
2. The builder looks for an ASGI `app` object in the specified entry point
3. Each incoming request invokes the serverless function, which boots the FastAPI app
4. The `lifespan` context manager in `main.py` handles startup/shutdown logic per invocation

### Static Files

Place static assets in `app/static/`. The route rule in `vercel.json` serves them directly from Vercel's CDN edge, bypassing the Python function for better performance.

---

## Build & Deploy Steps

### First-Time Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/talentflow-ats.git
cd talentflow-ats

# 2. Install Vercel CLI
npm install -g vercel

# 3. Link to your Vercel project
vercel link

# 4. Set environment variables
vercel env add DATABASE_URL
vercel env add SECRET_KEY
vercel env add ALGORITHM
vercel env add ACCESS_TOKEN_EXPIRE_MINUTES

# 5. Deploy to preview
vercel

# 6. Deploy to production
vercel --prod
```

### Subsequent Deployments

```bash
# Push to main branch triggers automatic production deployment
git add .
git commit -m "feat: add new feature"
git push origin main

# Or deploy manually
vercel --prod
```

### Local Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://localhost:5432/talentflow_dev
SECRET_KEY=dev-secret-key-change-in-production-minimum-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
ENVIRONMENT=development
EOF

# 4. Run the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## CI/CD Integration

### GitHub Actions (Recommended)

Create `.github/workflows/deploy.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run tests
        run: |
          python -m pytest tests/ -v --tb=short
        env:
          DATABASE_URL: "sqlite+aiosqlite:///./test.db"
          SECRET_KEY: "test-secret-key-not-for-production-use-32chars"
          ALGORITHM: "HS256"
          ACCESS_TOKEN_EXPIRE_MINUTES: "30"

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: "--prod"
```

### Required GitHub Secrets

| Secret | How to Obtain |
|---|---|
| `VERCEL_TOKEN` | Vercel Dashboard → Settings → Tokens → Create |
| `VERCEL_ORG_ID` | Run `vercel link`, check `.vercel/project.json` → `orgId` |
| `VERCEL_PROJECT_ID` | Run `vercel link`, check `.vercel/project.json` → `projectId` |

### Branch Preview Deployments

Vercel automatically creates preview deployments for every pull request when the GitHub integration is enabled. Each PR gets a unique URL for testing before merging to production.

---

## Troubleshooting

### Common Issues

#### 1. `ModuleNotFoundError: No module named 'xyz'`

**Cause:** Missing dependency in `requirements.txt`.

**Fix:** Ensure every imported package is listed in `requirements.txt`. Common omissions:
```
pydantic-settings
python-multipart
email-validator
python-jose[cryptography]
bcrypt
aiosqlite
asyncpg
```

#### 2. `500 Internal Server Error` on all routes

**Cause:** Missing or malformed environment variables.

**Fix:** Verify all required environment variables are set in Vercel:
```bash
vercel env ls
```
Check the function logs in Vercel Dashboard → Deployments → Functions tab.

#### 3. `Connection refused` or database timeout

**Cause:** Database not accessible from Vercel's serverless network, or wrong connection string.

**Fix:**
- Ensure your database allows connections from all IPs (Vercel uses dynamic IPs) or whitelist Vercel's IP ranges
- Verify the connection string uses `postgresql+asyncpg://` scheme
- Add `?sslmode=require` to the connection string
- Check that the database is not paused (Neon auto-suspends after inactivity)

#### 4. `Function timed out` (Vercel 10s limit)

**Cause:** Serverless functions on Vercel Hobby plan have a 10-second execution limit (60s on Pro).

**Fix:**
- Optimize slow database queries (add indexes, reduce joins)
- Use connection pooling to avoid cold-start connection overhead
- Move long-running tasks to background jobs or a separate worker

#### 5. `CORS error` in browser console

**Cause:** Frontend origin not in the allowed CORS origins list.

**Fix:** Set `CORS_ORIGINS` environment variable to include your frontend domain:
```
CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
```

#### 6. `RuntimeError: no running event loop` or `MissingGreenlet`

**Cause:** Synchronous database access in an async context, or lazy-loaded relationships.

**Fix:**
- Ensure all SQLAlchemy relationships use `lazy="selectin"`
- Use `selectinload()` in queries that access nested relationships
- Never call synchronous ORM methods inside async route handlers

#### 7. Static files returning 404

**Cause:** Incorrect path in `vercel.json` routes or files not in the expected directory.

**Fix:** Verify that:
- Static files are in `app/static/`
- The `vercel.json` route pattern matches: `"/static/(.*)"` → `"/app/static/$1"`
- File paths in templates use `/static/` prefix

#### 8. `ValidationError: extra fields not permitted`

**Cause:** Vercel injects extra environment variables that Pydantic Settings rejects.

**Fix:** Ensure your Settings class includes `extra="ignore"`:
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

### Viewing Logs

```bash
# Real-time function logs
vercel logs your-project.vercel.app --follow

# Or view in the dashboard:
# Vercel Dashboard → Project → Deployments → (select deployment) → Functions
```

### Redeploying

```bash
# Force a fresh deployment (clears build cache)
vercel --prod --force

# Redeploy a specific commit
git push --force-with-lease origin main
```

---

## Production Checklist

Before going live, verify the following:

- [ ] `SECRET_KEY` is a unique, randomly generated 32+ character string
- [ ] `ENVIRONMENT` is set to `production`
- [ ] `CORS_ORIGINS` is set to specific domains (not `*`)
- [ ] Database has SSL enabled (`?sslmode=require`)
- [ ] Database connection pooling is configured
- [ ] All migrations have been applied
- [ ] Error tracking (Sentry) is configured
- [ ] GitHub Actions CI/CD pipeline passes all tests
- [ ] Preview deployment has been manually tested
- [ ] Environment variables are set for Production scope in Vercel

---

## Architecture Notes

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Browser    │────▶│  Vercel Edge CDN │────▶│  Serverless Fn  │
│              │◀────│  (static files)  │◀────│  (FastAPI/ASGI) │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │   PostgreSQL     │
                                              │  (Neon/Supabase) │
                                              └─────────────────┘
```

- **Vercel Edge CDN** serves static assets with global caching
- **Serverless Functions** handle API requests and HTML rendering
- **PostgreSQL** stores all application data with async connections via `asyncpg`
- Each function invocation is stateless — no in-memory state persists between requests