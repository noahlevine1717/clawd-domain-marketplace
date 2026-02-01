# Claude Code Context - Clawd Domain Marketplace

*Last Updated: January 31, 2026*

This file provides context for Claude Code when working on this project.

## Table of Contents

- [Project Overview](#project-overview)
- [Key Components](#key-components)
- [x402 Payment Flow](#x402-payment-flow)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [Common Issues](#common-issues)
- [Security Notes](#security-notes)
- [Development Commands](#development-commands)
- [Database Schema](#database-schema)
- [API Response Codes](#api-response-codes)

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
- `src/relayer.py` - EIP-3009 transferWithAuthorization executor

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
- `clawd_domain_purchase` - Initiate x402 purchase flow (requires registrant info)
- `clawd_domain_confirm` - Confirm purchase after payment (with tx_hash)
- `clawd_domain_list` - List domains owned by a wallet
- `clawd_dns_list` - List DNS records (requires wallet)
- `clawd_dns_create` - Create DNS record (requires wallet)
- `clawd_dns_delete` - Delete DNS record (requires wallet)
- `clawd_domain_nameservers` - Update nameservers (requires wallet)
- `clawd_domain_auth_code` - Get EPP/auth code for domain transfer

## x402 Payment Flow (EIP-3009 Relayer Pattern)

1. Client calls `POST /purchase/initiate` with domain and registrant info
2. Backend returns `purchase_id` and payment details
3. Client calls `GET /purchase/pay/{purchase_id}`
4. Backend returns `402 Payment Required` with x402 JSON body
5. Client signs EIP-3009 authorization (off-chain, no gas needed)
6. Client resubmits with `X-PAYMENT` header containing base64-encoded authorization + signature
7. **Backend relayer** executes `transferWithAuthorization` on USDC contract (pays gas)
8. Backend waits for transaction confirmation
9. Domain is registered with Porkbun

**Key insight:** The client does NOT execute an onchain transfer. They sign an authorization that the server's relayer executes. This enables gasless payments for users.

**Relayer wallet:** Needs ETH on Base for gas fees (~0.01 ETH = 100+ transactions). USDC goes directly from payer to treasury.

## Environment Variables

Required for backend:
- `PORKBUN_API_KEY` - Porkbun API key (pk1_...)
- `PORKBUN_SECRET` - Porkbun secret (sk1_...)
- `TREASURY_ADDRESS` - Wallet to receive USDC payments
- `PUBLIC_URL` - Public URL for x402 callbacks
- `RELAYER_PRIVATE_KEY` - Private key for EIP-3009 relayer (pays gas, required in production)
- `BASE_RPC_URL` - Base network RPC (optional, defaults to public endpoint)

## Testing

See [TESTING.md](./TESTING.md) for comprehensive API tests and [MCP_TESTING.md](./MCP_TESTING.md) for MCP tool tests.

Quick examples:
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
3. **500 on payment** - Check PUBLIC_URL is accessible, relayer has ETH for gas
4. **"You don't own this domain"** - Use wallet that purchased the domain
5. **"Relayer has insufficient gas"** - Fund relayer wallet with ETH on Base
6. **"Transaction reverted"** - Authorization expired or already used (nonces are one-time)

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for comprehensive solutions.

## Security Notes

- Never enable `SKIP_PAYMENT_VERIFICATION` in production
- `.env` files contain secrets - never commit them
- `RELAYER_PRIVATE_KEY` has access to gas funds - protect it
- Database contains purchase history - exclude from git
- Wallet validation uses regex: `^0x[a-fA-F0-9]{40}$`

## Development Commands

```bash
# Backend (canonical command - use this everywhere)
cd backend && source venv/bin/activate && uvicorn src.main:app --host 0.0.0.0 --port 8402

# Backend with auto-reload (development only)
cd backend && source venv/bin/activate && uvicorn src.main:app --host 0.0.0.0 --port 8402 --reload

# MCP Server
cd mcp-server && npm run build && node dist/index.js

# Local tunnel for testing x402 (required for external clients)
ngrok http 8402
# Then update PUBLIC_URL in backend/.env with the ngrok URL
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
