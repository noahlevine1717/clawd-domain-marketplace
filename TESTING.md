# Testing Guide

*Last Updated: January 31, 2026*

This guide provides comprehensive tests to verify your Clawd Domain Marketplace installation is working correctly.

> **TL;DR:** Run the automated test script at the bottom, or step through Tests 1-5 manually.

## Prerequisites

Before running tests, ensure:

1. **Backend is running:**
   ```bash
   # Canonical command (use this everywhere)
   cd backend && source venv/bin/activate && uvicorn src.main:app --host 0.0.0.0 --port 8402
   ```

2. **Environment configured:**
   - `.env` file has valid Porkbun API credentials
   - `TREASURY_ADDRESS` is set to a valid checksummed Ethereum address
   - `RELAYER_PRIVATE_KEY` is set (for payment tests)
   - Porkbun account has sufficient balance (~$5+ for .xyz domains)
   - Relayer wallet has ETH on Base for gas (~0.01 ETH)

3. **For payment tests:**
   - clawd-wallet MCP server configured
   - Wallet has USDC on Base network
   - (No ETH needed for users - relayer pays gas)

---

## Test 1: Health Check

**Purpose:** Verify backend is running and configured correctly.

```bash
curl -s http://localhost:8402/health | jq .
```

**Expected output:**
```json
{
  "status": "ok",
  "mock_mode": false,
  "version": "0.2.0",
  "environment": "development"
}
```

**Troubleshooting:**
- If `mock_mode: true`, Porkbun API keys are missing
- If connection refused, backend isn't running

---

## Test 2: Domain Search

**Purpose:** Verify Porkbun API integration and domain availability checks.

```bash
curl -s -X POST http://localhost:8402/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test-unique-domain-12345","tlds":["xyz","com"]}' | jq .
```

**Expected output:**
```json
{
  "results": [
    {
      "domain": "test-unique-domain-12345.xyz",
      "available": true,
      "price": { "first_year": "4.99", "renewal": "14.99" }
    },
    {
      "domain": "test-unique-domain-12345.com",
      "available": true,
      "price": { "first_year": "12.99", "renewal": "14.99" }
    }
  ]
}
```

**Troubleshooting:**
- If 500 error, check Porkbun API credentials
- If rate limited, wait 10 seconds between searches

---

## Test 3: Purchase Initiation

**Purpose:** Verify purchase flow can be started.

```bash
curl -s -X POST http://localhost:8402/purchase/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "my-test-domain.xyz",
    "years": 1,
    "registrant": {
      "first_name": "Test",
      "last_name": "User",
      "email": "test@example.com"
    }
  }' | jq .
```

**Expected output:**
```json
{
  "purchase_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "domain": "my-test-domain.xyz",
  "years": 1,
  "payment_request": {
    "amount_usdc": "4.99",
    "recipient": "0x742D35cc6634C0532925a3B844bc9E7595f5BE91",
    "chain_id": 8453,
    "memo": "clawd:domain:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "expires_at": "..."
  }
}
```

**Troubleshooting:**
- Verify TREASURY_ADDRESS in .env is correctly checksummed
- Check domain is actually available

---

## Test 4: x402 Payment Flow (402 Response)

**Purpose:** Verify x402 protocol returns correct payment requirements.

```bash
# Use the purchase_id from Test 3
PURCHASE_ID="your-purchase-id-here"

curl -s "http://localhost:8402/purchase/pay/$PURCHASE_ID" | jq .
```

**Expected output:**
```json
{
  "x402Version": 1,
  "error": "X-PAYMENT header is required",
  "accepts": [
    {
      "scheme": "exact",
      "network": "base",
      "maxAmountRequired": "4990000",
      "payTo": "0x742D35cc6634C0532925a3B844bc9E7595f5BE91",
      "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      ...
    }
  ]
}
```

**Key validations:**
- Response is JSON with `x402Version: 1`
- `network` is `"base"` (not `"base-mainnet"`)
- `maxAmountRequired` is in micro-units (4990000 = $4.99)
- `outputSchema` is present (required by some x402 clients)

**Troubleshooting:**
- Must use GET method (not POST)
- Purchase ID must be valid and not expired (15 min timeout)

---

## Test 5: Full Payment Test (Requires Funded Wallet)

**Purpose:** End-to-end test of domain purchase with real payment.

**Warning:** This test spends real USDC!

### Using MCP Tools (Claude Desktop/Claude Code)

```
1. Search: clawd_domain_search("yourtest123", ["xyz"])
2. Purchase: clawd_domain_purchase("yourtest123.xyz", "Your", "Name", "email@example.com")
3. Pay: x402_payment_request(url="http://localhost:8402/purchase/pay/{purchase_id}", method="GET")
4. Verify: clawd_domain_list(wallet="0xYourWallet")
```

### Using curl (Manual)

```bash
# Step 1: Initiate purchase
RESPONSE=$(curl -s -X POST http://localhost:8402/purchase/initiate \
  -H "Content-Type: application/json" \
  -d '{"domain":"yourtest123.xyz","years":1,"registrant":{"first_name":"Test","last_name":"User","email":"test@example.com"}}')

PURCHASE_ID=$(echo $RESPONSE | jq -r '.purchase_id')
echo "Purchase ID: $PURCHASE_ID"

# Step 2: Get payment requirements
curl -s -i "http://localhost:8402/purchase/pay/$PURCHASE_ID"

# Step 3: Make payment via clawd-wallet x402_payment_request tool
# Step 4: Verify domain ownership
```

**Expected result:**
- USDC deducted from wallet
- Domain registered at Porkbun
- Domain appears in clawd_domain_list

---

## Test 6: DNS Management

**Purpose:** Verify DNS record CRUD operations.

**Prerequisites:** You must own a domain (complete Test 5 first, or use an existing domain).

### List DNS Records

```bash
DOMAIN="your-domain.xyz"
WALLET="0xYourWalletAddress"

curl -s "http://localhost:8402/domains/$DOMAIN/dns?wallet=$WALLET" | jq .
```

### Create A Record

```bash
curl -s -X POST "http://localhost:8402/domains/$DOMAIN/dns" \
  -H "Content-Type: application/json" \
  -d "{
    \"wallet\": \"$WALLET\",
    \"record_type\": \"A\",
    \"name\": \"\",
    \"content\": \"192.168.1.1\"
  }" | jq .
```

### Create TXT Record

```bash
curl -s -X POST "http://localhost:8402/domains/$DOMAIN/dns" \
  -H "Content-Type: application/json" \
  -d "{
    \"wallet\": \"$WALLET\",
    \"record_type\": \"TXT\",
    \"name\": \"\",
    \"content\": \"v=spf1 include:_spf.google.com ~all\"
  }" | jq .
```

### Delete Record

```bash
RECORD_ID="123456789"  # Get from list response

curl -s -X DELETE "http://localhost:8402/domains/$DOMAIN/dns/$RECORD_ID?wallet=$WALLET" | jq .
```

**Expected results:**
- List shows NS records by default
- Create returns record ID
- Records appear in list after creation
- Delete removes the record

**Troubleshooting:**
- "You don't own this domain" - use the wallet that purchased the domain
- 500 error - check backend logs for Porkbun API response

---

## Test 7: Wallet Ownership Verification

**Purpose:** Verify multi-tenant isolation (wallets can only access their own domains).

```bash
# Try to access a domain with wrong wallet
curl -s "http://localhost:8402/domains/someone-elses-domain.xyz/dns?wallet=0xWrongWallet" | jq .
```

**Expected output:**
```json
{
  "detail": "You don't own this domain"
}
```

---

## Test 8: Rate Limiting

**Purpose:** Verify rate limits are working.

```bash
# Run 25 searches rapidly (limit is 20/minute)
for i in {1..25}; do
  curl -s -X POST http://localhost:8402/search \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"ratelimit-test-$i\"}" &
done
wait
```

**Expected:** Some requests should return 429 Too Many Requests.

---

## Test 9: Address Checksum Validation

**Purpose:** Verify Ethereum addresses are validated.

```bash
# Invalid checksum (mixed case that doesn't match EIP-55)
curl -s "http://localhost:8402/domains/test.xyz/dns?wallet=0xABCDEF1234567890abcdef1234567890ABCDEF12" | jq .
```

**Note:** The backend accepts any 42-character hex address. Checksum validation happens in clawd-wallet.

---

## Test 10: MCP Server Integration

**Purpose:** Verify MCP tools work correctly.

### In Claude Desktop or Claude Code:

```
1. "Search for available domains with 'mcptest'"
   → Should use clawd_domain_search

2. "What's my wallet balance?"
   → Should use x402_check_balance

3. "List my domains"
   → Should use clawd_domain_list

4. "Create an A record pointing test.mydomain.xyz to 1.2.3.4"
   → Should use clawd_dns_create
```

---

## Test Checklist

Use this checklist to verify your installation:

- [ ] Health check returns `status: ok` and `mock_mode: false`
- [ ] Domain search returns availability and pricing
- [ ] Purchase initiation returns purchase_id and payment details
- [ ] x402 endpoint returns 402 with WWW-Authenticate header
- [ ] Payment endpoint accepts GET (not POST)
- [ ] DNS list works for owned domains
- [ ] DNS create/delete works
- [ ] Wrong wallet gets "You don't own this domain"
- [ ] Rate limiting triggers after 20 searches/minute
- [ ] MCP tools appear in Claude Desktop/Code

---

## Common Issues

### "bad address checksum" in clawd-wallet

Treasury address in `.env` has wrong casing. Fix:
```bash
node -e "const{ethers}=require('ethers');console.log(ethers.getAddress('YOUR_ADDRESS'.toLowerCase()))"
```

### "insufficient funds for intrinsic transaction cost"

Wallet needs ETH for gas on Base network. Send 0.001+ ETH to your wallet.

### Payment succeeds but domain not registered

Check backend logs for Porkbun errors:
```bash
tail -50 /tmp/backend.log | grep -i error
```

Common causes:
- Porkbun account has insufficient funds
- Domain became unavailable between search and purchase
- RPC connection error (transient, retry)

### DNS operations return 500

Check Porkbun API status and your API key validity:
```bash
curl -s -X POST https://api.porkbun.com/api/json/v3/ping \
  -H "Content-Type: application/json" \
  -d '{"apikey":"pk1_xxx","secretapikey":"sk1_xxx"}'
```

---

## Automated Test Script

Save this as `test-all.sh`:

```bash
#!/bin/bash
set -e

BASE_URL="${CLAWD_API_URL:-http://localhost:8402}"
WALLET="${TEST_WALLET:-0x10c4B8A12604a79b9f5534Cfdd763c3182C8EFd4}"

echo "=== Clawd Domain Marketplace Test Suite ==="
echo "Base URL: $BASE_URL"
echo ""

echo "1. Health check..."
curl -sf "$BASE_URL/health" | jq -e '.status == "ok"' > /dev/null
echo "   ✓ Backend is healthy"

echo "2. Domain search..."
curl -sf -X POST "$BASE_URL/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"automated-test-xyz123"}' | jq -e '.results | length > 0' > /dev/null
echo "   ✓ Search working"

echo "3. Purchase initiation..."
PURCHASE=$(curl -sf -X POST "$BASE_URL/purchase/initiate" \
  -H "Content-Type: application/json" \
  -d '{"domain":"automated-test-xyz123.xyz","years":1,"registrant":{"first_name":"Test","last_name":"User","email":"test@example.com"}}')
PURCHASE_ID=$(echo $PURCHASE | jq -r '.purchase_id')
echo "   ✓ Purchase initiated: $PURCHASE_ID"

echo "4. x402 payment endpoint..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/purchase/pay/$PURCHASE_ID")
[ "$STATUS" = "402" ] && echo "   ✓ Returns 402 Payment Required"

echo ""
echo "=== Basic tests passed! ==="
echo ""
echo "For full payment tests, use MCP tools with a funded wallet."
```

Run with:
```bash
chmod +x test-all.sh
./test-all.sh
```

---

## Performance Benchmarks

Expected response times (local development):

| Endpoint | Expected |
|----------|----------|
| Health check | < 50ms |
| Domain search | 1-3s (Porkbun rate limit) |
| Purchase initiate | < 500ms |
| x402 payment | 5-15s (blockchain confirmation) |
| DNS list | 1-2s |
| DNS create/delete | 1-2s |

If response times are significantly higher, check:
- Network connectivity to Porkbun API
- Base RPC endpoint responsiveness
- Database performance (SQLite should be fast for dev)
