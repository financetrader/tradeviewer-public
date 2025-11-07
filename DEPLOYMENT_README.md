# Server Deployment Package

This directory contains everything needed to deploy the wallet monitoring application to your server.

## Contents

- **Application Code**: All Python files, services, database models, utilities, templates, and static files
- **Docker Configuration**: Dockerfile, docker-compose.yml, .dockerignore
- **Dependencies**: requirements.txt
- **Configuration Template**: env.example (copy to .env and configure)
- **Database**: data/wallet.db (your existing database with all data)
- **Database Backup**: data/wallet_backup_20251106_150411.db (backup copy)
- **Documentation**: README.md and docs/ directory

## Deployment Steps

1. **Copy this entire directory to your server**
   ```bash
   scp -r deployment/ user@your-server:/opt/wallet-app/
   ```

2. **On the server, navigate to the directory**
   ```bash
   cd /opt/wallet-app
   ```

3. **Create .env file**
   ```bash
   cp env.example .env
   # Edit .env and set FLASK_SECRET_KEY
   # Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

4. **Start with Docker**
   ```bash
   docker-compose up -d
   ```

5. **Verify it's running**
   ```bash
   docker-compose ps
   curl http://localhost:5000/health
   ```

## Important Notes

- The database (`data/wallet.db`) is included and will be preserved via Docker volume mounts
- Make sure Docker and Docker Compose are installed on the server
- The application will run on port 5000 by default
- Logs will be written to the `logs/` directory (created automatically)

## What's Excluded

- `__pycache__/` directories
- `*.pyc` files
- `logs/` directory (will be created on server)
- `.git/` directory
- Test files
- Archived documentation

See README.md for complete documentation.

