# Essential Rules for Flask/Python Work with Claude Code

**How to Use This File with Claude Code:**
- Reference this file at the start of conversations: `@CLAUDE.md` or mention "follow the rules in CLAUDE.md"
- Claude Code will automatically read and follow these rules when you reference it
- Keep this file updated as you discover new gotchas

---

## 1. NEVER Delete the Database
**CRITICAL**: The database (`data/wallet.db`) contains all historical trading data, wallet configurations, and credentials. Deleting it is catastrophic.

**Rules:**
- **Never run**: `rm data/wallet.db` or `rm -f data/wallet.db`
- **Never delete**: Database files, even if "recreating" seems easier
- **If database is corrupted**: Restore from backup first, then investigate
- **If you need a fresh start**: Create a new database file with a different name, don't delete the existing one

**Exception**: Only delete if explicitly requested by project owner AND a verified backup exists.

## 2. Always Backup Database Before Modifications
**CRITICAL**: Before ANY database modification, create a backup and store it on the server.

**Backup Process:**
```bash
# 1. Create timestamped backup in data/ directory
cp data/wallet.db data/wallet_backup_$(date +%Y%m%d_%H%M%S).db

# 2. Verify backup was created
ls -lh data/wallet_backup_*.db

# 3. Store backup on server (keep at least 2 recent backups)
# Backups are stored in data/ directory on server
# Format: wallet_backup_YYYYMMDD_HHMMSS.db
```

**When to Backup:**
- **Before migrations**: Any schema changes
- **Before bulk operations**: Large data imports/exports
- **Before manual SQL**: Direct database queries that modify data
- **Before code changes**: That might affect database writes
- **Before encryption key changes**: Credentials will need re-encryption
- **Weekly**: Automated backups (set up cron job)

**Backup Storage:**
- Store backups in `data/` directory on server
- Keep at least 2 most recent backups
- Older backups can be archived to `~/backups/` or external storage
- Never commit backups to git (already in `.gitignore`)

**Verification:**
```bash
# Check backup integrity
sqlite3 data/wallet_backup_YYYYMMDD_HHMMSS.db "PRAGMA integrity_check;"

# Compare sizes (should be similar)
ls -lh data/wallet.db data/wallet_backup_*.db
```

## 3. Always Create a Branch for Every Change
**CRITICAL**: ALWAYS create a branch before making ANY changes. Branch off the CURRENT branch (not necessarily main).

**Git Workflow (CRITICAL ORDER: Code → Test → Document → Merge):**
```bash
# 1. Check current branch and status
git status
git branch  # Note which branch you're currently on

# 2. Create feature branch from CURRENT branch
# Branch off whatever branch you're currently on
git checkout -b feature/add-wallet-validation
# OR
git checkout -b fix/position-calculation-bug
# OR
git checkout -b upgrade/flask-3.2.0
# OR
git checkout -b docs/update-readme

# 3. STEP 1: Make code changes
# ... write code ...

# 4. STEP 2: TEST FIRST - Verify everything works completely
python app.py
curl http://localhost:5000/health
# Test actual functionality:
# - Test routes/endpoints
# - Verify database writes
# - Check logs for errors
# - Test edge cases
# DO NOT proceed to documentation until testing is confirmed

# 5. Commit code changes (after testing passes)
git add .
git commit -m "Add feature: description of changes"

# 6. STEP 3: DOCUMENT AFTER TESTING CONFIRMED
# Only add documentation after testing is verified
# Add docstrings to new functions/classes
# Update docs/GUIDE.md for API/config changes
# Update README.md for user-facing features
# Create session notes if major changes
git add .
git commit -m "docs: Add documentation for feature"

# 7. STEP 4: Merge ONLY after documentation complete
# If you branched off main:
git checkout main
git merge feature/add-wallet-validation

# If you branched off another feature branch:
git checkout <parent-branch-name>
git merge feature/add-wallet-validation
```

**Branch Naming Conventions:**
- `feature/` - New features
- `fix/` - Bug fixes
- `upgrade/` - Dependency or framework upgrades
- `refactor/` - Code refactoring
- `docs/` - Documentation updates

**Rules:**
- **ALWAYS branch** before making ANY changes (features, fixes, upgrades, refactors, docs)
- **Branch off current branch**: Don't assume you need to go back to main
- **Workflow order is CRITICAL**: Code → Test → Document → Merge
- **Test FIRST**: Verify all changes work completely before documenting
- **Document AFTER testing**: Only add documentation after testing is confirmed
- **Merge LAST**: Only merge after documentation is complete
- **Never commit directly** to any branch without creating a new branch first
- **Document changes** in commit messages

**Exception**: Only commit directly to a branch for trivial changes (typos, formatting) with explicit approval from project owner.

**Why This Order?**
- Testing first ensures code actually works before documenting
- Documentation reflects working code, not broken assumptions
- Prevents merging broken or undocumented code
- Cleaner git history with separate commits for code and docs

**Why Branch Off Current Branch?**
- If you're already on a feature branch, branch off that
- Keeps work organized and allows nested feature branches
- Easier to track related changes
- Can merge back to parent when ready

## 4. Test First, Document After, Then Merge
**CRITICAL**: Follow this exact order: Code → Test → Document → Merge

**Workflow Order:**
1. **Code**: Make changes on branch
2. **Test**: Verify changes work completely (see Testing section below)
3. **Document**: Only AFTER testing is confirmed, add documentation
4. **Merge**: Only merge after documentation is complete

**Why This Order?**
- Testing first ensures code actually works before documenting
- Documentation reflects working code, not broken assumptions
- Prevents merging broken or undocumented code
- Cleaner git history with separate commits for code and docs

**Documentation (AFTER testing confirmed):**

**Documentation Locations:**
- **Code changes**: Add docstrings to new functions/classes
- **API changes**: Update `docs/GUIDE.md` with new endpoints
- **Database changes**: Document schema changes in migration files
- **Gotchas**: Add to this `CLAUDE.md` file immediately
- **Session notes**: Create `docs/session-notes/YYYY-MM-DD-description.md` for major changes

**What to Document:**

**1. Code Documentation:**
```python
def calculate_leverage(position_size_usd, margin_used):
    """
    Calculate position leverage from margin delta.
    
    Args:
        position_size_usd: Position size in USD
        margin_used: Total margin used for position
        
    Returns:
        float: Leverage multiplier (e.g., 5.0 for 5x leverage)
        
    Note:
        This method works best for new positions. For existing positions
        opened before tracking started, returns None.
    """
```

**2. Database Schema Changes:**
```python
# In migration file: db/migrations/add_leverage_column.py
"""
Migration: Add leverage column to closed_trades

Date: 2024-01-15
Author: [Your name]

Changes:
- Add 'leverage' column to closed_trades table
- Default value: NULL
- Type: REAL

Rollback:
ALTER TABLE closed_trades DROP COLUMN leverage;

Dependencies:
- None

Testing:
1. Backup database
2. Run migration
3. Verify column exists: sqlite3 data/wallet.db "PRAGMA table_info(closed_trades);"
"""
```

**3. Session Notes Template:**
Create `docs/session-notes/YYYY-MM-DD-feature-name.md`:
```markdown
# Session Notes - [Date] - [Feature Name]

## What Changed
- Added X feature
- Fixed Y bug
- Upgraded Z dependency

## What Broke
- Issue 1: Description and error
- Issue 2: Description and error

## How It Was Fixed
- Fix 1: Solution and code reference
- Fix 2: Solution and code reference

## Testing Performed
- Tested X scenario: Result
- Tested Y scenario: Result

## Rollback Steps
1. Revert commit: `git revert <hash>`
2. Restore database: `cp data/wallet_backup_YYYYMMDD.db data/wallet.db`
3. Restart app: `python app.py`

## Notes for Future
- Gotcha discovered: [description]
- TODO: [item]
```

**4. Update Main Documentation:**
- **New features**: Add to `README.md` Features section
- **API changes**: Update `docs/GUIDE.md` endpoints section
- **Configuration**: Update `env.example` and `docs/GUIDE.md` config section
- **Troubleshooting**: Add common issues to `docs/GUIDE.md`

**Documentation Checklist:**
- [ ] Code has docstrings
- [ ] Migration files have rollback instructions
- [ ] README.md updated if user-facing changes
- [ ] GUIDE.md updated if API/config changes
- [ ] Session notes created for major changes
- [ ] CLAUDE.md updated with new gotchas

## 5. Never Let AI Modify Database Migrations Directly
**Critical**: Always review and test database migrations manually. One corrupted migration can break production data.

- **Create migration files** with Claude Code, but **review SQL before running**
- **Test migrations** on a backup database first: `cp data/wallet.db data/wallet_backup_test.db`
- **Check for missing columns** before querying: Use try/except around queries that reference new columns
- **Document migration order** in migration files (dependencies, rollback steps)

**Example pattern already in codebase:**
```python
try:
    # Query with new column
    trades = session.query(ClosedTrade).filter(...).all()
except OperationalError as e:
    if 'no such column' in str(e).lower():
        # Fallback to old query without new column
        print("Warning: Column not found. Run migration first.")
```

## 6. Never Include Personal Setup in Shared Documentation
**CRITICAL**: Session notes and documentation in this repo should NOT contain personal/server-specific information.

**Rules:**
- **NEVER commit server IPs** to git in regular documentation (README.md, GUIDE.md, session notes, etc.)
- **EXCEPTION**: CLAUDE.md is allowed to contain the actual server IP (`91.99.142.197:5000`) because it's specifically for Claude AI testing instructions
- **Session notes go in `docs/session-notes/`** and are gitignored (local only)
- **Generic placeholders** in examples: `http://localhost:5000`, `<server-ip>:5000`, `your-domain.com`
- **Never include**: Personal credentials, API keys, server passwords, specific user data
- **Safe for git**: Development setup docs, architecture guides, deployment guides, examples with placeholders

**Session Notes Guidelines:**
- Session notes are for local development tracking only
- Include in `.gitignore` (already done: `docs/session-notes/`)
- Use for: implementation details, testing notes, troubleshooting steps, rollback procedures
- Keep personal test URLs and IPs OUT of session notes
- Or if using specific URLs for testing, use `localhost` or `<server-ip>` placeholders

**Checked Locations:**
- ✅ `README.md` - No personal setup (uses examples)
- ✅ `docs/GUIDE.md` - No personal setup (uses localhost)
- ✅ `docs/FRESH_SERVER_INSTALLATION.md` - No personal setup (uses placeholders)
- ✅ `CLAUDE.md` - Contains server IP (intentional, for Claude AI testing)
- ⚠️ `docs/session-notes/` - Added to .gitignore (not pushed to GitHub)

## 7. Document Platform Gotchas Immediately
Hit a Flask/SQLAlchemy/SQLite issue? Add it to this file that session.

**Known Gotchas:**
- **SQLAlchemy scoped sessions**: Always use `with get_session() as session:` pattern. Never reuse sessions across requests.
- **SQLite locking**: Multiple threads writing can cause "database is locked" errors. Use connection pooling carefully.
- **Flask reloader**: Background threads start twice in debug mode. Use `WERKZEUG_RUN_MAIN` check (already implemented).
- **CSRF tokens**: Must be included in all POST forms. Use `{{ csrf_token() }}` in templates.
- **Symbol normalization**: Always normalize symbols before DB operations (`normalize_symbol()`). Different exchanges use different formats (BTC vs BTC-USDT).
- **Position opened date**: Don't use first-ever position snapshot. Find most recent zero-size → non-zero transition for accurate "time in trade".
- **Portfolio equity aggregation**: DO NOT filter wallets based on staleness (e.g., no update in 1 hour). This causes artificial dips in equity charts. Wallets are the source of truth - aggregate ALL connected wallets' latest snapshots, no matter the age. Show staleness warnings in UI instead (see `db/queries.py:get_equity_history()`).
- **Form array submission in Flask**: Use `request.form.getlist('fieldname')` to get HTML form arrays (when `<input name="symbol">` appears multiple times). Check for getlist() first, then fall back to get() for backwards compatibility with single-value forms. In templates, form fields with `name="symbols"` submit as array, not single string.
- **Table filtering with data attributes**: Use `data-*` attributes on table rows for client-side filtering/sorting. Get filter/sort values from data attributes, not from displayed cell text. This allows filtering by different values than what's displayed (e.g., numeric trade count instead of text). Always use `.toLowerCase()` for case-insensitive string comparisons. See `templates/admin_strategies.html` for example implementation.
- **Leverage calculation**: Calculated using margin delta tracking at position OPEN time (stored in position_snapshots). **CRITICAL**: Leverage is calculated ONCE when position first opens, then preserved for all future snapshots. Check the FIRST snapshot (not latest) - if it has leverage, use it for ALL future snapshots. Only calculate if first snapshot doesn't have it. Both Apex Omni and Hyperliquid use margin delta method for new positions. Old trades (Aug-Nov 7) have no leverage (logger not running then). See `docs/leverage/LEVERAGE_CALCULATION.md` for complete implementation, exchange-specific algorithms, and verification steps.
- **Aggregated trades**: Exchange APIs return individual fills. System groups fills by (wallet_id, timestamp, symbol) into logical trades. Uses `aggregated_trades` table. UI shows aggregated view; raw fills still in `closed_trades`. 148 fills grouped into 29 logical trades.
- **Data Refresh Architecture**: Dashboard routes are read-only from database (no API calls on page load). Refresh happens via AJAX endpoints (`/api/wallet/<id>/refresh`). Background scheduler uses `services/wallet_refresh.py::refresh_wallet_data()`. Always test refresh functionality separately from page load. Refresh errors shown as popup with error log.

## 8. Use Feature Flags for Experimental Code
Toggle new features on/off without rebuilding. Makes rolling back instant when something breaks.

**Pattern:**
```python
# In config.py
EXPERIMENTAL_LEVERAGE_CALC = os.getenv('EXPERIMENTAL_LEVERAGE_CALC', 'false').lower() == 'true'

# In code
if app.config.get('EXPERIMENTAL_LEVERAGE_CALC'):
    # New calculation method
else:
    # Old reliable method
```

**Benefits:**
- Roll back instantly: Change env var, restart app
- A/B test new features
- Gradual rollout to production

## 9. Always Request Debug Logging
Ask Claude Code to add `app.logger.info()` statements for complex flows. Future you will thank past you when debugging async API calls or position calculations.

**Critical areas needing logging:**
- API client calls (request/response)
- Database queries (especially complex joins)
- Position/leverage calculations
- Strategy assignment resolution
- Background logger operations

**Example:**
```python
app.logger.info(f"Calculating leverage for {symbol}: position_size={position_size_usd}, margin_used={margin_used}")
```

## 10. Test After Every Change!!
**CRITICAL**: Verify changes work before claiming success.

**IMPORTANT**: Always test against the actual running server, not localhost. Test URL: **http://91.99.142.197:5000/**

**Checklist:**
1. **Web server running**: `ps aux | grep app.py` or `curl http://91.99.142.197:5000/health`
2. **Database accessible**: Check `/health` endpoint returns 200
3. **Background logger**: Check `logs/exchange_traffic.log` for activity
4. **API endpoints**: Test actual routes at http://91.99.142.197:5000 (add wallet, view dashboard)
5. **Database writes**: Verify snapshots are being written (check DB directly)
6. **No console errors**: Check terminal output for exceptions
7. **Browser inspection**: Use DevTools to inspect rendered HTML/JavaScript

**Never assume changes worked without verification.**

## 11. Keep Conversations Focused on Single Components
Don't ask to "refactor the whole app". Smaller scope = better results.

**Good scopes:**
- "Add validation to wallet creation form"
- "Fix position opened date calculation for reopened positions"
- "Add error handling to Hyperliquid API client"

**Bad scopes:**
- "Refactor all database queries"
- "Improve the entire dashboard"
- "Optimize everything"

## 12. Database Session Management Rules
**CRITICAL**: SQLAlchemy session handling is easy to break.

**Rules:**
- **Always use context manager**: `with get_session() as session:`
- **Never reuse sessions**: Each request gets a new session
- **Commit explicitly**: `session.commit()` after writes
- **Rollback on errors**: `session.rollback()` in exception handlers
- **Close sessions**: `cleanup_session()` is called automatically via `@app.teardown_appcontext`

**Bad pattern:**
```python
session = get_session()  # DON'T DO THIS
# ... use session ...
session.close()  # Manual cleanup is error-prone
```

**Good pattern:**
```python
with get_session() as session:
    # ... use session ...
    session.commit()  # Explicit commit
# Session automatically cleaned up
```

## 13. Background Thread Safety
Background logger runs in a daemon thread. Be careful with shared state.

**Rules:**
- **Database connections**: Each thread needs its own session
- **Flask app context**: Background threads don't have Flask request context
- **Error handling**: Background thread errors won't show in Flask error handlers
- **Logging**: Use Python logging, not Flask's `app.logger` in background threads

**Current implementation (correct):**
```python
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    start_background_logger()  # Only start once, not on reloader
```

## 14. Exchange API Rate Limiting
Exchange APIs have rate limits. Don't hammer them.

**Rules:**
- **Add delays**: Use `time.sleep()` between rapid API calls
- **Cache responses**: Don't fetch same data multiple times per request
- **Error handling**: Handle 429 (rate limit) errors gracefully
- **Logging**: Log all API calls to `logs/exchange_traffic.log` (already implemented)

**Pattern:**
```python
try:
    data = client.fetch_positions()
except RateLimitError:
    app.logger.warning("Rate limited, backing off...")
    time.sleep(5)
    # Retry or return cached data
```

## 15. Symbol Normalization Consistency
Different exchanges use different symbol formats. Always normalize.

**Rules:**
- **Before DB operations**: Always call `normalize_symbol(symbol)`
- **Before comparisons**: Normalize both sides
- **Strategy assignments**: Store normalized symbols in database
- **Display**: Can show original format in UI, but store normalized

**Example:**
```python
# Bad
if symbol == 'BTC-USDT':  # Might not match 'BTCUSDT' or 'BTC_USDT'

# Good
normalized = normalize_symbol(symbol)
if normalized == normalize_symbol('BTC-USDT'):
```

## 16. Encryption Key Management
Changing encryption keys breaks existing credentials.

**Rules:**
- **Never change ENCRYPTION_KEY** without re-encrypting all credentials
- **Backup before key changes**: Users will need to re-enter API keys
- **Document key rotation**: If rotating keys, provide migration script
- **Test decryption**: After key changes, verify credentials still decrypt

**If key changes:**
1. Backup database
2. Notify users to re-enter credentials
3. Or: Write migration script to re-encrypt with new key

## 17. Position Calculation Edge Cases
Position calculations have many edge cases. Handle them explicitly.

**Known edge cases:**
- **Reopened positions**: Position closed then reopened → find most recent zero→non-zero transition
- **Multiple positions opened simultaneously**: Margin delta can't be attributed to single position
- **No historical data**: Can't calculate leverage for positions opened before tracking started
- **Position size changes**: Adding to position increases margin, but position already exists

**Always:**
- Log calculation method used (`margin_delta`, `margin_rate`, `unknown`)
- Provide fallback when calculation fails
- Document assumptions in code comments

## 18. CSRF Protection Gotchas
CSRF tokens are required for all POST requests.

**Rules:**
- **Include in templates**: `{{ csrf_token() }}` in all forms
- **Exempt when needed**: Use `@csrf.exempt` for API endpoints (sparingly)
- **Error handling**: CSRF errors return 400, handle gracefully
- **Testing**: Test forms work with CSRF enabled

**Current implementation:**
- CSRF enabled by default
- Admin routes exempted where needed (`@csrf.exempt`)
- Error handler shows user-friendly message

---

## Quick Reference: Common Commands

**Start app (WORKING method - verified):**
```bash
# Step 1: Kill all existing processes
pkill -9 -f "python.*app.py"
sleep 3

# Step 2: Verify port is free
netstat -tlnp 2>/dev/null | grep :5000 || ss -tlnp 2>/dev/null | grep :5000 || echo "Port 5000 is free"

# Step 3: Start app in background (Flask needs time to initialize)
cd /root/app-tradeviewer
source venv/bin/activate
python app.py 2>&1 &
sleep 15  # Flask needs ~15 seconds to fully start

# Step 4: Verify it's running
curl -s http://localhost:5000/health
# Should return: {"status": "healthy", "timestamp": "..."}

# Step 5: Check process is running
ps aux | grep -E "python.*app.py" | grep -v grep
```

**If app won't start:**
```bash
# Check for import errors first
source venv/bin/activate
python3 -c "import app; print('Import OK')" 2>&1

# Check syntax
python3 -m py_compile app.py

# Start and watch output for errors
python app.py 2>&1 | head -50
```

**Check if running:**
```bash
ps aux | grep app.py
curl http://localhost:5000/health
# Or check logs
tail -20 logs/app_startup.log
```

**View logs:**
```bash
tail -f logs/exchange_traffic.log
```

**Backup database (ALWAYS before changes):**
```bash
cp data/wallet.db data/wallet_backup_$(date +%Y%m%d_%H%M%S).db
ls -lh data/wallet_backup_*.db  # Verify backup
```

**Test database:**
```bash
sqlite3 data/wallet.db "SELECT COUNT(*) FROM equity_snapshots;"
```

**Git workflow (ALWAYS create branch for every change):**
```bash
# ORDER: Code → Test → Document → Merge

# 1. Create branch
git status  # Check current branch
git checkout -b feature/your-feature-name  # Branch off current branch

# 2. Make code changes
# ... write code ...

# 3. TEST FIRST - Verify everything works
python app.py
curl http://localhost:5000/health
# Test actual functionality, verify database writes, check logs

# 4. Commit code (after testing passes)
git add .
git commit -m "Add feature: description"

# 5. DOCUMENT AFTER TESTING CONFIRMED
# Add docstrings, update docs/GUIDE.md, README.md, etc.
git add .
git commit -m "docs: Add documentation for feature"

# 6. Merge ONLY after documentation complete
git checkout <parent-branch-name>
git merge feature/your-feature-name
```

**Verify backup integrity:**
```bash
sqlite3 data/wallet_backup_YYYYMMDD_HHMMSS.db "PRAGMA integrity_check;"
```

---

## Session Checklist

Before ending a coding session (follow this order):

- [ ] Git branch created (ALWAYS required for any change)
- [ ] Database backed up (if any DB changes)
- [ ] Code changes made
- [ ] Changes tested and verified working (TEST FIRST - verify routes, DB writes, logs)
- [ ] Code documented (docstrings, comments) - AFTER testing confirmed
- [ ] Documentation updated (README.md, GUIDE.md if needed) - AFTER testing confirmed
- [ ] Session notes created (for major changes) - AFTER testing confirmed
- [ ] CLAUDE.md updated (if new gotcha discovered) - AFTER testing confirmed
- [ ] No console errors
- [ ] Health endpoint returns 200
- [ ] Branch merged to parent (ONLY after documentation complete)

---

**Remember**: Every session should leave the codebase better than it found it. Document gotchas, add logging, test thoroughly, backup before changes, and ALWAYS create a branch for every change.

