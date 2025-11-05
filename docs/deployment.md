# Deployment Guide

This document explains how to set up automated deployment for the Unifiles project using GitHub Actions.

## Overview

We have deployment workflows:

1. **Basic SSH Deployment** (`deploy.yml`) - Deploys directly to a server via SSH


## Prerequisites

### For Basic SSH Deployment

1. A server with SSH access
2. Python 3.11+ and uv installed on the server
3. A systemd service for the application


## Setup Instructions

### 1. Repository Secrets

Add the following secrets to your GitHub repository:

#### For Basic SSH Deployment:
```
HOST                    # Server IP or hostname
USERNAME                # SSH username
SSH_PRIVATE_KEY         # SSH private key content
PORT                    # SSH port (default: 22)
PROJECT_PATH            # Path to project on server (default: /var/www/unifiles)
```

### 2. Server Setup

#### Basic SSH Deployment Setup:

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone your repository
git clone https://github.com/your-username/unifiles.git /var/www/unifiles
cd /var/www/unifiles

# 3. Install dependencies
uv sync

# 4. Create systemd service
sudo nano /etc/systemd/system/unifiles.service
```

**unifiles.service content:**
```ini
[Unit]
Description=Unifiles FastAPI Application
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/var/www/unifiles
Environment=PATH=/var/www/unifiles/.venv/bin
ExecStart=/var/www/unifiles/.venv/bin/uvicorn unifiles.server.v1.main:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# 5. Enable and start service
sudo systemctl enable unifiles
sudo systemctl start unifiles
```

### 3. Workflow Triggers

#### Basic SSH Deployment:
- **Automatic**: Triggers on push to `main`, `master`, `nbfile` branch
- **Manual**: Can be triggered manually from GitHub Actions tab

### 4. Creating a Release

To deploy to production with Docker workflow:

```bash
# Tag a new version
git tag v1.0.0
git push origin v1.0.0
```

This will:
1. Build and push Docker image to GitHub Container Registry
2. Deploy to staging environment
3. Deploy to production environment (zero-downtime)

## Local Development



### Using uv

```bash
# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Run application
uv run uvicorn unifiles.server.v1.main:app --reload
```

## Monitoring

### Health Checks

Both workflows include health checks:
- **HTTP Health Check**: `GET /health`
- **Docker Health Check**: Built into Dockerfile
- **Systemd Health Check**: Automatic restart on failure

### Logs

- **Basic Deployment**: Logs via systemd (`journalctl -u unifiles -f`)
- **Docker Deployment**: Logs via Docker (`docker logs unifiles-production -f`)

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   - Check SSH key format (should be OpenSSH private key)
   - Verify server firewall settings
   - Ensure user has proper permissions

2. **Docker Build Failed**
   - Check Dockerfile syntax
   - Verify all dependencies are available
   - Check GitHub Container Registry permissions

3. **Service Won't Start**
   - Check environment variables
   - Verify database connectivity
   - Check port availability

### Debug Commands

```bash
# Check service status
sudo systemctl status unifiles

# View recent logs
journalctl -u unifiles -n 50

# Test Docker container locally
docker run --rm -p 8000:8000 your-image:latest

# Check Docker container logs
docker logs container-name
```

## Security Considerations

1. **SSH Keys**: Use dedicated deployment keys with minimal permissions
2. **Secrets**: Store sensitive data in GitHub Secrets, not in code
3. **Firewall**: Restrict SSH access to GitHub Actions IP ranges
4. **SSL/TLS**: Use HTTPS in production with proper certificates
5. **Container Security**: Regular image updates and vulnerability scanning

## Advanced Configuration

### Multi-Environment Setup

You can extend the workflows to support multiple environments:

```yaml
strategy:
  matrix:
    environment: [staging, production]
    include:
      - environment: staging
        host: ${{ secrets.STAGING_HOST }}
      - environment: production
        host: ${{ secrets.PROD_HOST }}
```

### Blue-Green Deployment

For zero-downtime deployments, implement blue-green deployment pattern by modifying the Docker deployment script.

### Database Migrations

Add migration steps to your workflow:

```yaml
- name: Run migrations
  run: |
    uv run python scripts/migrate.py
```