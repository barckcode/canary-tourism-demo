# Tenerife Tourism Intelligence — Architecture Document

> Last updated: 2026-03-14

## Overview

Full-stack analytics platform for Tenerife tourism demand forecasting, tourist profiling, and what-if scenario analysis. Combines data from three public APIs (ISTAC, INE, CKAN), trains ensemble ML models, and presents interactive visualizations through a React frontend.

**Live URL:** https://tourism-demo.agentcrew.sh

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Project Structure](#2-project-structure)
3. [Backend](#3-backend)
4. [Frontend](#4-frontend)
5. [Infrastructure & Deployment](#5-infrastructure--deployment)
6. [Data Sources](#6-data-sources)
7. [ML Models](#7-ml-models)
8. [Data Flow](#8-data-flow)
9. [API Reference](#9-api-reference)
10. [Security & Performance](#10-security--performance)

---

## 1. System Architecture

```
┌─────────────┐     HTTPS      ┌──────────────┐     HTTPS      ┌────────────────┐
│   Browser   │ ◄────────────► │  Cloudflare   │ ◄────────────► │  Nginx (host)  │
│             │                │  (DNS + CDN)  │   Origin CA    │  :443 / :80    │
└─────────────┘                │  Full Strict  │                └───────┬────────┘
                               └──────────────┘                        │
                                                              proxy_pass :8080
                                                                       │
                              ┌────────────────────────────────────────┼──────────────┐
                              │  Docker Compose                       │              │
                              │                                       ▼              │
                              │  ┌──────────────────┐    ┌──────────────────────┐    │
                              │  │  Frontend :8080   │    │   Backend :8000       │    │
                              │  │  Nginx + React    │───►│   FastAPI + SQLite    │    │
                              │  │  (static assets)  │/api│   APScheduler         │    │
                              │  └──────────────────┘    │   ML Models (joblib)   │    │
                              │                          └──────────┬───────────┘    │
                              │                                     │                │
                              │                          ┌──────────▼───────────┐    │
                              │                          │  Volumes              │    │
                              │                          │  - backend-data (DB)  │    │
                              │                          │  - raw-data (RO)      │    │
                              │                          └──────────────────────┘    │
                              └──────────────────────────────────────────────────────┘
                                                                    │
                                              Scheduled ETL (APScheduler)
                                                                    │
                                         ┌──────────────────────────┼──────────────┐
                                         ▼                          ▼              ▼
                                  ┌─────────────┐          ┌──────────┐    ┌──────────┐
                                  │  ISTAC API   │          │ INE API  │    │ CKAN API │
                                  │  (Canarias)  │          │ (Spain)  │    │ (EGT)    │
                                  └─────────────┘          └──────────┘    └──────────┘
```

---

## 2. Project Structure

```
/home/canary/tenerife-tourism/
├── backend/
│   ├── app/
│   │   ├── config.py                  # Settings (env-based via Pydantic)
│   │   ├── main.py                    # FastAPI app, lifespan, middleware
│   │   ├── rate_limit.py              # SlowAPI rate limiter
│   │   ├── api/
│   │   │   ├── router.py              # Route aggregator
│   │   │   ├── dashboard.py           # KPIs & summary trends
│   │   │   ├── timeseries.py          # Historical data queries
│   │   │   ├── predictions.py         # Forecasts & model comparison
│   │   │   ├── profiles.py            # Tourist segmentation & flows
│   │   │   └── scenarios.py           # What-if analysis
│   │   ├── db/
│   │   │   ├── database.py            # SQLAlchemy engine & sessions
│   │   │   ├── models.py              # 5 ORM models
│   │   │   └── seed.py                # Initial data loader
│   │   ├── etl/
│   │   │   ├── pipeline.py            # 4 async ETL pipelines
│   │   │   ├── scheduler.py           # APScheduler (5 cron jobs)
│   │   │   ├── validators.py          # Data quality checks
│   │   │   └── sources/
│   │   │       ├── istac.py           # ISTAC API connector
│   │   │       ├── ine.py             # INE API connector
│   │   │       └── ckan.py            # CKAN portals connector
│   │   └── models/
│   │       ├── trainer.py             # ML training orchestrator
│   │       ├── forecaster.py          # SARIMA / Holt-Winters / Ensemble
│   │       ├── profiler.py            # K-Means clustering
│   │       └── scenario_engine.py     # Gradient Boosting what-if
│   ├── data/
│   │   ├── tourism.db                 # SQLite database (~68 MB)
│   │   └── models/
│   │       ├── forecaster.pkl         # Serialized ensemble (~25 MB)
│   │       ├── profiler.pkl           # Serialized K-Means (~15 MB)
│   │       └── scenario_engine.pkl    # Serialized GBR (~1 MB)
│   ├── tests/                         # pytest test suite
│   ├── Dockerfile                     # python:3.12-slim
│   └── requirements.txt              # 15 dependencies
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx                   # Entry point + React Router
│   │   ├── App.tsx                    # Routes & lazy loading
│   │   ├── api/
│   │   │   ├── client.ts             # Fetch wrapper (7 endpoint groups)
│   │   │   └── hooks.ts              # 11 custom React hooks
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx      # KPIs, map, trends
│   │   │   ├── ForecastPage.tsx       # Predictions, scenarios, heatmap
│   │   │   ├── ProfilesPage.tsx       # Clusters, nationalities, Sankey
│   │   │   └── DataExplorerPage.tsx   # Raw indicator browser
│   │   ├── components/
│   │   │   ├── layout/               # AppShell, Panel
│   │   │   ├── shared/               # AnimatedNumber, ChartContainer, ErrorBoundary, SparklineChart
│   │   │   ├── map/                  # TenerifeMap (Deck.gl 3D heatmap)
│   │   │   ├── forecast/            # ForecastChart, ScenarioChart, YoYHeatmap
│   │   │   ├── profiles/            # ClusterViz (D3 force), SankeyFlow (D3 Sankey)
│   │   │   └── timeline/            # TimeSlider
│   │   └── styles/globals.css        # Tailwind + custom dark theme
│   ├── public/tenerife.geojson        # Municipality boundaries
│   ├── vite.config.ts                 # Build config + code splitting
│   ├── tailwind.config.js             # Custom palette (ocean/volcanic/tropical)
│   ├── nginx.conf                     # SPA routing + /api proxy
│   ├── Dockerfile                     # node:20-alpine → nginx:alpine
│   └── package.json                   # React 19, D3, Deck.gl, MapLibre, Framer Motion
│
├── docker-compose.yml                 # 2 services + 1 named volume
└── CLAUDE.md                          # Dev workspace instructions

/home/canary/tenerife-tourism-data/    # Raw data (sibling directory)
├── istac/                             # ISTAC CSV/JSON files (~140 files)
├── ine/                               # INE JSON files (~12 files)
├── cabildo/istac_extra/               # EGT microdata CSVs + extra datasets
├── exploration/                       # EDA scripts & charts (dev artifacts)
└── PLAN.md                            # Project planning document
```

---

## 3. Backend

### 3.1 Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | FastAPI | 0.115.6 |
| ORM | SQLAlchemy | 2.0.36 |
| Database | SQLite (WAL mode) | — |
| Server | Uvicorn | 0.34.0 |
| Validation | Pydantic + pydantic-settings | 2.10.3 |
| HTTP Client | httpx (async) | 0.28.1 |
| Scheduler | APScheduler | 3.10.4 |
| Rate Limiting | slowapi | 0.1.9 |
| ML: Time Series | statsmodels | 0.14.4 |
| ML: Clustering | scikit-learn | 1.6.0 |
| ML: Scenarios | scikit-learn (GBR) | 1.6.0 |
| Data Processing | pandas, numpy | 2.2.3, 1.26.4 |
| Model Persistence | joblib | 1.4.2 |

### 3.2 Configuration

All settings via environment variables with `TOURISM_` prefix (Pydantic Settings):

| Setting | Default | Description |
|---------|---------|-------------|
| `TOURISM_DEBUG` | `false` | Debug mode |
| `TOURISM_RAW_DATA_DIR` | `/home/canary/tenerife-tourism-data` | Raw data path |
| `TOURISM_CORS_ORIGINS` | `localhost:5173,localhost:3000` | Allowed origins |
| `TOURISM_DATABASE_URL` | `sqlite:///data/tourism.db` | DB connection |
| `TOURISM_SCHEDULER_ENABLED` | `true` | Enable ETL scheduler |

### 3.3 Database Schema

**5 tables:**

| Table | Records | Purpose |
|-------|---------|---------|
| `time_series` | ~200K+ | Historical indicator data (ISTAC, INE, CKAN) |
| `microdata` | ~50K+ | Individual tourist survey records (EGT) |
| `predictions` | ~200+ | Pre-computed forecasts (4 models × indicators) |
| `profiles` | 4 | K-Means cluster summaries |
| `pipeline_runs` | growing | ETL execution audit log |

**Key indices:** `(indicator, geo_code)`, `(source, indicator)`, `(period)`, `(model, indicator, geo_code)`, `(cluster_id)`, `(nacionalidad)`

### 3.4 Application Lifecycle

```
Startup:
  1. init_db()           → Create tables if not exist
  2. seed_all()          → Load raw data (only if DB empty)
  3. ModelTrainer.train_all() → Train models (only if no predictions)
  4. setup_scheduler()   → Start 5 background jobs

Shutdown:
  1. shutdown_scheduler() → Graceful APScheduler stop
```

### 3.5 ETL Scheduler

| Job | Schedule | Source | Misfire Grace |
|-----|----------|--------|---------------|
| `fetch_istac_indicators` | Monday 00:00 UTC | ISTAC API | 1 hour |
| `fetch_ine_series` | Monday 00:30 UTC | INE API | 1 hour |
| `fetch_egt_microdata` | 1st & 15th, 01:00 UTC | CKAN | 2 hours |
| `fetch_cabildo_datasets` | 1st of month, 02:00 UTC | Cabildo CKAN | 2 hours |
| `health_check` | Daily 06:00 UTC | Internal | 1 hour |

When new data is ingested, models are automatically retrained.

### 3.6 Data Validation

Two validators in `validators.py`:

- **TimeSeriesValidator**: Schema checks, period format (YYYY-MM/YYYY-Q/YYYY), value ranges, deduplication
- **MicrodataValidator**: Required fields, quarter format, age 0–120, spending ≥ 0, nights 0–365

---

## 4. Frontend

### 4.1 Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | React | 19.0.0 |
| Language | TypeScript | 5.7.2 |
| Build Tool | Vite | 6.0.5 |
| Routing | React Router | 7.1.0 |
| Styling | Tailwind CSS | 3.4.17 |
| Charts | D3.js + d3-sankey | 7.9.0 |
| 3D Map | Deck.gl + MapLibre GL | 9.2.11 / 5.20.1 |
| Animations | Framer Motion | 12.0.0 |

### 4.2 Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | DashboardPage | 6 KPI cards, 3D map, arrivals sparkline, time slider |
| `/forecast` | ForecastPage | Ensemble forecast chart, scenario engine, model comparison, YoY heatmap |
| `/profiles` | ProfilesPage | Cluster bubbles (D3 force), nationality breakdown, Sankey flows |
| `/data` | DataExplorerPage | Indicator table + time series viewer |

All pages are lazy-loaded with React Suspense and code-split by Vite.

### 4.3 Visualization Components

| Component | Library | Renders |
|-----------|---------|---------|
| `ForecastChart` | D3 | Line chart with 80%/95% CI bands |
| `ScenarioChart` | D3 | Baseline vs scenario with impact shading |
| `YoYHeatmap` | D3 | Month × Year color matrix |
| `ClusterViz` | D3 Force | Interactive bubble chart (draggable, clickable) |
| `SankeyFlow` | D3 Sankey | Country → Accommodation flow diagram |
| `TenerifeMap` | Deck.gl + MapLibre | 3D municipality heatmap |
| `SparklineChart` | D3 | Mini trend line with forecast |
| `AnimatedNumber` | Framer Motion | Animated KPI counter |
| `TimeSlider` | Native | Period selector (2010–2026) |

### 4.4 API Integration

Custom `useQuery<T>` hook with:
- AbortController for request cancellation
- Dependency serialization to prevent infinite loops
- Loading/error state management
- `refetch()` function

11 hooks covering all API endpoints (see [API Reference](#9-api-reference)).

### 4.5 Design System

Dark theme with custom Tailwind palette:

| Token | Usage | Hex |
|-------|-------|-----|
| `ocean-500` | Primary (links, charts) | `#0087b9` |
| `volcanic-500` | Secondary (accents) | `#f69b1a` |
| `tropical-500` | Success/positive | `#0fa74d` |

Glass-panel effect: `bg-gray-900/60 backdrop-blur-xl border border-white/5`

### 4.6 Build Output

Code-split bundles:

| Chunk | Size (gzip) |
|-------|-------------|
| `index` | 73 KB |
| `maplibre` | 284 KB |
| `deckgl` | 214 KB |
| `framer` | 46 KB |
| `d3` | 31 KB |
| Pages (each) | 1–10 KB |

---

## 5. Infrastructure & Deployment

### 5.1 Docker Compose

```yaml
services:
  backend:
    image: python:3.12-slim
    ports: ["8000:8000"]
    volumes:
      - backend-data:/app/data              # DB + models (persistent)
      - ../tenerife-tourism-data:/raw-data:ro  # Raw data (read-only)
    env: TOURISM_RAW_DATA_DIR=/raw-data, TOURISM_DEBUG=false
    user: appuser (UID 1000)
    restart: unless-stopped

  frontend:
    image: node:20-alpine → nginx:alpine (multi-stage)
    ports: ["8080:80"]
    depends_on: [backend]
    restart: unless-stopped
```

### 5.2 Host Nginx (Reverse Proxy)

```
Client → Cloudflare (HTTPS) → Nginx :443 (Origin CA) → Docker Frontend :8080 → Docker Backend :8000
```

- SSL termination with Cloudflare Origin CA certificate
- HTTP → HTTPS redirect handled at Cloudflare edge ("Always Use HTTPS" enabled)

### 5.3 SSL/TLS

| Layer | Protocol | Certificate |
|-------|----------|-------------|
| Client ↔ Cloudflare | TLS 1.2/1.3 | Cloudflare Universal SSL |
| Cloudflare ↔ Origin | TLS 1.2/1.3 | Cloudflare Origin CA (valid until 2041) |

Mode: **Full (Strict)** — end-to-end encryption with certificate validation.

### 5.4 Firewall (DigitalOcean)

| Port | Status | Service |
|------|--------|---------|
| 22 | Open | SSH |
| 443 | Open | HTTPS (Cloudflare → Nginx) |
| 80 | Blocked | Not needed — Cloudflare redirects HTTP→HTTPS at edge |
| 8000 | Blocked | Backend Docker (only reachable locally via Nginx) |
| 8080 | Blocked | Frontend Docker (only reachable locally via Nginx) |
| All others | Blocked | — |

All public traffic flows exclusively through Cloudflare. Docker service ports (8000, 8080) are only accessible from `127.0.0.1` via the host Nginx reverse proxy.

---

## 6. Data Sources

### 6.1 ISTAC (Instituto Canario de Estadística)

- **API:** `https://datos.canarias.es/api/estadisticas/indicators/v1.0`
- **14 indicators:** Tourist arrivals, occupancy rates, ADR, RevPAR, overnight stays, average stay, beds, rooms, revenue, staff
- **Geography:** ES709 (Tenerife)
- **Granularity:** Monthly
- **Format:** ISTAC JSON (SDMX-like dimensions + observations)

### 6.2 INE (Instituto Nacional de Estadística)

- **API:** `https://servicios.ine.es/wstempus/js/ES`
- **21 series:** Hotel occupancy (EOH), tourist apartments (EAT), rural tourism (ETR), resident tourism
- **Geography:** Mix of ES709 (Tenerife) and ES70 (Canarias)
- **Granularity:** Monthly/Quarterly
- **Format:** JSON arrays

### 6.3 CKAN (Open Data Portals)

- **ISTAC CKAN:** `https://datos.canarias.es/catalogos/estadisticas`
  - EGT microdata (tourist spending surveys)
  - ~50K+ records per year, CSV format
- **Cabildo CKAN:** `https://datos.tenerife.es`
  - Local tourism datasets (frequently offline)

### 6.4 EGT Microdata Fields

| Category | Fields |
|----------|--------|
| Demographics | sexo, edad, nacionalidad, pais_residencia |
| Trip | proposito, noches, aloj_categ, aeropuerto_origen |
| Spending | gasto_euros, coste_vuelos, coste_alojamiento, 8 breakdown categories |
| Satisfaction | satisfaccion (0–10), 19 importance factors (ordinal 0–3) |
| Activities | 19 binary activity indicators |

---

## 7. ML Models

### 7.1 Ensemble Forecaster

Combines three models with dynamic weighting:

| Model | Short-term (≤3m) | Medium-term (>3m) |
|-------|-------------------|---------------------|
| SARIMA(2,0,1)(2,0,0,12) | 70% | 50% |
| Holt-Winters (add trend, mult seasonal) | 20% | 30% |
| Seasonal Naive (last 12m repeat) | 10% | 20% |

- COVID period (2020-03 to 2021-06) excluded via interpolation
- Outputs 80% and 95% confidence intervals
- Predictions stored in DB; retrained when new data arrives

### 7.2 Tourist Profiler (K-Means)

- **k=4** clusters, StandardScaler normalization
- **Features:** Age, spend, nights, flight/accommodation costs, party size, 19 importance factors (ordinal), 19 activities (binary), satisfaction, one-hot nationality/purpose/accommodation
- **Output clusters:**
  - 0: Budget / Young / Short-stay
  - 1: High-spend / Family
  - 2: Budget / Older / Medium-stay
  - 3: Premium / Long-stay

### 7.3 Scenario Engine (GBR)

- **Algorithm:** GradientBoostingRegressor (200 trees, depth=5, lr=0.1)
- **Features:** Lagged arrivals (1/3/6/12m), rolling means (3/12m), foreign ratio, lagged accommodation metrics (occupancy, ADR, RevPAR), cyclical month encoding (sin/cos)
- **Parameters:** occupancy_change_pct, adr_change_pct, foreign_ratio_change_pct (±50%)
- **Output:** Baseline forecast, scenario forecast, impact summary

---

## 8. Data Flow

### 8.1 Initial Startup

```
Container starts
  → init_db() creates tables
  → DB empty? seed_all() loads from /raw-data/
    → ISTAC CSVs → time_series table
    → INE JSONs → time_series table
    → EGT CSVs → microdata table
  → No predictions? ModelTrainer.train_all()
    → Forecaster → predictions table + forecaster.pkl
    → Profiler → profiles table + cluster_id on microdata + profiler.pkl
    → ScenarioEngine → scenario_engine.pkl
  → setup_scheduler() starts 5 cron jobs
  → App ready
```

### 8.2 Scheduled Update (weekly)

```
APScheduler triggers pipeline
  → Fetch from external API (ISTAC/INE/CKAN)
  → Validate (schema, ranges, dedup)
  → Upsert into time_series or microdata
  → Log to pipeline_runs
  → If new records: retrain all models
  → Fresh predictions available for next request
```

### 8.3 User Request (example: Dashboard)

```
Browser → GET /api/dashboard/kpis
  → Query latest time_series for each indicator
  → Calculate YoY change
  → Return JSON with 7 KPIs

Browser → GET /api/dashboard/summary
  → Query last 24m arrivals + 12m occupancy + ensemble forecast
  → Return trends arrays

React renders:
  → AnimatedNumber for KPI cards
  → SparklineChart for trends
  → TenerifeMap for 3D heatmap
```

### 8.4 Scenario Analysis

```
User adjusts sliders → clicks "Run Scenario"
  → POST /api/scenarios { occupancy: +5%, adr: -10%, foreign: 0 }
  → Load GBR model from pkl
  → Iterate month-by-month:
    → Build feature vector (lags, rolling stats, month encoding)
    → Baseline = GBR.predict(features)
    → Scenario = GBR.predict(modified_features)
  → Return baseline_forecast, scenario_forecast, impact_summary
  → ScenarioChart renders overlay with impact shading
```

---

## 9. API Reference

Base URL: `/api`

### Dashboard

| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| GET | `/dashboard/kpis` | 60/min | Latest KPIs (arrivals, YoY, occupancy, ADR, RevPAR, avg_stay) |
| GET | `/dashboard/summary` | 60/min | 24m arrivals trend, 12m occupancy, ensemble forecast |

### Time Series

| Method | Path | Params | Rate Limit |
|--------|------|--------|------------|
| GET | `/timeseries` | `indicator`, `geo`, `from`, `to`, `measure` | 60/min |
| GET | `/timeseries/indicators` | — | 60/min |

### Predictions

| Method | Path | Params | Rate Limit |
|--------|------|--------|------------|
| GET | `/predictions` | `indicator`, `geo`, `horizon`, `model` | 20/min |
| GET | `/predictions/compare` | `indicator`, `geo`, `horizon` | 20/min |

### Profiles

| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| GET | `/profiles` | 60/min | All cluster summaries |
| GET | `/profiles/{cluster_id}` | 60/min | Detailed cluster profile |
| GET | `/profiles/nationalities` | 60/min | Aggregate stats by nationality |
| GET | `/profiles/flows` | 60/min | Sankey data (top 6 countries → top 4 accommodations) |

### Scenarios

| Method | Path | Body | Rate Limit |
|--------|------|------|------------|
| POST | `/scenarios` | `occupancy_change_pct`, `adr_change_pct`, `foreign_ratio_change_pct`, `horizon` | 20/min |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns `{"status": "ok", "version": "0.1.0"}` |

---

## 10. Security & Performance

### Security

| Measure | Implementation |
|---------|---------------|
| HTTPS | Cloudflare Full (Strict) + Origin CA |
| Firewall | Only ports 22 (SSH) and 443 (HTTPS) open; all others blocked |
| Edge Security | Cloudflare proxy (DDoS protection, WAF, "Always Use HTTPS") |
| CORS | Whitelist-based (`TOURISM_CORS_ORIGINS`) |
| Rate Limiting | 60/min data, 20/min predictions/scenarios |
| SQL Injection | SQLAlchemy ORM (parameterized queries) |
| XSS | React auto-escaping, D3 `.text()` escaping |
| Container Security | Non-root user (appuser:1000) |
| Network Isolation | Docker ports only reachable via localhost; not exposed to internet |
| Read-only Data | Raw data volume mounted `:ro` |
| HTTP Headers | X-Frame-Options, X-Content-Type-Options, X-XSS-Protection (Nginx) |
| Secrets | None in code; env-based configuration |

### Performance

| Optimization | Where |
|-------------|-------|
| SQLite WAL mode | Concurrent reads during writes |
| DB indices | 8 composite indices on hot query paths |
| Pre-computed predictions | Stored in DB, not computed on request |
| Code splitting | 6 Vite chunks (d3, deckgl, maplibre, framer, pages) |
| Lazy loading | React.lazy + Suspense for all pages |
| Request cancellation | AbortController in useQuery hook |
| Memoization | useMemo for data transforms |
| Model caching | joblib pkl files, lazy-loaded on first request |
| Misfire grace | 1–2 hour tolerance for scheduler jobs |
