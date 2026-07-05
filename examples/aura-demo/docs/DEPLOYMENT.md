# ASSURE 2.0 Deployment Guide

This guide covers running the ASSURE 2.0 pilot stack locally with Docker Compose and deploying it to Render/Vercel, AWS, GCP, and Azure. All data is synthetic.

---

## Local quickstart (Docker Compose)

The root `docker-compose.yml` brings up four services:

| Service | Role | Internal URL | Exposed on host |
|---|---|---|---|
| `kernel` | Deterministic rules engine (`assure-kernel`) | `http://kernel:8000` | via nginx `/kernel/*`, `/v1/*`, `/docs` |
| `backend` | Aura-demo FastAPI API | `http://backend:8000` | via nginx `/api/*` |
| `frontend` | Next.js 14 app | `http://frontend:3000` | via nginx `/` |
| `nginx` | Reverse proxy + security headers | `http://nginx:80` | `http://localhost:8080` |

### Steps

```bash
# From examples/aura-demo/
docker compose up --build
```

Wait for the healthchecks to pass, then verify:

```bash
python scripts/smoke_docker.py
```

Expected output:

```text
OK:   nginx edge (/nginx-health)
OK:   kernel health (/v1/health)
OK:   backend health (/api/health)
OK:   frontend root (/)
```

The app is available at http://localhost:8080.

### Persistent data

The backend SQLite book lives in a named Docker volume `backend-data` mounted at `/app/data`. On first start the backend generates the 34k synthetic book; subsequent restarts reuse the existing database.

To wipe the book and regenerate:

```bash
docker compose down -v
docker compose up --build
```

---

## Render + Vercel (existing path)

The repository already ships with:

- `backend/render.yaml` — deploys the FastAPI backend on Render.
- `frontend/vercel.json` — deploys the Next.js frontend on Vercel.

### Backend on Render

1. Create a new **Web Service** on Render and point it at this repo.
2. Set root directory to `backend`.
3. Add environment variables:
   - `ANTHROPIC_API_KEY` — only needed for Claude-powered features (explain, chat, voice).
   - `MARKET_SEED` — optional, default `42`.
4. Render runs `pip install -r requirements.txt` then `uvicorn main:app --host 0.0.0.0 --port $PORT`.
5. Note the deployed URL (e.g. `https://assure-backend.onrender.com`).

### Frontend on Vercel

1. Import the repo into Vercel.
2. Set root directory to `frontend`.
3. Add environment variable:
   - `API_URL` — the Render backend URL from above.
4. Vercel builds with `npm run build` and serves the Next.js app.
5. The frontend rewrites same-origin `/api/*` to the backend, so the client never sees the backend URL.

---

## AWS

Recommended pattern: ECS Fargate with an Application Load Balancer.

1. **Container images**
   - Build and push each image to Amazon ECR:
     ```bash
     aws ecr get-login-password | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
     docker build -f backend/Dockerfile -t assure-backend .
     docker build -f frontend/Dockerfile -t assure-frontend .
     docker build -f packages/assure-kernel/Dockerfile -t assure-kernel packages/assure-kernel
     docker build -f nginx/Dockerfile -t assure-nginx .
     ```
2. **ECS cluster**
   - Create an ECS cluster (Fargate).
   - Define task definitions for `kernel`, `backend`, `frontend`, and `nginx`.
   - Use an EFS volume or Fargate ephemeral storage for `/app/data` on the backend task.
3. **ALB**
   - Create an ALB with a target group pointing to the `nginx` service.
   - Terminate TLS at the ALB (ACM certificate).
4. **Secrets**
   - Store `ANTHROPIC_API_KEY` in AWS Secrets Manager and inject as an environment variable.
5. **IAM**
   - Task execution role with `AmazonECSTaskExecutionRolePolicy`.
   - Task role with least-privilege access to ECR and Secrets Manager.

---

## Google Cloud Platform

Recommended pattern: Cloud Run for each service or GKE Autopilot.

### Cloud Run

1. Build and push images to Artifact Registry:
   ```bash
   gcloud auth configure-docker $REGION-docker.pkg.dev
   docker build -f backend/Dockerfile -t $REGION-docker.pkg.dev/$PROJECT/assure/backend .
   docker push $REGION-docker.pkg.dev/$PROJECT/assure/backend
   ```
2. Deploy each service:
   ```bash
   gcloud run deploy assure-backend --image $REGION-docker.pkg.dev/$PROJECT/assure/backend --region $REGION
   ```
3. For the backend, mount a Cloud Storage FUSE bucket or use Cloud SQL (Postgres) for persistent state instead of local SQLite.
4. Put Cloud Run services behind a Load Balancer with Cloud Armor for WAF + TLS.

### GKE Autopilot

1. Create a GKE Autopilot cluster.
2. Deploy the four services using the Kubernetes manifests generated from `docker-compose.yml` (use `kompose convert` or hand-author).
3. Use a GCE ingress or Istio/ASM for routing and TLS.

---

## Azure

Recommended pattern: Azure Container Apps or AKS.

### Azure Container Apps

1. Build and push images to Azure Container Registry:
   ```bash
   az acr login --name $ACR_NAME
   docker build -f backend/Dockerfile -t $ACR_NAME.azurecr.io/assure/backend .
   docker push $ACR_NAME.azurecr.io/assure/backend
   ```
2. Create Container Apps for `kernel`, `backend`, `frontend`, and `nginx`.
3. Use a single Container Apps Environment and internal ingress for service-to-service communication.
4. Expose only the `nginx` app on a public ingress with HTTPS.
5. For persistence, mount an Azure Files share on the backend app at `/app/data` or switch to Azure Database for PostgreSQL.

### AKS

1. Create an AKS cluster and attach ACR.
2. Deploy manifests for the four services.
3. Use an Ingress Controller (NGINX or Application Gateway) with cert-manager for TLS.

---

## Production checklist

- [ ] Use a managed Postgres database instead of SQLite for multi-replica backend deployments. The backend already imports `psycopg` and uses SQLAlchemy-style raw SQL; adapt `core/storage.py` connection logic.
- [ ] Restrict `CORS_ALLOWED_ORIGINS` to the exact frontend origin.
- [ ] Do not commit real secrets; use the cloud provider secret manager.
- [ ] Enable centralized logging (CloudWatch / Cloud Logging / Azure Monitor).
- [ ] Enable automated vulnerability scanning on container images.
- [ ] Run backups for the persistent volume / database.
- [ ] Pin base image tags and dependency versions for reproducible builds.
- [ ] Configure healthchecks and auto-restart policies.
- [ ] Review the `docs/SOC2-CHECKLIST.md` before any pilot with regulated data.
