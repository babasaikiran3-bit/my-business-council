# Multi-Environment Configuration Guide

This guide explains how to configure Eternal Ops Control for **development**, **staging**, and **production** environments.

## Environment Overview

| Environment | Purpose | Supabase Project | WorkOS Environment |
|-------------|---------|------------------|-------------------|
| **Development** | Local development | Dedicated dev project | Staging credentials |
| **Staging** | Pre-production testing | Dedicated staging project | Staging credentials |
| **Production** | Live application | prod-eternal-ops-control | Production credentials |

## Quick Start

### Initial Setup

1. Copy the appropriate environment files:
   ```bash
   # Backend environment
   cp .env.development.example .env.development

   # Frontend environment
   cp frontend/.env.development.example frontend/.env.development
   ```

2. Fill in the actual credentials for your environment.

### Running the Application

**Development (Default):**
```bash
# Option 1: Using shell scripts (recommended)
./run.sh                    # Backend on port 8001
./run-frontend.sh           # Frontend on port 5173

# Option 2: Using npm scripts
cd frontend && npm run dev  # Uses --mode development

# Option 3: Direct Python command
python -m backend.main      # Defaults to ENV=development
```

**Staging:**
```bash
# Backend
./run.sh --staging
# or
ENV=staging python -m backend.main

# Frontend
./run-frontend.sh --staging
# or
cd frontend && npm run dev:staging
```

**Production (requires confirmation):**
```bash
# Backend
./run.sh --production
# or
ENV=production python -m backend.main

# Frontend
./run-frontend.sh --production
# or
cd frontend && npm run dev:production
```

### Environment File Loading Priority

| Environment | Backend Loads | Frontend Loads (Vite Mode) |
|-------------|---------------|---------------------------|
| Development | `.env.development` → `.env` (fallback) | `.env.development` → `.env` |
| Staging | `.env.staging` (required) | `.env.staging` |
| Production | `.env.production` (required) | `.env.production` |

---

## 1. Supabase Database Setup

Each environment requires its own Supabase project to ensure data isolation.

### Creating a New Supabase Project

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Click **New Project**
3. Fill in the details:
   - **Name**: `dev-eternal-ops-control` or `staging-eternal-ops-control`
   - **Database Password**: Generate a strong password
   - **Region**: Choose based on your location (eu-west-1 for Europe)
4. Click **Create new project**
5. Wait for the project to be provisioned (~2 minutes)

### Getting Credentials

After project creation:
1. Go to **Project Settings** → **API**
2. Copy:
   - **Project URL** → `SUPABASE_URL`
   - **service_role key** (under "Project API keys") → `SUPABASE_SERVICE_ROLE_KEY`

> ⚠️ **Security**: The `service_role` key bypasses Row Level Security. Never expose it in frontend code.

### Applying the Database Schema

Run the schema migration script to create tables and RLS policies:

```bash
# Using the Supabase CLI
supabase db push --db-url "postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres"

# Or manually via SQL Editor in Supabase Dashboard
# Copy contents of scripts/schema.sql and run in SQL Editor
```

See [scripts/schema.sql](../scripts/schema.sql) for the complete schema.

### Environment-Specific Supabase Projects

| Environment | Project Name | Region | Purpose |
|-------------|--------------|--------|---------|
| Development | `dev-eternal-ops-control` | Any | Local testing, experimental features |
| Staging | `staging-eternal-ops-control` | Same as prod | Mirror of production for testing |
| Production | `prod-eternal-ops-control` | eu-west-1 | Live user data |

---

## 2. WorkOS Authentication Setup

WorkOS provides separate environments for development and production.

### Environment Strategy

- **Development & Staging**: Share WorkOS **Staging** environment
- **Production**: Use WorkOS **Production** environment

### Creating a Production Environment in WorkOS

1. Go to [WorkOS Dashboard](https://dashboard.workos.com)
2. Click the environment dropdown (top-left)
3. Select **Production**
4. Complete the production checklist:
   - Verify your domain
   - Configure SSO connections
   - Set up redirect URIs

### Configuring Redirect URIs

Each environment needs its own redirect URI configured in WorkOS:

| Environment | Redirect URI |
|-------------|--------------|
| Development | `http://localhost:5173/callback` |
| Staging | `https://staging.your-domain.com/callback` |
| Production | `https://your-domain.com/callback` |

**To configure in WorkOS:**
1. Go to **Redirects** in the dashboard
2. Add each URI under **Sign-in callback URLs**
3. Add sign-out redirect URLs as needed

### WorkOS Credentials by Environment

| Environment | API Key Prefix | Client ID Prefix |
|-------------|----------------|------------------|
| Staging | `sk_test_` | `client_01...` |
| Production | `sk_live_` | `client_01...` (different ID) |

---

## 3. Typesense Search Setup

Typesense Cloud provides full-text search for conversations and messages. Each environment requires its own Typesense cluster.

### Creating a Typesense Cloud Cluster

1. Go to [Typesense Cloud](https://cloud.typesense.org)
2. Click **Create Cluster**
3. Configure the cluster:
   - **Name**: `eternal-ops-{environment}` (e.g., `eternal-ops-dev`)
   - **Plan**: Start with the smallest plan for dev/staging
   - **Region**: Choose based on your location (Frankfurt for Europe)
4. Wait for the cluster to be provisioned (~1-2 minutes)

### Getting Credentials

After cluster creation:
1. Go to **Cluster Details** → **API Keys**
2. Copy the following:
   - **Host**: `{cluster-id}.a1.typesense.net` → `TYPESENSE_HOST`
   - **Port**: `443` → `TYPESENSE_PORT`
   - **Protocol**: `https` → `TYPESENSE_PROTOCOL`
   - **Admin API Key**: Full access key → `TYPESENSE_API_KEY`
   - **Search-only API Key**: Create one with read-only permissions → `TYPESENSE_SEARCH_ONLY_KEY`

> ⚠️ **Security**: The Admin API Key has write access. Never expose it in frontend code. Only the search-only key is used for generating scoped keys.

### Creating a Search-Only API Key

1. In Typesense Cloud, go to **API Keys**
2. Click **Generate API Key**
3. Set permissions:
   - **Actions**: `documents:search` only
   - **Collections**: `conversations`, `messages`, `zep_memories`
4. Save the key as `TYPESENSE_SEARCH_ONLY_KEY`

### Initializing Collections

After setting environment variables, run the migration commands:

```bash
# 1. Initialize collection schemas
python -m backend.search init

# Expected output:
# Created collection: conversations
# Created collection: messages
# Created collection: zep_memories

# 2. Sync existing data from Supabase
python -m backend.search sync

# Expected output:
# Synced 18 conversations
# Synced 14 messages
# Synced 0 memories
```

### Verification

Confirm the setup is working:

```bash
python -c "
from backend.search import get_typesense_client
client = get_typesense_client()
for name in ['conversations', 'messages', 'zep_memories']:
    info = client.collections[name].retrieve()
    print(f'{name}: {info[\"num_documents\"]} documents')
"
```

### Environment-Specific Typesense Clusters

| Environment | Cluster Name | Region | Purpose |
|-------------|--------------|--------|---------|
| Development | `eternal-ops-dev` | Any | Local testing |
| Staging | `eternal-ops-staging` | Same as prod | Pre-production testing |
| Production | `eternal-ops-prod` | Frankfurt | Live search |

### Rollback Procedure

If Typesense becomes unavailable:

1. **Storage operations continue normally** - Typesense indexing is non-blocking
2. **Search bar shows "Search not configured"** - User can still navigate manually
3. **To re-enable**: Fix Typesense credentials and restart backend
4. **To re-sync after outage**: Run `python -m backend.search sync`

---

## 4. Environment Configuration Files

### File Structure

```
eternal-ops-control/
├── .env                          # Active environment (git-ignored)
├── .env.example                  # Template with all variables
├── .env.development.example      # Development defaults
├── .env.staging.example          # Staging configuration
├── .env.production.example       # Production configuration
└── frontend/
    ├── .env                      # Active frontend env (git-ignored)
    └── .env.example              # Frontend template
```

### Loading Environment Variables

The backend uses `python-dotenv` to load from `.env`:

```python
from dotenv import load_dotenv
load_dotenv()  # Loads from .env in project root
```

For the frontend, Vite automatically loads from `frontend/.env`.

---

## 6. Environment Detection

The application can detect which environment it's running in:

```python
import os

def get_environment():
    """Detect the current environment."""
    # Vercel sets VERCEL_ENV to 'production', 'preview', or 'development'
    vercel_env = os.getenv("VERCEL_ENV")
    if vercel_env:
        if vercel_env == "production":
            return "production"
        elif vercel_env == "preview":
            return "staging"
        else:
            return "development"

    # Fallback to explicit ENV variable
    return os.getenv("ENV", "development")
```

---

## 7. Troubleshooting

### Common Issues

**1. "Supabase not configured" error**
- Ensure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set
- Check that `.env` file is in the project root

**2. WorkOS authentication fails**
- Verify redirect URI matches exactly (including trailing slashes)
- Check you're using the correct environment's credentials
- Ensure `VITE_WORKOS_CLIENT_ID` in `frontend/.env` matches backend

**3. CORS errors in staging/production**
- Add your domain to `ALLOWED_ORIGINS` environment variable
- Vercel automatically allows `*.vercel.app` domains

**4. Database schema mismatch**
- Run the schema migration script on the affected environment
- Compare schemas using `supabase db diff`

**5. "Search not configured" after sign-in**
- Ensure all `TYPESENSE_*` environment variables are set
- Run `python -m backend.search init` to create collections
- Check backend logs for Typesense connection errors
- Verify the search-only key has correct permissions

**6. Empty search results after user switch**
- This is fixed in the latest code; ensure you're on the latest version
- The GlobalSearch component now resets the adapter cache when user changes

**7. Typesense indexing errors in logs**
- Indexing failures don't block storage operations (graceful degradation)
- Check cluster health in Typesense Cloud dashboard
- Re-sync data with `python -m backend.search sync`

---

## 8. Security Checklist

Before deploying to production:

- [ ] All `.env` files are in `.gitignore`
- [ ] Production uses `sk_live_` WorkOS key (not `sk_test_`)
- [ ] `SUPABASE_SERVICE_ROLE_KEY` is never exposed to frontend
- [ ] RLS policies are enabled on all tables
- [ ] CORS `ALLOWED_ORIGINS` is set to specific domains (not `*`)
- [ ] Email domain validation is configured (`EMPLOYEE_EMAIL_DOMAIN`)
- [ ] `TYPESENSE_API_KEY` (admin key) is never exposed to frontend
- [ ] `TYPESENSE_SEARCH_ONLY_KEY` is used only for generating scoped keys
- [ ] Scoped search keys expire (default: 1 hour)

---

## Quick Reference

### Development Commands

```bash
# Start backend (development)
python -m backend.main

# Start frontend (development)
cd frontend && npm run dev

# Run tests
python -m pytest tests/ -v
```

### Environment Variable Summary

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `WORKOS_API_KEY` | Yes | WorkOS API key |
| `WORKOS_CLIENT_ID` | Yes | WorkOS client ID |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key |
| `EMPLOYEE_EMAIL_DOMAIN` | No | Email domain for access control |
| `ALLOWED_ORIGINS` | No | CORS allowed origins |
| `VITE_WORKOS_CLIENT_ID` | Yes | WorkOS client ID (frontend) |
| `VITE_WORKOS_REDIRECT_URI` | Yes | OAuth callback URL (frontend) |
| `TYPESENSE_HOST` | Yes | Typesense Cloud hostname |
| `TYPESENSE_PORT` | Yes | API port (443 for HTTPS) |
| `TYPESENSE_PROTOCOL` | Yes | Connection protocol (`https`) |
| `TYPESENSE_API_KEY` | Yes | Admin API key (write access) |
| `TYPESENSE_SEARCH_ONLY_KEY` | Yes | Search-only key (read access) |

## 4. Vercel Deployment Configuration

### Setting Environment Variables in Vercel

1. Go to your project in [Vercel Dashboard](https://vercel.com/dashboard)
2. Navigate to **Settings** → **Environment Variables**
3. Add variables for each environment:

| Variable | Development | Preview | Production |
|----------|-------------|---------|------------|
| `SUPABASE_URL` | Dev URL | Staging URL | Prod URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Dev key | Staging key | Prod key |
| `WORKOS_API_KEY` | `sk_test_...` | `sk_test_...` | `sk_live_...` |
| `WORKOS_CLIENT_ID` | Staging ID | Staging ID | Prod ID |
| `OPENROUTER_API_KEY` | Your key | Your key | Your key |
| `ALLOWED_ORIGINS` | (optional) | Staging URL | Prod URL |

### Environment Targeting in Vercel

Vercel supports targeting variables to specific environments:
- **Production**: Only the production deployment
- **Preview**: All preview deployments (PRs, branches)
- **Development**: Local development with `vercel dev`

### Branch-Based Deployments

Configure branch deployments for staging:
1. Go to **Settings** → **Git**
2. Set **Production Branch** to `main`
3. Create a `staging` branch for staging deployments
4. Preview deployments on `staging` branch will use Preview environment variables

---

## 5. Staging Data Sync Strategy

To keep staging data realistic, periodically sync from production:

### Option A: Schema-Only Sync (Recommended)

Keep schema in sync, use synthetic test data:

```bash
# Export schema from production
supabase db dump --schema-only > schema.sql

# Apply to staging
psql $STAGING_DB_URL < schema.sql
```

### Option B: Full Data Clone (With Caution)

For testing with production-like data:

1. Create a backup in Supabase Dashboard
2. Download the backup
3. Restore to staging project

> ⚠️ **Privacy**: Anonymize sensitive data before syncing to staging.

---

