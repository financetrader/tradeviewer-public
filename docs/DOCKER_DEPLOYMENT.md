# Docker Deployment Guide

## Overview

The wallet viewer application runs in Docker containers managed by docker-compose. Understanding this setup is critical to avoid deployment errors.

## Container Architecture

### Services
1. **wallet-app** - Main Flask application
2. **nginx-proxy** - Reverse proxy with authentication
3. **hello-demo** - Test service

### Network
All services run on the `app-network` Docker network, allowing them to communicate.

## Critical: How Code Updates Work

### ⚠️ IMPORTANT: The container uses BUILT code, not live files

The wallet-app container is built from a Dockerfile, which means:
- Code is **COPIED INTO** the container during build
- Changes to files in `/home/ubuntu/app-tradeviewer/` do NOT automatically appear in the container
- You MUST rebuild the container to see code changes

### What IS mounted as volumes:
- `/home/ubuntu/app-tradeviewer/data` → `/app/data` (database files)
- `/home/ubuntu/app-tradeviewer/logs` → `/app/logs` (log files)

### What is NOT mounted:
- Python code (`.py` files)
- Templates (`.html` files)
- Configuration files
- Documentation

## Deployment Process

### Standard Deployment (Recommended)

```bash
cd /home/ubuntu

# Stop all services
docker-compose stop

# Rebuild the wallet service with latest code
docker-compose build wallet

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
```

### Quick Rebuild (wallet only)

```bash
cd /home/ubuntu
docker-compose stop wallet
docker-compose build wallet
docker-compose up -d wallet
docker-compose restart nginx  # Ensure nginx reconnects
```

### Check Service Status

```bash
# List all containers
docker-compose ps

# Should show:
# - wallet-app: Up (healthy)
# - nginx-proxy: Up  
# - hello-demo: Up

# Check specific service logs
docker-compose logs wallet --tail 50
docker-compose logs nginx --tail 20
```

## Common Issues and Solutions

### Issue 1: 404 Error / "Cannot connect to service"

**Symptom**: Nginx returns 404 or connection errors when accessing the site

**Cause**: wallet-app container is not on the same Docker network as nginx

**Solution**:
```bash
# Stop all services
docker-compose stop

# Remove orphaned containers
docker-compose down

# Restart everything
docker-compose up -d

# Verify network
docker network inspect app-network
# Should show wallet-app, nginx-proxy, hello-demo
```

### Issue 2: Code Changes Not Appearing

**Symptom**: You changed code but the app still shows old behavior

**Cause**: Container has old code built into it

**Solution**:
```bash
cd /home/ubuntu
docker-compose build wallet  # Rebuild with new code
docker-compose up -d wallet  # Start with new image
```

### Issue 3: docker-compose KeyError: 'ContainerConfig'

**Symptom**: Error when running docker-compose up

**Cause**: Docker image metadata corruption

**Solution**:
```bash
# Stop and remove all containers
docker-compose down

# Remove the problematic container manually
docker rm -f wallet-app nginx-proxy hello-demo

# Rebuild and start fresh
docker-compose build
docker-compose up -d
```

### Issue 4: Container Running but Code Not Updated

**Symptom**: Container is running but changes aren't reflected

**Diagnostic**:
```bash
# Check if code in container matches your files
docker exec wallet-app cat /app/app.py | head -20
# Compare with: cat /home/ubuntu/app-tradeviewer/app.py | head -20

# Check container image age
docker images | grep ubuntu_wallet
```

**Solution**: Force rebuild without cache
```bash
cd /home/ubuntu
docker-compose build --no-cache wallet
docker-compose up -d wallet
```

## Manual Container Management (Emergency Only)

If docker-compose fails, you can manage containers manually:

### Stop and Remove Manual Container
```bash
docker stop wallet-app
docker rm wallet-app
```

### Build Image Manually
```bash
cd /home/ubuntu
docker build -t ubuntu_wallet:latest ./app-tradeviewer
```

### Run Container Manually
```bash
docker run -d \
  --name wallet-app \
  --network ubuntu_app-network \
  -v ./app-tradeviewer/data:/app/data:rw \
  -v ./app-tradeviewer/logs:/app/logs:rw \
  --env-file ./app-tradeviewer/.env \
  ubuntu_wallet:latest
```

### ⚠️ Warning: Manual containers won't reconnect to docker-compose
If you create containers manually, docker-compose may have issues managing them. Always prefer docker-compose when possible.

## Database Migrations

### Running Migrations

Migrations need to run INSIDE the container:

```bash
# Option 1: Using Python
docker exec wallet-app python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('/app/data/wallet.db')
cursor = conn.cursor()
cursor.execute('ALTER TABLE equity_snapshots ADD COLUMN initial_margin FLOAT')
conn.commit()
conn.close()
EOF

# Option 2: Using SQL file
docker exec wallet-app python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/wallet.db')
cursor = conn.cursor()
cursor.executescript(open('/app/migrations/migration.sql').read())
conn.commit()
conn.close()
"
```

### Checking Schema

```bash
# Check if column exists
docker exec wallet-app python3 -c "
import sqlite3
conn = sqlite3.connect('/app/data/wallet.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(equity_snapshots)')
for row in cursor.fetchall():
    print(row)
conn.close()
"
```

## Verification Checklist

After any deployment, verify:

```bash
# 1. Containers are running
docker ps | grep -E "wallet|nginx|hello"

# 2. wallet-app is healthy
docker inspect wallet-app | grep -A 5 "Health"

# 3. Network connectivity
docker network inspect ubuntu_app-network

# 4. App responds internally
docker exec wallet-app curl -s http://localhost:5000/ | head -5

# 5. Nginx proxy works
curl -s http://localhost:5001/ | head -5
# Should show: 401 Authorization Required (correct - needs auth)

# 6. External access works
curl -s http://13.49.127.74:5001/
# Should show: 401 Authorization Required
```

## Port Mapping

- **Internal**: wallet-app runs on port 5000 inside container
- **Nginx**: Listens on host port 5001, proxies to wallet-app:5000
- **External**: http://13.49.127.74:5001/ (with HTTP basic auth)

## Logs

### View Real-time Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f wallet

# Last 100 lines
docker-compose logs --tail 100 wallet
```

### Log Files on Host
- Application logs: `/home/ubuntu/app-tradeviewer/logs/`
- Exchange traffic: `/home/ubuntu/app-tradeviewer/logs/exchange_traffic.log`

## Best Practices

1. **Always use docker-compose** for management
2. **Always rebuild** after code changes
3. **Always verify** after deployment
4. **Never mix** manual docker commands with docker-compose
5. **Commit before deploying** to preserve working states
6. **Test in feature branches** before merging to master

## Development Workflow

```bash
# 1. Create feature branch
cd /home/ubuntu/app-tradeviewer
git checkout -b feature/my-feature

# 2. Make code changes
# ... edit files ...

# 3. Rebuild and test
cd /home/ubuntu
docker-compose build wallet
docker-compose up -d wallet

# 4. Verify changes
docker-compose logs wallet --tail 50

# 5. Test application
curl http://localhost:5001/

# 6. Commit if working
cd /home/ubuntu/app-tradeviewer
git add -A
git commit -m "feat: description"

# 7. Merge to master when stable
git checkout master
git merge feature/my-feature
```

## Emergency Rollback

If something breaks:

```bash
# 1. Check current branch
cd /home/ubuntu/app-tradeviewer
git branch

# 2. Checkout working branch
git checkout master  # or last known good branch

# 3. Rebuild with old code
cd /home/ubuntu
docker-compose build wallet
docker-compose up -d wallet

# 4. Verify
docker-compose ps
docker exec wallet-app curl -s http://localhost:5000/ | head -5
```

## Container Health

The wallet-app container has a health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1
```

Check health status:
```bash
docker inspect wallet-app --format='{{.State.Health.Status}}'
# Should return: healthy
```

