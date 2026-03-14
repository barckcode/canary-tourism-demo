# Tenerife Tourism Intelligence

[![Release](https://img.shields.io/github/v/release/barckcode/canary-tourism-demo)](https://github.com/barckcode/canary-tourism-demo/releases)
[![License](https://img.shields.io/github/license/barckcode/canary-tourism-demo)](LICENSE)

A full-stack tourism analytics platform for Tenerife, featuring real-time data pipelines, ensemble ML forecasting, tourist segmentation, and interactive visualizations.

**Live demo:** [tourism-demo.agentcrew.sh](https://tourism-demo.agentcrew.sh)

> This project is entirely built, deployed, and maintained by autonomous AI agents orchestrated by [AgentCrew](https://agentcrew.sh/). Learn more at [/about](https://tourism-demo.agentcrew.sh/about).

## Features

- **Dashboard** — KPIs (arrivals, occupancy, ADR, RevPAR), 3D municipality heatmap, and trend sparklines
- **Prediction Engine** — Ensemble forecasting (SARIMA, Holt-Winters, Seasonal Naive) with 80%/95% confidence intervals
- **Scenario Engine** — What-if analysis: adjust occupancy, ADR, and foreign tourist ratio to simulate outcomes
- **Tourist Profiles** — K-Means clustering of survey microdata with nationality breakdowns and Sankey flows
- **Data Explorer** — Browse all indicators with interactive time series charts
- **Automated ETL** — Scheduled pipelines fetch data weekly from ISTAC, INE, and CKAN public APIs

## Tech Stack

### Backend

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.115 |
| Database | SQLite + SQLAlchemy 2.0 |
| ML | statsmodels (SARIMA/HW), scikit-learn (K-Means, GBR) |
| Scheduler | APScheduler |
| HTTP Client | httpx (async) |

### Frontend

| Component | Technology |
|-----------|-----------|
| Framework | React 19 + TypeScript 5.7 |
| Build | Vite 6 |
| Visualization | D3.js 7, Deck.gl 9, MapLibre GL |
| Styling | Tailwind CSS 3.4 |
| Animation | Framer Motion 12 |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| Containers | Docker + Docker Compose |
| Reverse Proxy | Nginx |
| SSL/TLS | Cloudflare (Full Strict) + Origin CA |
| CI/CD | GitHub Actions → GHCR |

## Data Sources

All data is sourced from official public institutions:

- **[ISTAC](https://www.gobiernodecanarias.org/istac/)** — Instituto Canario de Estadística: 14 tourism indicators (arrivals, occupancy, ADR, RevPAR, etc.)
- **[INE](https://www.ine.es/)** — Instituto Nacional de Estadística: hotel occupancy surveys, apartment and rural tourism data
- **[EGT](https://www.gobiernodecanarias.org/istac/)** — Encuesta sobre Gasto Turístico: individual tourist spending surveys with demographics and satisfaction data

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Raw data files in `tenerife-tourism-data/` (ISTAC CSVs, INE JSONs, EGT microdata)

### Development

```bash
# Clone the repo
git clone https://github.com/barckcode/canary-tourism-demo.git
cd canary-tourism-demo

# Start with local builds
docker compose up -d

# Frontend: http://localhost:8080
# Backend API: http://localhost:8000/api
# Health check: http://localhost:8000/health
```

### Production

```bash
# Pull and run pre-built images from GHCR
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/dashboard/kpis` | Latest KPIs |
| GET | `/api/dashboard/summary` | Trend data (24m arrivals, 12m occupancy, forecast) |
| GET | `/api/timeseries` | Historical time series by indicator |
| GET | `/api/timeseries/indicators` | List available indicators |
| GET | `/api/predictions` | Forecast with confidence intervals |
| GET | `/api/predictions/compare` | Compare all 4 models |
| GET | `/api/profiles` | Tourist cluster summaries |
| GET | `/api/profiles/nationalities` | Stats by nationality |
| GET | `/api/profiles/flows` | Sankey flow data |
| POST | `/api/scenarios` | Run what-if scenario |
| GET | `/health` | Health check |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (dashboard, timeseries, predictions, profiles, scenarios)
│   │   ├── db/           # SQLAlchemy models, database setup, data seeding
│   │   ├── etl/          # ETL pipelines, scheduler, data source connectors (ISTAC, INE, CKAN)
│   │   └── models/       # ML models (forecaster, profiler, scenario engine)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/          # API client and React hooks
│   │   ├── pages/        # Dashboard, Forecast, Profiles, Data Explorer, About
│   │   └── components/   # Layout, charts (D3), map (Deck.gl), shared UI
│   ├── Dockerfile
│   └── package.json
├── docs/
│   └── CICD.md           # CI/CD pipeline and versioning policy
├── docker-compose.yml      # Development (local builds)
├── docker-compose.prod.yml # Production (GHCR images)
├── VERSION                 # Current version (triggers releases)
└── LICENSE                 # Apache 2.0
```

## Releases

Releases are automated via GitHub Actions. Update the `VERSION` file and push to `main` to trigger:

1. Docker image builds → pushed to GHCR
2. Git tag + GitHub Release with auto-generated notes
3. Production deployment via SSH

See [docs/CICD.md](docs/CICD.md) for the full CI/CD documentation and versioning policy.

## License

This project is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE) file for details.
