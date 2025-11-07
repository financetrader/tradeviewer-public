# Wallet Monitor - Complete Guide

Complete guide for setting up, running, and securing the wallet monitoring application.

---

## Quick Start

**Prerequisites:**
- Docker Engine 20.10+ installed
- Docker Compose installed (or docker-compose standalone)

**Setup Steps:**

1. **Create .env File**
   ```bash
   cp env.example .env
   # Edit .env and set FLASK_SECRET_KEY
   # Generate a key with: python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Start Application**
   ```bash
   docker-compose up -d
   ```

3. **View Logs**
   ```bash
   docker-compose logs -f
   ```

4. **Access Application**
   - **Portfolio Overview:** http://localhost:5000
   - **Wallets:** http://localhost:5000/admin
   - **Strategies:** http://localhost:5000/admin/strategies
   - **Exchange Logs:** http://localhost:5000/admin/exchange-logs

**Note**: Your existing database (`data/wallet.db`) will be preserved via volume mounts.

**To stop the application:**
```bash
docker-compose down
```

### Database

The database is automatically created on first run inside the Docker container. The `data/` directory is mounted as a volume, so your database persists across container restarts.

To start fresh (WARNING: This deletes all data):
```bash
docker-compose down
rm -f data/wallet.db
docker-compose up -d
```

---

## Security Features

### Implemented ✅

- **Request Size Limits** - 16MB maximum payload prevents DoS attacks
- **Input Validation** - Custom sanitization for all inputs (XSS detection, length limits, bounds checking)
- **Rate Limiting** - Admin: 30/hour, Test wallet: 10/minute, All POST routes protected
- **Security Headers** - HSTS, CSP, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy
- **Credential Encryption** - Fernet encryption at rest, automatic encryption/decryption
- **Database Permissions** - File permissions set to 600 (owner read/write only)
- **Error Handling** - Generic messages prevent information disclosure, internal logging
- **Health Check** - `/health` endpoint for monitoring with database connectivity check
- **Configuration Management** - Environment-based configs, debug disabled in production

### Not Implemented ⚠️

- **CSRF Protection** - Disabled (all POST routes use `@csrf.exempt` decorator)
- **Authentication** - All routes are public (no login required)

### Security Details

#### CSRF Protection
- **Status**: Disabled - All POST routes use `@csrf.exempt` decorator
- Flask-WTF is installed but CSRF protection is not active
- Forms may include CSRF tokens in templates, but they are not validated

#### Input Validation Functions
- `sanitize_string()` - Basic string validation
- `validate_wallet_name()` - Wallet name format
- `validate_symbol()` - Trading symbol format
- `validate_wallet_address()` - Ethereum address format
- `sanitize_integer()` - Safe integer conversion with bounds
- `sanitize_float()` - Safe float conversion with bounds
- `sanitize_text()` - Text field sanitization

**Usage:**
```python
from utils.validation import sanitize_integer, validate_wallet_name

wallet_id = sanitize_integer(request.form.get('wallet_id'), default=0, min_val=1)
name = validate_wallet_name(request.form.get('name'))
```

#### Credential Encryption
- Automatic encryption on save, decryption on access
- Files: `utils/encryption.py`, `db/models.py`

**Usage:**
```python
wallet = WalletConfig(api_key="secret-key")  # Encrypted on save
print(wallet.api_key)  # "secret-key" (decrypted automatically)
```

---

## Configuration

### Environment Variables

**Development:**
```
FLASK_ENV=development
FLASK_SECRET_KEY=<random-key>
ENCRYPTION_KEY_SEED=dev-seed-change-in-production
ADMIN_LOG_TAIL=200
```

**Production:**
```
FLASK_ENV=production
FLASK_SECRET_KEY=<strong-random-key>
ENCRYPTION_KEY=<fernet-key>
```

### Generating Keys

**Flask Secret Key:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Encryption Key (Production):**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Security Hardening

- Keep `.env` file secure and never commit to git
- Restrict database file permissions: `chmod 600 data/wallet.db`
- Use strong encryption keys for production use
- Debug mode automatically disabled in production

---

## Common Tasks

### Add a New Wallet
1. Go to http://localhost:5000/admin
2. Click "Add Wallet"
3. Select provider (Apex Omni, Hyperliquid, Property)
4. Enter credentials
5. Click "Add Wallet"
6. Click "Test" to verify connection

### Create a Strategy
1. Go to http://localhost:5000/admin/strategies
2. Click "Add Strategy"
3. Enter name and description
4. Click "Create"

### Assign Strategy to Wallet
1. In strategies page, find "Assignments" section
2. Select wallet, symbol, and strategy
3. Click "Assign"

### View Wallet Data
1. Go to http://localhost:5000 (portfolio overview)
2. Click on a wallet to view details
3. View positions, trades, and P&L data

---

## Monitoring & Maintenance

### Application Logs

View application logs using Docker:
```bash
docker-compose logs -f
```

View exchange traffic logs:
```bash
tail -f logs/exchange_traffic.log
```

### Database Backups

```bash
# Create local backup
cp data/wallet.db data/wallet_backup_$(date +%Y%m%d_%H%M%S).db

# Or backup to external location
cp data/wallet.db ~/backups/wallet_backup_$(date +%Y%m%d_%H%M%S).db
```

### Monitoring

- Check application logs: `docker-compose logs -f`
- Monitor database size: `ls -lh data/wallet.db`
- Check container status: `docker-compose ps`
- Use `/health` endpoint for health checks: `curl http://localhost:5000/health`

### Updates

```bash
# Pull latest code (if using git)
git pull

# Rebuild and restart container
docker-compose up -d --build

# Verify it's running
docker-compose ps
curl http://localhost:5000/health
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 5000
lsof -i :5000
# Kill it
kill -9 <PID>
```

### ImportError or ModuleNotFoundError
```bash
# Rebuild the Docker image to reinstall dependencies
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database Errors
```bash
# Remove and recreate database (WARNING: deletes all data)
docker-compose down
rm -f data/wallet.db
docker-compose up -d
```

### Can't Decrypt Wallet Credentials
This happens when the encryption key changes. Solution:
1. Go to wallets page
2. Edit the wallet
3. Re-enter the API credentials
4. Save

The credentials will be encrypted with the current key.

### Encryption Key Issues
If decryption fails:
```bash
# Regenerate key (WARNING: Existing encrypted credentials will become inaccessible!)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Permission Denied Errors
```bash
# Fix file permissions
chmod 600 ./data/wallet.db
```

### CSRF Token Errors
- Flask-WTF is included in the Docker image
- Check that forms include CSRF token: `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>`
- If issues persist, rebuild the container: `docker-compose up -d --build`

### Validation Errors
- Check `utils/validation.py` for validation rules
- Ensure inputs match expected formats

### Rate Limiting Issues
- Check rate limits in `utils/rate_limit.py`
- Adjust limits if needed for your use case

---

## Testing Security Features

### Test CSRF Protection
1. Submit a form without CSRF token → Should get 400 error
2. Submit with valid token → Should work

### Test Rate Limiting
```bash
# Rapid requests
for i in {1..35}; do curl -X POST http://localhost:5000/admin/add_wallet; done
# Should be rate limited after limit
```

### Test Input Validation
- Submit invalid wallet name → Should be rejected
- Submit invalid wallet address → Should be rejected
- Submit negative numbers → Should be sanitized to default

### Test Security Headers
```bash
curl -I http://localhost:5000/
# Should see security headers in response
```

---

## Security Checklist

Before production deployment:

- [x] CSRF protection enabled
- [x] Request size limits configured
- [x] Input validation implemented
- [x] Rate limiting active
- [x] Security headers enabled
- [x] Credentials encrypted
- [x] Database permissions set
- [x] Error handling implemented
- [x] Debug mode disabled in production
- [x] Health check endpoint available
- [ ] Authentication implemented (optional)
- [ ] HTTPS/TLS configured (if deploying publicly)
- [ ] Monitoring and logging setup

---

## Reference

### Key Endpoints

- `/` - Portfolio overview dashboard
- `/admin` - Wallet management
- `/admin/strategies` - Strategy management
- `/wallet/<id>` - Wallet dashboard
- `/health` - Health check endpoint
- `/admin/exchange-logs` - Exchange traffic logs

### Dependencies

**Security Packages:**
- `Flask-WTF>=1.2.0` - CSRF protection
- `Flask-Limiter==3.5.0` - Rate limiting
- `cryptography==41.0.7` - Credential encryption

**All in:** `requirements.txt`

### File Structure

```
├── app.py                    # Main Flask application
├── config.py                 # Configuration
├── requirements.txt           # Dependencies
├── .env                      # Environment variables (not committed)
├── db/                       # Database models and queries
├── services/                 # Business logic
├── utils/                    # Utilities (encryption, validation, etc.)
├── templates/                # HTML templates
└── data/                     # SQLite database
```

### Environment Variables Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `FLASK_ENV` | development | Set to 'production' for production |
| `FLASK_SECRET_KEY` | dev-key-... | Session encryption key |
| `ENCRYPTION_KEY_SEED` | dev-seed-123 | Credential encryption seed |
| `ENCRYPTION_KEY` | (none) | Fernet key for production |
| `DATABASE_URL` | sqlite:///data/wallet.db | Database connection |
| `ADMIN_LOG_TAIL` | 200 | Number of log lines to show |

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] Generate strong `FLASK_SECRET_KEY`
- [ ] Generate encryption key for credentials
- [ ] Update environment variables
- [ ] Set up database backups
- [ ] Configure logging and monitoring
- [ ] Review security headers
- [ ] Set `FLASK_ENV=production`
- [ ] Test rate limiting
- [ ] Verify security headers with browser

### Production WSGI Server (Optional)

For production environments, you can use Gunicorn instead of Flask dev server:
```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 60 app:app
```

---

## Docker Deployment

The application is fully containerized and ready for Docker deployment. Docker provides a consistent environment across development, staging, and production.

### Prerequisites

- Docker Engine 20.10+ installed
- Docker Compose 2.0+ installed

### Quick Start with Docker

1. **Create .env File**
   ```bash
   cp env.example .env
   # Edit .env and set required variables:
   # - FLASK_SECRET_KEY (required for production)
   # - ENCRYPTION_KEY (optional, for credential encryption)
   ```

2. **Start the Application**
   ```bash
   docker-compose up -d
   ```

3. **Verify It's Running**
   ```bash
   docker-compose ps
   curl http://localhost:5000/health
   ```

### Docker Configuration

The `docker-compose.yml` file configures:
- **Port**: 5000 (configurable via `PORT` environment variable)
- **Volumes**: 
  - `./data:/app/data` - Database directory (preserves `wallet.db`)
  - `./logs:/app/logs` - Log files directory
- **Environment**: Loads from `.env` file
- **Health Check**: Uses `/health` endpoint
- **Restart Policy**: `unless-stopped` (auto-restart on failure)

### Docker Commands

```bash
# Build the image
docker-compose build

# Start in foreground (for debugging)
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f wallet-app

# Stop the application
docker-compose down

# Stop and remove volumes (WARNING: deletes database!)
docker-compose down -v

# Rebuild and restart
docker-compose up -d --build

# Execute commands in container
docker-compose exec wallet-app bash

# Check container status
docker-compose ps

# View resource usage
docker stats wallet-app
```

### Database Persistence

**Important**: Your existing database (`data/wallet.db`) is preserved via volume mounts. The `./data` directory is mounted into the container, ensuring:

- Database persists across container restarts
- Database persists when updating the container image
- You can backup the database by copying `data/wallet.db` from the host

### Log Persistence

Application logs are written to `./logs` directory, which is mounted as a volume:

- `logs/exchange_traffic.log` - Exchange API traffic logs
- `logs/gunicorn-access.log` - Gunicorn access logs (if configured)
- `logs/gunicorn-error.log` - Gunicorn error logs (if configured)

Logs persist across container restarts and can be viewed from the host system.

### Environment Variables

Docker-specific environment variables (set automatically in `docker-compose.yml`):

- `DOCKER_ENV=true` - Indicates running in Docker (skips chmod operations)
- `EXCHANGE_LOG_PATH=/app/logs/exchange_traffic.log` - Log file path in container
- `FLASK_ENV=production` - Production mode (debug disabled)

Additional variables can be set in `.env` file and will be loaded automatically.

### Updating the Application

To update the application with new code:

```bash
# Pull latest code (if using git)
git pull

# Rebuild and restart
docker-compose up -d --build

# Verify it's running
docker-compose ps
curl http://localhost:5000/health
```

Your database and logs will be preserved during updates.

### Docker Troubleshooting

**Container won't start:**
```bash
# Check logs
docker-compose logs wallet-app

# Check if port is already in use
lsof -i :5000

# Verify .env file exists and has required variables
cat .env
```

**Database permission errors:**
- The application skips `chmod` operations in Docker (handled by volume mounts)
- Ensure `data/` directory is writable: `chmod 755 data/`

**Can't access the application:**
```bash
# Check if container is running
docker-compose ps

# Check health endpoint
curl http://localhost:5000/health

# Check container logs
docker-compose logs -f wallet-app
```

**Background logger not running:**
- The background logger runs inside the container automatically
- Check logs: `docker-compose logs wallet-app | grep logger`
- The logger runs every 30 minutes and logs to the database

**Volume mount issues:**
```bash
# Verify volumes are mounted correctly
docker-compose exec wallet-app ls -la /app/data
docker-compose exec wallet-app ls -la /app/logs

# Check file permissions
docker-compose exec wallet-app ls -l /app/data/wallet.db
```

### Production Deployment with Docker

For production deployment:

1. **Set Production Environment Variables**
   ```bash
   # In .env file
   FLASK_ENV=production
   FLASK_SECRET_KEY=<strong-random-key>
   ENCRYPTION_KEY=<fernet-key>
   ```

2. **Use Reverse Proxy (Nginx)**
   - Configure Nginx to proxy to `localhost:5000`
   - Set up SSL/TLS certificates
   - See "Production Deployment" section above

3. **Set Up Monitoring**
   - Monitor container health: `docker-compose ps`
   - Monitor logs: `docker-compose logs -f`
   - Set up log rotation for Docker logs
   - Monitor disk space for database and logs

4. **Backup Strategy**
   ```bash
   # Backup database
   cp data/wallet.db backups/wallet_backup_$(date +%Y%m%d_%H%M%S).db
   
   # Backup can be automated with cron
   # Add to crontab: 0 2 * * * /path/to/backup-script.sh
   ```

---

## Support

For issues or questions:
1. Check Docker logs: `docker-compose logs -f`
2. Review this guide
3. Check `README.md` for project overview
4. Verify all environment variables are set in `.env` file
5. Check container status: `docker-compose ps`
6. Verify health endpoint: `curl http://localhost:5000/health`

See `README.md` for project overview, features, and detailed information.

