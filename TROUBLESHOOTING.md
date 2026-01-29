# Troubleshooting Guide

This guide covers common issues when setting up and running Clawd Domain Marketplace.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Backend Issues](#backend-issues)
- [Payment Issues](#payment-issues)
- [DNS Management Issues](#dns-management-issues)
- [MCP Server Issues](#mcp-server-issues)
- [Porkbun API Issues](#porkbun-api-issues)

---

## Installation Issues

### Python version mismatch

**Error:**
```
ERROR: This package requires Python 3.11 or higher
```

**Solution:**
```bash
# Check your Python version
python3 --version

# Install Python 3.11+ via Homebrew (macOS)
brew install python@3.11

# Use specific version
python3.11 -m venv venv
```

### pip install fails with compilation errors

**Error:**
```
error: command 'gcc' failed with exit status 1
```

**Solution:**
```bash
# macOS - install Xcode command line tools
xcode-select --install

# Linux - install build essentials
sudo apt-get install build-essential python3-dev
```

### Node.js version too old

**Error:**
```
SyntaxError: Unexpected token '?'
```

**Solution:**
```bash
# Check Node version (need 18+)
node --version

# Install via nvm
nvm install 18
nvm use 18
```

### npm install fails in mcp-server

**Error:**
```
npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
```

**Solution:**
```bash
# Clear npm cache and retry
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

---

## Backend Issues

### "Address already in use" error

**Error:**
```
OSError: [Errno 48] Address already in use
```

**Solution:**
```bash
# Find process using port 8402
lsof -i :8402

# Kill it
kill -9 <PID>

# Or use a different port
uvicorn src.main:app --port 8403
```

### "ModuleNotFoundError: No module named 'src'"

**Error:**
```
ModuleNotFoundError: No module named 'src'
```

**Solution:**
```bash
# Make sure you're in the backend directory
cd backend

# Activate virtual environment
source venv/bin/activate

# Run from the correct location
uvicorn src.main:app --reload
```

### Database locked error

**Error:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
```bash
# Stop all backend processes
pkill -f uvicorn

# Remove lock file if exists
rm -f clawd_domains.db-journal

# Restart
uvicorn src.main:app --reload
```

### "SKIP_PAYMENT_VERIFICATION cannot be enabled in production"

**Error:**
```
RuntimeError: SKIP_PAYMENT_VERIFICATION cannot be enabled in production!
```

**Solution:**
```bash
# Either set environment to development
ENVIRONMENT=development

# Or disable the skip flag
SKIP_PAYMENT_VERIFICATION=false
```

---

## Payment Issues

### Payment fails with 500 error

**Symptoms:**
- x402 payment initiated
- Payment transaction succeeds on chain
- Backend returns 500 error

**Debugging:**
```bash
# Check backend logs
tail -f /tmp/clawd-backend.log

# Or if running in foreground, check terminal output
```

**Common Causes:**

1. **PUBLIC_URL not accessible**
   ```bash
   # For local development, use ngrok
   ngrok http 8402

   # Update .env
   PUBLIC_URL=https://your-ngrok-url.ngrok-free.dev
   ```

2. **Porkbun insufficient funds**
   - Log into porkbun.com
   - Add funds to your account

3. **Rate limited by Porkbun**
   - Wait 10 seconds between domain checks
   - The backend handles this, but rapid requests can still hit limits

### "Invalid nonce" error

**Error:**
```
{"error": "Invalid nonce"}
```

**Cause:** Payment was made with wrong nonce, or purchase expired.

**Solution:**
```bash
# Start a new purchase
# Purchase IDs expire after 15 minutes
```

### "Invalid recipient address" error

**Error:**
```
{"error": "Invalid recipient address"}
```

**Cause:** Payment was sent to wrong address.

**Solution:**
```bash
# Check TREASURY_ADDRESS in .env matches your wallet
# The payment must go to this exact address
```

---

## DNS Management Issues

### "You don't own this domain"

**Error:**
```
{"detail": "You don't own this domain"}
```

**Cause:** The wallet address doesn't match the purchase wallet.

**Solution:**
```bash
# Check which wallet owns the domain
sqlite3 clawd_domains.db "SELECT owner_wallet FROM domains WHERE domain='yourdomain.xyz';"

# Use that exact wallet address (case-insensitive)
```

### DNS record creation fails

**Error:**
```
{"detail": "Failed to create DNS record"}
```

**Debugging:**
```bash
# Check backend logs for Porkbun API response
tail -f /tmp/clawd-backend.log
```

**Common Causes:**

1. **Invalid record type** - Only A, AAAA, CNAME, MX, TXT, NS, SRV supported
2. **Invalid content** - A records must be valid IPv4, AAAA must be IPv6
3. **Porkbun API error** - Check your Porkbun account status

### "String should have at least 42 characters" on wallet

**Error:**
```
{"detail":[{"type":"string_too_short","loc":["body","wallet"],"msg":"String should have at least 42 characters"}]}
```

**Cause:** Wallet address format is invalid.

**Solution:**
```bash
# Wallet must be exactly 42 characters: 0x + 40 hex chars
# Example: 0x742d35Cc6634C0532925a3b844Bc9e7595f5bE91
```

---

## MCP Server Issues

### Tools not appearing in Claude Desktop

**Symptoms:**
- MCP server configured in claude_desktop_config.json
- Restarted Claude Desktop
- Tools don't appear

**Debugging:**
```bash
# Test MCP server directly
cd mcp-server
npm run build
node dist/index.js

# Should see: "Clawd Domain MCP Server running on stdio"
```

**Solutions:**

1. **Check config file location**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Linux: `~/.config/claude-desktop/claude_desktop_config.json`

2. **Verify JSON syntax**
   ```bash
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | jq .
   ```

3. **Check absolute paths**
   ```json
   {
     "mcpServers": {
       "clawd-domains": {
         "command": "node",
         "args": ["/absolute/path/to/mcp-server/dist/index.js"]
       }
     }
   }
   ```

### "CLAWD_API_URL not set"

**Error:**
```
Error: CLAWD_API_URL environment variable not set
```

**Solution:**
```json
{
  "mcpServers": {
    "clawd-domains": {
      "command": "node",
      "args": ["/path/to/mcp-server/dist/index.js"],
      "env": {
        "CLAWD_API_URL": "http://localhost:8402"
      }
    }
  }
}
```

---

## Porkbun API Issues

### "Insufficient funds"

**Error in logs:**
```
Porkbun registration result: {'status': 'ERROR', 'message': 'Insufficient funds.'}
```

**Solution:**
1. Log into [porkbun.com](https://porkbun.com)
2. Go to Billing
3. Add funds (minimum ~$5 for .xyz domains)

### Rate limit hit

**Symptoms:**
- Domain searches fail intermittently
- "Could not get pricing" errors

**Explanation:**
Porkbun limits domain availability checks to 1 per 10 seconds per API key.

**Solution:**
- The backend handles this automatically
- If you're testing rapidly, wait 10+ seconds between searches

### "Invalid API key"

**Error:**
```
{'status': 'ERROR', 'message': 'Invalid API key'}
```

**Solutions:**

1. **Check key format**
   - API key should start with `pk1_`
   - Secret should start with `sk1_`

2. **Regenerate keys**
   - Go to porkbun.com > Account > API Access
   - Create new API key pair
   - Update .env file

3. **Check for whitespace**
   ```bash
   # .env should have no spaces around =
   PORKBUN_API_KEY=pk1_yourkey  # correct
   PORKBUN_API_KEY = pk1_yourkey  # wrong
   ```

### Domain shows unavailable but should be available

**Cause:** Porkbun may have temporary issues or the domain is reserved.

**Solution:**
```bash
# Verify directly on Porkbun website
# Some domains are reserved or premium
```

---

## General Debugging

### Enable verbose logging

```python
# In backend/src/main.py, add at top:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check database state

```bash
cd backend

# List all purchases
sqlite3 clawd_domains.db "SELECT id, domain, status FROM purchases;"

# List all domains
sqlite3 clawd_domains.db "SELECT domain, owner_wallet FROM domains;"
```

### Test API endpoints directly

```bash
# Health check
curl http://localhost:8402/health

# Search (no auth needed)
curl -X POST http://localhost:8402/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test123"}'

# List domains (need wallet that owns domains)
curl "http://localhost:8402/domains/test.xyz/dns?wallet=0x..."
```

### Reset everything

```bash
# Stop all processes
pkill -f uvicorn
pkill -f "node.*clawd"

# Remove database (WARNING: loses all purchase/domain history)
rm backend/clawd_domains.db

# Restart backend
cd backend
source venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8402 --reload
```

---

## Getting Help

If you're still stuck:

1. Check the [GitHub Issues](https://github.com/noahlevine1717/clawd-domain-marketplace/issues)
2. Open a new issue with:
   - Error message
   - Steps to reproduce
   - Backend logs
   - Environment (OS, Python version, Node version)
