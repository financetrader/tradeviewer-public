# Wallet Monitor - Complete Guide

Complete guide for setting up, running, and securing the wallet monitoring application.

---

## Quick Start

**Prerequisites:**
- Python 3.8 or higher
- pip (Python package manager)

**Setup Steps:**

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create .env File**
   ```bash
   cp env.example .env
   # Edit .env and set FLASK_SECRET_KEY
   # Generate a key with: python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Start Application**
   ```bash
   python app.py
   ```

4. **Access Application**
   - **Portfolio Overview:** http://localhost:5000
   - **Wallets:** http://localhost:5000/admin
   - **Strategies:** http://localhost:5000/admin/strategies
   - **Exchange Logs:** http://localhost:5000/admin/exchange-logs

**To stop the application:**
Press `Ctrl+C` in the terminal

### Database

The database is automatically created on first run. The `data/` directory stores your database locally, so it persists across application restarts.

To start fresh (WARNING: This deletes all data):
```bash
rm -f data/wallet.db
python app.py
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

View application logs:
The application logs are displayed in the terminal when you run `python app.py`. You can also view the log files:

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

- Monitor database size: `ls -lh data/wallet.db`
- Use `/health` endpoint for health checks: `curl http://localhost:5000/health`
- Check process status: `ps aux | grep app.py`

### Updates

```bash
# Pull latest code (if using git)
git pull

# Reinstall dependencies (in case they changed)
pip install -r requirements.txt

# Restart the application (stop old one with Ctrl+C, then start new one)
python app.py

# Verify it's running
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
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Then restart the application
python app.py
```

### Database Errors
```bash
# Remove and recreate database (WARNING: deletes all data)
rm -f data/wallet.db
python app.py
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
- Flask-WTF is included in the dependencies (requirements.txt)
- Check that forms include CSRF token: `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>`
- If issues persist, reinstall dependencies: `pip install -r requirements.txt --force-reinstall`

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

## Production Deployment

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. **Create .env File**
   ```bash
   cp env.example .env
   # Edit .env and set required variables:
   # - FLASK_SECRET_KEY (required for production)
   # - ENCRYPTION_KEY (optional, for credential encryption)
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Application**
   ```bash
   python app.py
   ```

4. **Verify It's Running**
   ```bash
   curl http://localhost:5000/health
   ```

### Database Persistence

**Important**: Your existing database (`data/wallet.db`) is stored locally and persists across application restarts. You can backup the database by copying `data/wallet.db`:

```bash
cp data/wallet.db data/wallet_backup_$(date +%Y%m%d_%H%M%S).db
```

### Log Persistence

Application logs are written to `./logs` directory:

- `logs/exchange_traffic.log` - Exchange API traffic logs

Logs persist across application restarts and can be viewed from the host system.

### Running in Background

To run the application in the background, use tools like `screen`, `tmux`, or set up a systemd service:

**Using screen:**
```bash
screen -S wallet-app
python app.py
# Press Ctrl+A then D to detach
```

**Using tmux:**
```bash
tmux new-session -d -s wallet-app python app.py
```

**Using systemd (create `/etc/systemd/system/wallet-app.service`):**
```ini
[Unit]
Description=Wallet Monitoring Application
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/app-tradeviewer
ExecStart=/usr/bin/python3 app.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable wallet-app
sudo systemctl start wallet-app
```

### Updating the Application

To update the application with new code:

```bash
# Stop the application (Ctrl+C if running in foreground, or systemctl stop wallet-app)

# Pull latest code (if using git)
git pull

# Reinstall dependencies if they changed
pip install -r requirements.txt

# Start the application again
python app.py
```

Your database and logs will be preserved during updates.

### Troubleshooting

**Port 5000 already in use:**
```bash
# Check if port is already in use
lsof -i :5000

# Kill the process
kill -9 <PID>
```

**Can't access the application:**
```bash
# Check health endpoint
curl http://localhost:5000/health

# Check if process is running
ps aux | grep app.py
```

**Background logger not running:**
- The background logger runs automatically when the application starts
- Check the logs in `logs/exchange_traffic.log`
- The logger runs every 30 minutes and logs to the database

---

## Monitoring & Backup

### Monitoring

```bash
# Check if process is running
ps aux | grep app.py

# Monitor disk space for database and logs
df -h
ls -lh data/wallet.db

# Check health endpoint
curl http://localhost:5000/health
```

### Backup Strategy

```bash
# Backup database
cp data/wallet.db backups/wallet_backup_$(date +%Y%m%d_%H%M%S).db

# Backup can be automated with cron
# Add to crontab: 0 2 * * * /path/to/backup-script.sh
```

---

## Support

For issues or questions:
1. Check console output when running `python app.py`
2. Review this guide
3. Check `README.md` for project overview
4. Verify all environment variables are set in `.env` file
5. Check if process is running: `ps aux | grep app.py`
6. Verify health endpoint: `curl http://localhost:5000/health`

See `README.md` for project overview, features, and detailed information.

