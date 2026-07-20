# Ceche Deployment Guide

## Architecture

```
Nginx (80/443) → Astro (4321) + FastAPI (8080) → MySQL 8
```

- **Nginx**: Reverse proxy, SSL termination (Let's Encrypt)
- **Astro**: Node SSR server (public pages, admin panel)
- **FastAPI**: Python API server (appraisal engine, admin CRUD)
- **MySQL 8**: Persistent storage

## Quick Start

```bash
# 1. Install MySQL 8 and create database
mysql -u root -e "CREATE DATABASE ceche CHARACTER SET utf8mb4;"
mysql -u root -e "CREATE USER 'ceche'@'localhost' IDENTIFIED BY '<your-password>';"
mysql -u root -e "GRANT ALL ON ceche.* TO 'ceche'@'localhost';"
mysql -u ceche -p ceche < database/schema.sql

# 2. Set environment variables (see below)

# 3. Start FastAPI
pip install -r requirements.txt
ceche server serve --port 8080

# 4. Build and start Astro
cd web && npm install && npm run build
PORT=4321 node dist/server/entry.mjs

# 5. Configure Nginx (see deploy/nginx.conf.example)
```

## Required Environment Variables

| Variable | Description |
|---|---|
| `CECHE_MYSQL_HOST` | MySQL host |
| `CECHE_MYSQL_USER` | MySQL user |
| `CECHE_MYSQL_PASSWORD` | MySQL password |
| `CECHE_MYSQL_DATABASE` | Database name |
| `CECHE_ADMIN_SECRET` | JWT signing secret |
| `CECHE_ADMIN_PASSWORD` | First admin password |
| `DEEPSEEK_API_KEY` | AI provider key |
| `CECHE_AI_ENABLED` | Set to `true` to enable AI |
| `CECHE_OPR_KEY` | OpenPageRank API key |
| `CECHE_GOOGLE_CSE_KEY` | Google Custom Search key |
| `CECHE_GOOGLE_CSE_CX` | Google Custom Search CX |

## Optional Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CECHE_AI_TEMPERATURE` | `0.1` | AI temperature |
| `CECHE_AI_MAX_TOKENS` | `150` | AI max tokens per call |

## Systemd (optional)

Copy `deploy/ceche-fastapi.service.example` to `/etc/systemd/system/`:

```bash
cp deploy/ceche-fastapi.service.example /etc/systemd/system/ceche-fastapi.service
systemctl daemon-reload
systemctl enable ceche-fastapi
systemctl start ceche-fastapi
```

## Nginx (optional)

Copy `deploy/nginx.conf.example` to your Nginx config and adjust `server_name`:

```bash
cp deploy/nginx.conf.example /etc/nginx/sites-available/ceche
ln -s /etc/nginx/sites-available/ceche /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

## Seed Data

```bash
mysql -u ceche -p ceche < database/seeds/all.sql
```

## Docker (alternative)

```bash
docker compose up -d
```
