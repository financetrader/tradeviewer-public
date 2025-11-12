# Fresh Server Installation Guide

Complete step-by-step guide to install and deploy the Apex Omni Wallet Viewer application on a fresh server.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Pre-Installation Checklist](#pre-installation-checklist)
3. [Installation Steps](#installation-steps)
4. [Post-Installation Verification](#post-installation-verification)
5. [Production Deployment](#production-deployment)
6. [Backup Strategy](#backup-strategy)
7. [Monitoring](#monitoring)
8. [Updating the Application](#updating-the-application)
9. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Operating System
- **Linux**: Ubuntu 18.04+, Debian 10+, CentOS 7+, or any modern Linux distribution
- **macOS**: 10.14+ (for development)
- **Windows**: Not recommended (use WSL2 if needed)

### Software Dependencies
- **Python**: 3.8 or higher (3.10+ recommended)
- **pip**: Python package manager (usually included with Python)
- **git**: For version control (recommended, optional)
- **curl**: For testing endpoints (optional, included on most systems)

### Hardware Requirements
- **Disk Space**: Minimum 500MB for application, dependencies, and database
- **RAM**: Minimum 512MB (1GB+ recommended for production)
- **Network**: Stable internet connection for API calls to exchanges

### Optional Tools (for monitoring/management)
- **screen** or **tmux**: For running application in background
- **sqlitebrowser**: For database inspection
- **systemd**: For service management (standard on modern Linux)

---

## Pre-Installation Checklist

### Step 1: Check Python Version

```bash
python3 --version  # Should be 3.8 or higher
```

If Python is not installed, install it:

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**CentOS/RHEL:**
```bash
sudo yum install python3 python3-pip python3-venv
```

**macOS:**
```bash
brew install python3
```

### Step 2: Verify pip

```bash
pip3 --version
```

### Step 3: Create Application Directory

```bash
# Create directory for application
sudo mkdir -p /opt/wallet-app

# Set proper permissions (replace 'your_user' with your username)
sudo chown your_user:your_user /opt/wallet-app

# Navigate to directory
cd /opt/wallet-app
```

### Step 4: Prepare Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Linux/macOS
# OR on Windows:
# venv\Scripts\activate

# Verify activation (prompt should show "(venv)")
```

---

## Installation Steps

### Step 1: Clone or Copy Application Code

**Option A: Using Git (Recommended)**
```bash
git clone https://github.com/your-repo/app-tradeviewer.git /tmp/app-src
cp -r /tmp/app-src/* /opt/wallet-app/
cd /opt/wallet-app
source venv/bin/activate
```

**Option B: Copy from Local Machine**
```bash
# On your local machine
scp -r /path/to/app-tradeviewer/* user@your-server:/opt/wallet-app/

# On server
cd /opt/wallet-app
source venv/bin/activate
```

### Step 2: Install Python Dependencies

```bash
# Verify virtual environment is activated (check for "(venv)" in prompt)
pip install --upgrade pip setuptools wheel

# Install project dependencies
pip install -r requirements.txt
```

**Verify Installation:**
```bash
pip list  # Should show Flask, SQLAlchemy, etc.
```

### Step 3: Create Environment Configuration

```bash
# Copy example configuration
cp env.example .env

# Edit .env file with your preferred editor
nano .env
# OR
vim .env
```

**Configure the following required variables:**

```bash
# Flask Configuration
FLASK_ENV=production  # Set to 'production' for production servers
FLASK_SECRET_KEY=<generate-with-command-below>

# Generate a strong secret key
python3 -c "import secrets; print(secrets.token_hex(32))"
# Copy the output and paste into FLASK_SECRET_KEY=

# Optional: Encryption Key for credentials
# Generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=

# Other settings (optional)
EXCHANGE_LOG_PATH=logs/exchange_traffic.log
ADMIN_LOG_TAIL=200
STALE_WALLET_HOURS=2
```

**Example .env file:**
```bash
FLASK_ENV=production
FLASK_SECRET_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
ENCRYPTION_KEY=
EXCHANGE_LOG_PATH=logs/exchange_traffic.log
ADMIN_LOG_TAIL=200
STALE_WALLET_HOURS=2
APEX_NETWORK=main
```

### Step 4: Create Required Directories

```bash
# Create logs directory (if not exists)
mkdir -p logs

# Create data directory (if not exists)
mkdir -p data

# Set appropriate permissions
chmod 755 logs
chmod 755 data
```

### Step 5: Initialize Database

```bash
# The database will be created automatically on first run
# Or verify it can be accessed
sqlite3 data/wallet.db ".tables"
```

---

## Post-Installation Verification

### Step 1: Test Application Start

```bash
# Verify virtual environment is activated
source venv/bin/activate

# Start the application
python app.py
```

**Expected output:**
```
 * Serving Flask app 'app'
 * Debug mode: off
 * Running on http://0.0.0.0:5000
Press CTRL+C to quit
```

> **Note**: The application listens on all interfaces (`0.0.0.0:5000`), meaning you can access it from any machine on your network at `http://<server-ip>:5000`

### Step 2: Test Health Endpoint

In a separate terminal on the server:
```bash
curl http://localhost:5000/health
```

From another machine:
```bash
curl http://<server-ip>:5000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

### Step 3: Access Web Interface

Open your browser and navigate to:
- **Portfolio Overview**: http://<server-ip>:5000
- **Admin Panel**: http://<server-ip>:5000/admin
- **Health Check**: http://<server-ip>:5000/health

### Step 4: Verify Application Structure

```bash
# Check directory structure
ls -la

# Verify key files exist
test -f app.py && echo "✓ app.py exists"
test -f requirements.txt && echo "✓ requirements.txt exists"
test -f .env && echo "✓ .env exists"
test -d data && echo "✓ data directory exists"
test -d logs && echo "✓ logs directory exists"
```

### Step 5: Verify Database Functionality

```bash
# Check database exists and has tables
sqlite3 data/wallet.db ".tables"

# Expected output should show: wallet_configs equity_snapshots position_snapshots closed_trades strategies strategy_assignments
```

### Step 6: Test Logging

The application creates logs automatically. Verify:

```bash
# Check if log directory has files
ls -la logs/

# Check for exchange traffic log
tail logs/exchange_traffic.log
```

---

## Production Deployment

### Option 1: Running with systemd (Recommended)

**Create systemd service file:**

```bash
sudo nano /etc/systemd/system/wallet-app.service
```

**Paste the following configuration:**

```ini
[Unit]
Description=Apex Wallet Monitoring Application
After=network.target

[Service]
Type=simple
User=your_user
Group=your_user
WorkingDirectory=/opt/wallet-app
Environment="PATH=/opt/wallet-app/venv/bin"
ExecStart=/opt/wallet-app/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Enable and start the service:**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable wallet-app

# Start the service
sudo systemctl start wallet-app

# Verify it's running
sudo systemctl status wallet-app

# View logs
sudo journalctl -u wallet-app -f  # Follow logs in real-time
```

### Option 2: Running with tmux

```bash
# Start new tmux session
tmux new-session -d -s wallet-app

# Send commands to session
tmux send-keys -t wallet-app "cd /opt/wallet-app && source venv/bin/activate && python app.py" Enter

# Attach to session (to see output)
tmux attach -t wallet-app

# Detach from session (Ctrl+B then D)
```

### Option 3: Running with screen

```bash
# Start new screen session
screen -S wallet-app

# Inside screen, run:
cd /opt/wallet-app
source venv/bin/activate
python app.py

# Detach (Ctrl+A then D)
# Reattach: screen -r wallet-app
```

### Option 4: Using Gunicorn (Production WSGI Server)

```bash
# Gunicorn is included in requirements.txt
# Start with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 --access-logfile logs/access.log --error-logfile logs/error.log app:app
```

### Option 5: Using Nginx Reverse Proxy

**Install Nginx:**
```bash
sudo apt install nginx
```

**Create Nginx configuration:**
```bash
sudo nano /etc/nginx/sites-available/wallet-app
```

**Paste configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
    }
}
```

**Enable the configuration:**
```bash
sudo ln -s /etc/nginx/sites-available/wallet-app /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

---

## Backup Strategy

### Initial Backup

```bash
# Create initial backup
cp data/wallet.db data/wallet_backup_$(date +%Y%m%d_%H%M%S).db

# Verify backup
ls -lh data/wallet_backup_*.db
```

### Automated Daily Backups

**Create backup script:**

```bash
sudo nano /usr/local/bin/backup-wallet-db.sh
```

**Paste the following:**

```bash
#!/bin/bash

BACKUP_DIR="/opt/wallet-app/data"
BACKUP_FILE="$BACKUP_DIR/wallet_backup_$(date +%Y%m%d_%H%M%S).db"

# Create backup
cp "$BACKUP_DIR/wallet.db" "$BACKUP_FILE"

# Keep only last 7 backups
ls -t "$BACKUP_DIR"/wallet_backup_*.db | tail -n +8 | xargs -r rm

# Verify backup
if [ -f "$BACKUP_FILE" ]; then
    echo "Backup created: $BACKUP_FILE"
    sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" > /dev/null && echo "Backup verified OK"
else
    echo "Backup failed" >&2
    exit 1
fi
```

**Make executable:**
```bash
sudo chmod +x /usr/local/bin/backup-wallet-db.sh
```

**Add to crontab:**
```bash
sudo crontab -e

# Add this line (backup daily at 2 AM)
0 2 * * * /usr/local/bin/backup-wallet-db.sh
```

---

## Monitoring

### Health Checks

```bash
# Check if process is running
ps aux | grep app.py

# Check health endpoint
curl http://localhost:5000/health

# Check database connectivity
curl http://localhost:5000/admin
```

### Log Monitoring

```bash
# View application logs (if using systemd)
sudo journalctl -u wallet-app -f

# View exchange traffic logs
tail -f /opt/wallet-app/logs/exchange_traffic.log

# View all logs
tail -f /opt/wallet-app/logs/*.log
```

### Disk Usage

```bash
# Check database size
ls -lh /opt/wallet-app/data/wallet.db

# Check total disk usage
du -sh /opt/wallet-app/

# Check available disk space
df -h /opt/wallet-app/
```

---

## Updating the Application

### Step 1: Backup Database

```bash
cp /opt/wallet-app/data/wallet.db /opt/wallet-app/data/wallet_backup_$(date +%Y%m%d_%H%M%S).db
```

### Step 2: Stop Application

```bash
# If using systemd
sudo systemctl stop wallet-app

# If using tmux/screen, attach and press Ctrl+C
```

### Step 3: Pull Latest Code

```bash
cd /opt/wallet-app
source venv/bin/activate
git pull origin master  # Or your main branch
```

### Step 4: Update Dependencies

```bash
pip install -r requirements.txt --upgrade
```

### Step 5: Start Application

```bash
# If using systemd
sudo systemctl start wallet-app

# If using tmux
tmux send-keys -t wallet-app "python app.py" Enter

# If using screen
screen -S wallet-app -c /dev/null -d -m bash -c "cd /opt/wallet-app && source venv/bin/activate && python app.py"
```

### Step 6: Verify

```bash
# Check if running
ps aux | grep app.py

# Test health endpoint
curl http://localhost:5000/health
```

---

## Troubleshooting

### Port 5000 Already in Use

```bash
# Find process using port
lsof -i :5000

# Kill the process
kill -9 <PID>

# Or use different port (modify app.py or .env)
```

### Python Module Not Found

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Or install specific package
pip install Flask==3.1.0
```

### Database Lock Errors

```bash
# Close any open connections
ps aux | grep sqlite

# Restart application
sudo systemctl restart wallet-app
```

### Encryption Key Issues

If credentials won't decrypt:

1. Go to `/admin`
2. Edit affected wallets
3. Re-enter API credentials
4. Save (they will be re-encrypted with current key)

### Cannot Connect to Wallet

```bash
# Check if application is running
ps aux | grep app.py

# Check health endpoint
curl http://localhost:5000/health

# Check logs for errors
tail -f logs/exchange_traffic.log

# Verify network connectivity
ping api-docs.pro.apex.exchange
```

### Database Corruption

```bash
# Check database integrity
sqlite3 data/wallet.db "PRAGMA integrity_check;"

# Restore from backup if corrupted
cp data/wallet_backup_YYYYMMDD_HHMMSS.db data/wallet.db
```

### Permission Denied

```bash
# Fix file permissions
chmod 755 /opt/wallet-app
chmod 644 /opt/wallet-app/data/wallet.db
chmod 755 /opt/wallet-app/logs

# Fix ownership if needed
sudo chown -R your_user:your_user /opt/wallet-app
```

### Application Won't Start

1. **Check Python version:**
   ```bash
   python3 --version
   ```

2. **Check virtual environment:**
   ```bash
   source venv/bin/activate
   which python
   ```

3. **Check dependencies:**
   ```bash
   pip list | grep Flask
   ```

4. **Test with verbose output:**
   ```bash
   python -u app.py 2>&1 | tee debug.log
   ```

5. **Check for syntax errors:**
   ```bash
   python -m py_compile app.py
   ```

---

## Verification Checklist

After installation, verify everything is working:

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip list` shows Flask, SQLAlchemy, etc.)
- [ ] `.env` file created with `FLASK_SECRET_KEY` set
- [ ] Application starts without errors (`python app.py`)
- [ ] Health endpoint returns 200 (`curl http://localhost:5000/health`)
- [ ] Database created (`ls -la data/wallet.db`)
- [ ] Logs directory created (`ls -la logs/`)
- [ ] Can access web interface (http://<server-ip>:5000)
- [ ] Can access admin panel (http://<server-ip>:5000/admin)
- [ ] Database backup created
- [ ] Service configured for production (systemd/tmux/screen)
- [ ] Monitoring and logs working
- [ ] Backup strategy in place

---

## Next Steps

1. **Add Wallets**: Navigate to `/admin` and add your wallet credentials
2. **Configure Strategies**: Go to `/admin/strategies` and create trading strategies
3. **Monitor Data**: View equity history and position snapshots on dashboard
4. **Set Up Alerts**: Configure monitoring for key metrics (see `docs/GUIDE.md`)

---

## Support & Documentation

- **Project README**: [README.md](../README.md)
- **Complete Guide**: [docs/GUIDE.md](./GUIDE.md)
- **Development Rules**: [CLAUDE.md](../CLAUDE.md)
- **Project Rules**: [docs/rules.md](./rules.md)

---

## Quick Reference

```bash
# Activate virtual environment
source venv/bin/activate

# Start application
python app.py

# Check health
curl http://localhost:5000/health

# Backup database
cp data/wallet.db data/wallet_backup_$(date +%Y%m%d_%H%M%S).db

# View logs
tail -f logs/exchange_traffic.log

# Stop application (if in foreground)
Ctrl+C

# Start with systemd
sudo systemctl start wallet-app
sudo systemctl status wallet-app
sudo systemctl stop wallet-app

# View systemd logs
sudo journalctl -u wallet-app -f
```

---

**Remember**: Always backup your database before making changes to the installation or configuration.
