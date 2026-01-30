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

### "bad address checksum" error (ethers.js / clawd-wallet)

**Error:**
```
bad address checksum (argument="address", value="0x742d35Cc6634C0532925a3b844Bc9e7595f5bE91", code=INVALID_ARGUMENT)
```

**Cause:** ethers.js requires EIP-55 checksummed addresses. The address has incorrect casing.

**Solution:**
```bash
# Get the correctly checksummed address
node -e "const { ethers } = require('ethers'); console.log(ethers.getAddress('0x742d35Cc6634C0532925a3b844Bc9e7595f5bE91'.toLowerCase()));"

# Update your .env with the checksummed version
# Wrong:  TREASURY_ADDRESS=0x742d35Cc6634C0532925a3b844Bc9e7595f5bE91
# Right:  TREASURY_ADDRESS=0x742D35cc6634C0532925a3B844bc9E7595f5BE91
```

**Note:** All-lowercase addresses also work but provide no checksum protection.

### "insufficient funds for intrinsic transaction cost" error

**Error:**
```
USDC transfer failed: insufficient funds for intrinsic transaction cost
```

**Cause:** The wallet has USDC but no ETH for gas fees. ERC-20 token transfers require native currency (ETH on Base) to pay for transaction gas.

**Solution:**
```bash
# Check ETH balance
node -e "
const { ethers } = require('ethers');
const p = new ethers.JsonRpcProvider('https://mainnet.base.org');
p.getBalance('YOUR_WALLET_ADDRESS').then(b => console.log('ETH:', ethers.formatEther(b)));
"

# Fund the wallet with ETH on Base network
# Even 0.001 ETH (~$3) is enough for hundreds of transactions on Base
# Send from Coinbase, bridge from Ethereum, or use a faucet
```

**Typical gas costs for USDC transfers:**
| Network | Cost |
|---------|------|
| Base | ~$0.001-0.01 |
| Ethereum | ~$2-10 |
| Polygon | ~$0.001 |

### x402 payment returns success but no transfer happens

**Symptoms:**
- `x402_payment_request` returns `{"success": true, "response": null}`
- Wallet balance unchanged
- No transaction on chain

**Cause:** The payment endpoint may only accept GET requests (not POST) for the 402 flow.

**Solution:**
```bash
# Test what method the endpoint accepts
curl -i http://localhost:8402/purchase/pay/YOUR_PURCHASE_ID

# If you get 402, it accepts GET
# If you get 405 "Method Not Allowed", you're using the wrong method

# When using clawd-wallet, use method: "GET"
```

### Config changes not taking effect

**Symptoms:**
- Updated config.py but backend still uses old values
- TREASURY_ADDRESS shows old value after restart

**Cause:** The `.env` file overrides defaults in config.py. The dotenv package loads environment variables first.

**Solution:**
```bash
# Check what's in .env
cat backend/.env | grep TREASURY

# Update the .env file, not just config.py
nano backend/.env

# Restart the backend completely
pkill -9 -f uvicorn
cd backend && source venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8402
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

## clawd-wallet Integration Issues

### Wallet not making onchain transfers

**Symptoms:**
- Payment "succeeds" but no blockchain transaction
- Balance doesn't change
- No tx_hash in response

**Debugging:**
```bash
# Check if wallet has ETH for gas
node -e "
const { ethers } = require('ethers');
const p = new ethers.JsonRpcProvider('https://mainnet.base.org');
p.getBalance('0x10c4B8A12604a79b9f5534Cfdd763c3182C8EFd4').then(b =>
  console.log('ETH balance:', ethers.formatEther(b))
);
"

# Check USDC balance
# Use x402_check_balance tool or check on basescan.org
```

**Common causes:**
1. No ETH for gas (see "insufficient funds" error above)
2. Address checksum mismatch (see "bad address checksum" above)
3. Wrong HTTP method (see "x402 payment returns success" above)

### Verifying successful payment

After a payment succeeds, verify on chain:
```bash
# Check transaction on Base
# https://basescan.org/tx/YOUR_TX_HASH

# Check wallet balances changed
# Payer wallet should have less USDC
# Treasury wallet should have more USDC
```

### Complete x402 payment flow

For reference, the successful flow is:

1. **Initiate purchase** → Backend returns `purchase_id` and payment details
2. **Request payment endpoint** (GET) → Backend returns 402 with `WWW-Authenticate` header
3. **clawd-wallet parses 402** → Extracts recipient, amount, nonce
4. **On-chain USDC transfer** → Wallet sends real USDC, gets tx_hash
5. **Retry with Authorization header** → Include tx_hash for verification
6. **Backend verifies onchain** → Checks tx_hash on Base blockchain
7. **Domain registered** → Porkbun API called, domain added to your account

---

## Getting Help

If you're still stuck:

1. Check the [GitHub Issues](https://github.com/noahlevine1717/clawd-domain-marketplace/issues)
2. Open a new issue with:
   - Error message
   - Steps to reproduce
   - Backend logs
   - Environment (OS, Python version, Node version)
