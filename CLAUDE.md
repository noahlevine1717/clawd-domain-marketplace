# Claude Code Context - Clawd Domain Marketplace

This file provides context for Claude Code when working on this project.

## Project Overview

Clawd Domain Marketplace is a CLI-native domain registration service that enables purchasing domains with USDC via the x402 payment protocol. It's designed to be used by AI agents and integrates with Claude Desktop via MCP.

## Key Components

### Backend (`/backend`)

FastAPI server handling domain operations and payments.

**Key Files:**
- `src/main.py` - API endpoints, request/response models, rate limiting
- `src/config.py` - Configuration from environment variables
- `src/porkbun.py` - Porkbun API client for domain registration and DNS
- `src/database.py` - SQLite persistence for purchases and domain ownership
- `src/payments.py` - x402 payment verification on Base network

**Important Patterns:**
- All DNS operations require wallet ownership verification
- Rate limiting: 20/min search, 10/min purchase, 30/min DNS
- Porkbun has its own rate limit: 1 domain check per 10 seconds
- Error messages are sanitized to not expose internal paths

### MCP Server (`/mcp-server`)

TypeScript MCP server providing tools for Claude Desktop.

**Key Files:**
- `src/index.ts` - All MCP tool definitions

**Available Tools:**
- `clawd_domain_search` - Search for available domains
- `clawd_domain_purchase` - Initiate x402 purchase flow
- `clawd_dns_list` - List DNS records (requires wallet)
- `clawd_dns_create` - Create DNS record (requires wallet)
- `clawd_dns_delete` - Delete DNS record (requires wallet)
- `clawd_domain_nameservers` - Update nameservers (requires wallet)

## x402 Payment Flow

1. Client calls `POST /purchase/initiate` with domain
2. Backend returns `purchase_id` and payment details
3. Client calls `GET /purchase/pay/{purchase_id}`
4. Backend returns `402 Payment Required` with `WWW-Authenticate` header
5. Client pays USDC on Base network
6. Client resubmits with `Authorization: x402 ...` header
7. Backend verifies payment and registers domain with Porkbun

## Environment Variables

Required for backend:
- `PORKBUN_API_KEY` - Porkbun API key (pk1_...)
- `PORKBUN_SECRET` - Porkbun secret (sk1_...)
- `TREASURY_ADDRESS` - Wallet to receive USDC
- `PUBLIC_URL` - Public URL for x402 callbacks

## Testing

```bash
# Health check
curl http://localhost:8402/health

# Search domains
curl -X POST http://localhost:8402/search \
  -H "Content-Type: application/json" \
  -d '{"query":"myproject","tlds":["xyz"]}'

# DNS management (requires wallet that owns domain)
curl "http://localhost:8402/domains/mydomain.xyz/dns?wallet=0x..."
```

## Common Issues

1. **"Insufficient funds"** - Porkbun account needs balance
2. **Rate limit exceeded** - Wait 1 minute, or 10 seconds for Porkbun checks
3. **500 on payment** - Check PUBLIC_URL is accessible (use ngrok for local dev)
4. **"You don't own this domain"** - Use wallet that purchased the domain

## Security Notes

- Never enable `SKIP_PAYMENT_VERIFICATION` in production
- `.env` files contain secrets - never commit them
- Database contains purchase history - exclude from git
- Wallet validation uses regex: `^0x[a-fA-F0-9]{40}$`

## Development Commands

```bash
# Backend
cd backend && source venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8402 --reload

# MCP Server
cd mcp-server
npm run build
node dist/index.js

# Local tunnel for testing
ngrok http 8402
```

## Database Schema

```sql
-- Purchases table
CREATE TABLE purchases (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    years INTEGER NOT NULL,
    amount TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    registrant TEXT,
    payer TEXT,
    nonce TEXT,
    tx_hash TEXT,
    signature TEXT
);

-- Domains table
CREATE TABLE domains (
    domain TEXT PRIMARY KEY,
    owner_wallet TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    nameservers TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    registrant TEXT
);
```

## API Response Codes

- `200` - Success
- `400` - Bad request (validation error)
- `402` - Payment required (x402 flow)
- `403` - Forbidden (wallet doesn't own domain)
- `404` - Not found
- `429` - Rate limit exceeded
- `500` - Server error (check logs)
