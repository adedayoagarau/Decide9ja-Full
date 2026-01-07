# Decide9ja Deployment Guide

This directory contains deployment configurations for running the Decide9ja scheduler and news processing services.

## Overview

The background services include:

| Service | Description | Frequency |
|---------|-------------|-----------|
| News Scraper | Scrapes Nigerian news sources | Every 1 hour |
| News Indexer | Generates embeddings for RAG | Every 2 hours |
| Issue Extractor | Extracts political issues via Claude | Every 3 hours |
| News Agent | Continuous article processing | Every 5 minutes |
| Daily Digest | WhatsApp digest to users | 7 AM WAT |
| News Cleanup | Remove articles > 30 days | 3 AM daily |

## Deployment Options

### Option 1: Systemd (Linux VPS/VM)

Best for: Dedicated servers, VPS, or VMs running Linux.

```bash
# Install
cd deployment/systemd
sudo ./install.sh

# Manage services
sudo systemctl status decide9ja-scheduler
sudo systemctl status decide9ja-news-worker
journalctl -u decide9ja-scheduler -f  # View logs
```

**Files:**
- `decide9ja-scheduler.service` - Main scheduler service
- `decide9ja-news-worker.service` - News processing worker
- `install.sh` - Installation script

### Option 2: Docker Compose

Best for: Development, small deployments, or when you need PostgreSQL/Redis included.

```bash
cd deployment/docker

# Copy and configure environment
cp .env.example .env
vim .env  # Add your API keys

# Start services
docker-compose up -d

# View logs
docker-compose logs -f scheduler
docker-compose logs -f news-worker

# Stop
docker-compose down
```

**Services included:**
- PostgreSQL database
- Redis cache
- Scheduler container
- News worker container

### Option 3: AWS (ECS Fargate + CloudWatch)

Best for: Production deployments on AWS with managed infrastructure.

```bash
cd deployment/cloud/aws/terraform

# Initialize
terraform init

# Plan
terraform plan -var="anthropic_api_key=sk-..." -var="openai_api_key=sk-..."

# Apply
terraform apply

# Build and push Docker image
aws ecr get-login-password | docker login --username AWS --password-stdin <ecr-url>
docker build -t decide9ja-scheduler -f deployment/docker/Dockerfile.scheduler .
docker tag decide9ja-scheduler:latest <ecr-url>/decide9ja-scheduler:latest
docker push <ecr-url>/decide9ja-scheduler:latest
```

**Resources created:**
- ECS Fargate cluster with scheduler task
- RDS PostgreSQL (db.t3.micro)
- ElastiCache Redis
- Secrets Manager for API keys
- CloudWatch Logs

### Option 4: GCP (Cloud Run + Cloud Scheduler)

Best for: Serverless deployments on Google Cloud.

```bash
cd deployment/cloud/gcp

# Set up secrets
gcloud secrets create anthropic-api-key --data-file=<(echo -n "sk-...")
gcloud secrets create openai-api-key --data-file=<(echo -n "sk-...")

# Deploy via Cloud Build
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=_REGION=europe-west1,_DATABASE_URL=...,_REDIS_URL=...
```

**Resources created:**
- Cloud Run Job for scheduler
- Cloud Run Service for news worker
- Cloud Scheduler triggers

### Option 5: Azure Functions

Best for: Serverless, timer-triggered execution on Azure.

```bash
cd deployment/cloud/azure

# Create Function App
az functionapp create \
  --resource-group decide9ja-rg \
  --consumption-plan-location westeurope \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name decide9ja-scheduler \
  --storage-account decide9jastorage

# Configure settings
az functionapp config appsettings set \
  --name decide9ja-scheduler \
  --resource-group decide9ja-rg \
  --settings \
    "ANTHROPIC_API_KEY=sk-..." \
    "OPENAI_API_KEY=sk-..." \
    "DATABASE_URL=postgresql://..."

# Deploy
func azure functionapp publish decide9ja-scheduler
```

## Environment Variables

All deployments require these environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic Claude API key |
| `OPENAI_API_KEY` | Yes | OpenAI API key (for embeddings) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | No | Redis connection string (optional caching) |
| `TWILIO_ACCOUNT_SID` | No | For WhatsApp messaging |
| `TWILIO_AUTH_TOKEN` | No | For WhatsApp messaging |

## Monitoring

### Logs

```bash
# Systemd
journalctl -u decide9ja-scheduler -f

# Docker
docker-compose logs -f scheduler

# AWS
aws logs tail /ecs/decide9ja-scheduler --follow

# GCP
gcloud logging read "resource.type=cloud_run_job"

# Azure
az monitor app-insights query --app decide9ja-insights --analytics-query "traces | take 100"
```

### Health Check

All deployments expose a health endpoint:

```bash
# Local/Docker
curl http://localhost:8000/health

# AWS (via ALB)
curl https://your-alb-url/health

# Azure Functions
curl https://decide9ja-scheduler.azurewebsites.net/api/health
```

## Manual Job Execution

Run a specific job manually:

```bash
# Systemd/Docker
python -m app.scheduler_unified --job news

# Azure Functions (HTTP trigger)
curl -X POST "https://decide9ja-scheduler.azurewebsites.net/api/trigger/news?code=<function_key>"
```

Available jobs: `news`, `index`, `issues`, `dossiers`, `cards`, `cleanup`, `health`

## Scaling

### Horizontal Scaling

The scheduler itself should run as a single instance (APScheduler handles timing).
The news worker can be scaled:

```bash
# Docker
docker-compose up -d --scale news-worker=3

# AWS ECS
aws ecs update-service --cluster decide9ja --service news-worker --desired-count 3

# GCP Cloud Run
gcloud run services update decide9ja-news-worker --max-instances=5
```

### Resource Tuning

| Service | Min Memory | Recommended | Max CPU |
|---------|-----------|-------------|---------|
| Scheduler | 512MB | 1GB | 1 vCPU |
| News Worker | 256MB | 512MB | 0.5 vCPU |

## Troubleshooting

### Common Issues

1. **"No module named app"**
   - Ensure `PYTHONPATH` includes the backend directory

2. **Database connection errors**
   - Check `DATABASE_URL` format
   - Ensure database is accessible from the container/VM

3. **API rate limits**
   - Adjust `NEWS_SCRAPE_INTERVAL_HOURS` in environment
   - Reduce `ISSUE_EXTRACTION_LIMIT`

4. **Memory issues**
   - Increase container/VM memory
   - Reduce batch sizes in scheduler jobs

### Debug Mode

```bash
# Run scheduler in foreground with debug logging
LOG_LEVEL=DEBUG python -m app.scheduler_unified
```

## Cost Estimates

| Platform | Config | Est. Monthly Cost |
|----------|--------|-------------------|
| VPS (DigitalOcean) | 2GB Droplet | $12/mo |
| Docker (self-hosted) | 2GB VM | $10-20/mo |
| AWS ECS Fargate | 0.5 vCPU, 1GB | $15-25/mo |
| GCP Cloud Run | On-demand | $5-15/mo |
| Azure Functions | Consumption | $5-10/mo |

*Estimates exclude database and API costs.*
