# CI/CD Pipeline

## Overview

Releases are fully automated via GitHub Actions. Pushing a change to the `VERSION` file on the `main` branch triggers the entire release pipeline: image builds, registry push, GitHub Release creation, and production deployment.

## Release Flow

```
Developer updates VERSION file
  |
  v
Push to main branch
  |
  v
GitHub Actions (release.yml) triggers
  |
  ├─ 1. Read version from VERSION file
  ├─ 2. Check if tag already exists (skip if duplicate)
  ├─ 3. Login to GHCR (GitHub Container Registry)
  ├─ 4. Build backend Docker image
  ├─ 5. Build frontend Docker image
  ├─ 6. Push both images to GHCR with version tag + latest
  ├─ 7. Create git tag (v0.x.x)
  ├─ 8. Create GitHub Release with auto-generated notes
  └─ 9. Deploy to production server via SSH
        ├─ Pull new images from GHCR
        ├─ Restart containers with docker-compose.prod.yml
        └─ Prune old images
```

## How to Release

1. Make your code changes and commit them to `main`
2. When ready to release, update the `VERSION` file with the new version number
3. Commit and push:
   ```bash
   git add VERSION
   git commit -m "Release vX.Y.Z"
   git push origin main
   ```
4. The pipeline runs automatically — monitor progress at:
   **GitHub → Actions → Release**
5. Once complete:
   - Docker images are available at `ghcr.io/barckcode/canary-tourism-demo/backend:X.Y.Z` and `frontend:X.Y.Z`
   - A GitHub Release is published with auto-generated notes listing all changes since the previous release
   - Production server is updated and running the new version

## Versioning Policy (SemVer)

Version format: **MAJOR.MINOR.PATCH**

### PATCH — `0.0.X`

Small fixes and corrections:
- Typo fixes
- CSS/styling adjustments
- Minor bug fixes
- Dependency version bumps
- Documentation updates

Example: `0.1.0` → `0.1.1`

### MINOR — `0.X.0`

New features or significant fixes:
- New pages or UI components
- New API endpoints
- New data sources or indicators
- Significant bug fixes that change behavior
- ML model improvements
- Performance optimizations

Example: `0.1.0` → `0.2.0`

### MAJOR — `X.0.0`

Breaking or structural changes:
- Database schema changes (new tables, column modifications, migrations)
- Data model restructuring
- API contract changes (breaking changes to request/response formats)
- Major architectural changes (new services, infrastructure redesign)
- Framework or language version upgrades that affect the full stack

Example: `0.5.0` → `1.0.0`

## Docker Images

Images are published to GitHub Container Registry (GHCR):

| Image | Registry Path |
|-------|--------------|
| Backend | `ghcr.io/barckcode/canary-tourism-demo/backend` |
| Frontend | `ghcr.io/barckcode/canary-tourism-demo/frontend` |

Each release pushes two tags per image:
- **Version tag**: `backend:0.2.0` (immutable, for rollback)
- **Latest tag**: `backend:latest` (always points to newest release)

## Production Deployment

The production server runs `docker-compose.prod.yml` which references GHCR images:

```yaml
services:
  backend:
    image: ghcr.io/barckcode/canary-tourism-demo/backend:${VERSION:-latest}
  frontend:
    image: ghcr.io/barckcode/canary-tourism-demo/frontend:${VERSION:-latest}
```

The deploy step connects via SSH and runs:
```bash
cd /home/canary/tenerife-tourism
export VERSION=X.Y.Z
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
docker image prune -f
```

## Manual Rollback

If a release causes issues, rollback to a previous version:

```bash
export VERSION=0.1.0  # previous working version
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## GitHub Secrets Required

The pipeline requires these secrets in **GitHub → Settings → Secrets → Actions**:

| Secret | Description |
|--------|-------------|
| `SERVER_HOST` | Production server IP |
| `SERVER_USER` | SSH username |
| `SSH_PRIVATE_KEY` | SSH private key for authentication |

`GITHUB_TOKEN` is provided automatically by GitHub Actions for GHCR authentication.

## Workflow File

The pipeline is defined in `.github/workflows/release.yml` and uses:
- `actions/checkout@v4` — Repository checkout
- `docker/login-action@v3` — GHCR authentication
- `docker/setup-buildx-action@v3` — Docker Buildx for build caching
- `docker/build-push-action@v6` — Image build and push with GHA cache
- `softprops/action-gh-release@v2` — GitHub Release creation
- `appleboy/ssh-action@v1` — SSH deployment
