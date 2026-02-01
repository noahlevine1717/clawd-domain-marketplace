# Clawd Domain Marketplace

*Last Updated: January 31, 2026*

A CLI-native domain registration marketplace that enables purchasing domains with USDC using the x402 payment protocol. Built for AI agents and developers who want programmatic domain management.

> **TL;DR:** Search domains, pay with USDC on Base, get instant registration. Works with Claude Desktop/Code via MCP.
>
> ```bash
> # Quick test (no setup needed):
> curl https://your-backend-url.com/health
> # Expected: {"status": "ok", "version": "0.2.0", ...}
> ```

> **Includes [clawd-wallet](https://github.com/csmoove530/clawd-wallet):** This repo comes with clawd-wallet as a git submodule, providing USDC payment capabilities via the x402 protocol. Clone with `--recurse-submodules` to get both.

## Features

- **x402 Payment Protocol**: HTTP 402-based payment flow for USDC on Base network
- **Porkbun Integration**: Real domain registration through Porkbun's API
- **Full DNS Management**: Create, list, and delete DNS records (A, AAAA, CNAME, MX, TXT, NS, SRV)
- **Wallet-Based Access Control**: Domain owners can only manage their own domains
- **MCP Server**: Claude Desktop integration for AI-assisted domain management
- **Includes clawd-wallet**: Bundled as a git submodule for seamless USDC payments and wallet management
- **Security Hardened**: Rate limiting, CORS protection, input validation, error sanitization

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Clawd Domain Marketplace                         │
│                    (x402 Payment Protocol)                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────┐                                                  │
│  │  Claude Desktop │                                                  │
│  │  or Claude Code │                                                  │
│  └────────┬────────┘                                                  │
│           │                                                           │
│           ▼                                                           │
│  ┌─────────────────────────────────────────┐     ┌──────────────┐    │
│  │              MCP Servers                 │     │   Porkbun    │    │
│  │  ┌─────────────┐    ┌─────────────┐     │     │     API      │    │
│  │  │clawd-domains│    │clawd-wallet │     │     └──────┬───────┘    │
│  │  │  (search,   │    │  (x402      │     │            │            │
│  │  │   purchase, │    │   payments, │     │            │            │
│  │  │   DNS)      │    │   USDC)     │     │            │            │
│  │  └──────┬──────┘    └──────┬──────┘     │            │            │
│  └─────────┼──────────────────┼────────────┘            │            │
│            │                  │                         │            │
│            ▼                  │                         │            │
│  ┌─────────────────┐          │                         │            │
│  │     Backend     │◀─────────┘                         │            │
│  │    (FastAPI)    │     X-PAYMENT header               │            │
│  │                 │     (EIP-3009 authorization)       │            │
│  │ ┌─────────────┐ │                                    │            │
│  │ │ HTTP 402    │ │  ◀── Returns payment requirements  │            │
│  │ │ + x402 JSON │ │                                    │            │
│  │ └─────────────┘ │                                    │            │
│  │ ┌─────────────┐ │                                    │            │
│  │ │ Relayer     │ │  ──▶ Executes USDC transfer        │            │
│  │ └─────────────┘ │────────────────────────────────────┘            │
│  │                 │      Register domain after                      │
│  │                 │      relayer confirms tx                        │
│  └────────┬────────┘                                                 │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────┐          ┌─────────────────┐                    │
│  │   SQLite DB     │          │   Base Network  │                    │
│  │  (Purchases &   │          │  (USDC onchain │                    │
│  │   Ownership)    │◀────────▶│   verification) │                    │
│  └─────────────────┘          └─────────────────┘                    │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### x402 Payment Flow (EIP-3009 Relayer Pattern)

```
1. Client: GET /purchase/pay/{id}

2. Backend: HTTP 402 Payment Required
            Returns x402 JSON with payment requirements

3. clawd-wallet: Signs EIP-3009 transferWithAuthorization
                 (No onchain tx yet - just a signature)

4. Client: GET /purchase/pay/{id}
           X-PAYMENT: base64-encoded authorization + signature

5. Backend Relayer: Executes transferWithAuthorization on USDC contract
                    Pays gas, waits for confirmation

6. Backend: Domain registered with Porkbun

7. Client: HTTP 200 + Domain info!
```

**Key insight:** The client signs an *authorization*, not a transaction. The server's relayer executes the actual onchain transfer, paying gas fees. This enables gasless payments for users.

### Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Backend** | API server handling purchases, DNS, payments | FastAPI (Python) |
| **Relayer** | Executes EIP-3009 transfers (pays gas for users) | web3.py |
| **MCP Server** | Claude Desktop integration | TypeScript |
| **Database** | Persistent storage for purchases and ownership | SQLite / PostgreSQL |
| **Porkbun** | Domain registration and DNS management | REST API |

## Quick Start

### For Users (MCP Server Only)

If you just want to use the domain marketplace through Claude Desktop:

1. **Install the MCP Server**
   ```bash
   cd mcp-server
   npm install
   npm run build
   ```

2. **Configure Claude Desktop**

   First, get the absolute path to the MCP server:
   ```bash
   cd mcp-server && pwd
   # Copy the output (e.g., /Users/you/clawd-domain-marketplace/mcp-server)
   ```

   Add to your Claude Desktop MCP config:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/claude-desktop/claude_desktop_config.json`

   ```json
   {
     "mcpServers": {
       "clawd-domains": {
         "command": "node",
         "args": ["/YOUR/ABSOLUTE/PATH/mcp-server/dist/index.js"],
         "env": {
           "CLAWD_BACKEND_URL": "https://your-backend-url.com"
         }
       }
     }
   }
   ```

   > **Important:** Replace `/YOUR/ABSOLUTE/PATH` with the output from the `pwd` command above.

3. **Use in Claude**
   - Search: "Search for available domains like myproject"
   - Purchase: "Buy myproject.xyz domain"
   - DNS: "Add an A record pointing to 1.2.3.4"

### For Resellers (Full Setup)

If you want to run your own domain marketplace:

#### Prerequisites

- Python 3.11+
- Node.js 18+
- [Porkbun Account](https://porkbun.com) with API access and funds
- Ethereum wallet for receiving USDC payments

#### 1. Clone Repository (with clawd-wallet)

```bash
# Clone with submodules to get clawd-wallet automatically
git clone --recurse-submodules https://github.com/noahlevine1717/clawd-domain-marketplace.git
cd clawd-domain-marketplace

# If you already cloned without --recurse-submodules:
git submodule update --init --recursive
```

#### 2. Setup Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials (see Configuration section)
```

#### 3. Configure Your Credentials

Edit `backend/.env`:

```bash
# Your Porkbun API credentials
PORKBUN_API_KEY=pk1_your_key_here
PORKBUN_SECRET=sk1_your_secret_here

# Your wallet to receive USDC payments
TREASURY_ADDRESS=0xYourWalletAddress

# Your public URL (use ngrok for local dev)
PUBLIC_URL=https://your-domain.com
```

#### 4. Start the Backend

```bash
cd backend
source venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8402 --reload
```

#### 5. Setup MCP Servers

```bash
# Build clawd-domains MCP server
cd mcp-server && npm install && npm run build

# Build clawd-wallet MCP server (included as submodule)
cd ../clawd-wallet && npm install && npm run build
```

## Configuration

### Backend Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PORKBUN_API_KEY` | Yes | Your Porkbun API key (starts with `pk1_`) |
| `PORKBUN_SECRET` | Yes | Your Porkbun secret key (starts with `sk1_`) |
| `TREASURY_ADDRESS` | Yes | Ethereum address to receive USDC payments |
| `PUBLIC_URL` | Yes | Public URL for x402 callbacks |
| `RELAYER_PRIVATE_KEY` | Yes (prod) | Private key for EIP-3009 relayer (pays gas) |
| `BASE_RPC_URL` | No | Base network RPC (default: public endpoint) |
| `ENVIRONMENT` | No | `development` or `production` |
| `DATABASE_URL` | No | Database connection string |
| `ALLOWED_ORIGINS` | No | CORS allowed origins (comma-separated) |

### Getting Porkbun API Keys

1. Log into [porkbun.com](https://porkbun.com)
2. Go to **Account** > **API Access**
3. Click **Create API Key**
4. Copy both the API key and Secret key
5. **Important**: Add funds to your Porkbun account to enable registration

### MCP Server Configuration

The MCP server connects to your backend. Set the backend URL:

```bash
export CLAWD_BACKEND_URL=http://localhost:8402  # or your production URL
```

## API Reference

### Domain Search

```bash
POST /search
Content-Type: application/json

{
  "query": "myproject",
  "tlds": ["com", "dev", "xyz"]
}
```

Response:
```json
{
  "query": "myproject",
  "results": [
    {
      "domain": "myproject.xyz",
      "available": true,
      "first_year_price_usdc": "4.99",
      "renewal_price_usdc": "14.99"
    }
  ]
}
```

### Initiate Purchase

```bash
POST /purchase/initiate
Content-Type: application/json

{
  "domain": "myproject.xyz",
  "years": 1,
  "registrant": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com"
  }
}
```

Response:
```json
{
  "purchase_id": "uuid-here",
  "domain": "myproject.xyz",
  "payment_request": {
    "amount_usdc": "4.99",
    "recipient": "0x...",
    "chain_id": 8453,
    "memo": "clawd:domain:uuid-here"
  }
}
```

### x402 Payment Flow

```bash
GET /purchase/pay/{purchase_id}
# Returns 402 with WWW-Authenticate header containing payment details
# Client pays USDC and resubmits with Authorization header
```

### DNS Management

```bash
# List records
GET /domains/{domain}/dns?wallet=0x...

# Create record
POST /domains/dns
{
  "domain": "myproject.xyz",
  "record_type": "A",
  "name": "www",
  "content": "1.2.3.4",
  "wallet": "0x..."
}

# Delete record
DELETE /domains/dns
{
  "domain": "myproject.xyz",
  "record_id": "123456",
  "wallet": "0x..."
}
```

## DNS Management

The marketplace provides full DNS control for registered domains.

### Supported Record Types

| Type | Description | Example Content |
|------|-------------|-----------------|
| A | IPv4 address | `1.2.3.4` |
| AAAA | IPv6 address | `2001:db8::1` |
| CNAME | Canonical name | `www.example.com` |
| MX | Mail exchange | `mail.example.com` |
| TXT | Text record | `v=spf1 include:_spf.google.com ~all` |
| NS | Nameserver | `ns1.example.com` |
| SRV | Service record | `0 5 5060 sipserver.example.com` |

### Access Control

- Only the wallet that paid for a domain can manage its DNS
- Ownership is verified on every DNS operation
- Invalid wallet addresses are rejected with validation error

### Example: Setting Up a Website

```bash
# Point root domain to your server
curl -X POST http://localhost:8402/domains/dns \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "mysite.xyz",
    "record_type": "A",
    "name": "",
    "content": "123.45.67.89",
    "wallet": "0xYourWallet"
  }'

# Point www subdomain
curl -X POST http://localhost:8402/domains/dns \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "mysite.xyz",
    "record_type": "CNAME",
    "name": "www",
    "content": "mysite.xyz",
    "wallet": "0xYourWallet"
  }'

# Add email verification
curl -X POST http://localhost:8402/domains/dns \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "mysite.xyz",
    "record_type": "TXT",
    "name": "",
    "content": "v=spf1 include:_spf.google.com ~all",
    "wallet": "0xYourWallet"
  }'
```

## x402 Payment Protocol

The x402 protocol enables HTTP-native cryptocurrency payments using EIP-3009 gasless authorization.

> **TL;DR:** Client signs authorization → Server executes transfer → Domain registered. Users don't need ETH for gas.

### Sequence Diagram

```
┌─────────┐          ┌─────────┐          ┌─────────┐
│  Client │          │ Backend │          │  Chain  │
└────┬────┘          └────┬────┘          └────┬────┘
     │                    │                    │
     │  GET /pay/{id}     │                    │
     │───────────────────▶│                    │
     │                    │                    │
     │  402 + x402 JSON   │                    │
     │◀───────────────────│                    │
     │                    │                    │
     │  Sign EIP-3009     │                    │
     │  authorization     │                    │
     │                    │                    │
     │  GET /pay/{id}     │                    │
     │  + X-PAYMENT       │                    │
     │───────────────────▶│                    │
     │                    │                    │
     │                    │  Relayer executes  │
     │                    │  transferWithAuth  │
     │                    │───────────────────▶│
     │                    │                    │
     │                    │  tx confirmed      │
     │                    │◀───────────────────│
     │                    │                    │
     │  200 + Domain Info │                    │
     │◀───────────────────│                    │
     │                    │                    │
```

### Complete 402 Response Example

```bash
curl -i http://localhost:8402/purchase/pay/d336e9e5-ec45-4483-af0f-7c5d1f122223
```

```http
HTTP/1.1 402 Payment Required
Content-Type: application/json

{
  "x402Version": 1,
  "error": "X-PAYMENT header is required",
  "accepts": [
    {
      "scheme": "exact",
      "network": "base",
      "maxAmountRequired": "4990000",
      "resource": "https://your-backend.com/purchase/pay/d336e9e5-...",
      "description": "Domain: example.xyz (1 year)",
      "mimeType": "application/json",
      "payTo": "0x742D35cc6634C0532925a3B844bc9E7595f5BE91",
      "maxTimeoutSeconds": 300,
      "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      "extra": {
        "name": "USD Coin",
        "version": "2"
      },
      "outputSchema": {
        "input": {
          "type": "http",
          "method": "POST",
          "discoverable": true
        }
      }
    }
  ]
}
```

**Key fields:**
- `maxAmountRequired`: Amount in micro-units (4990000 = $4.99 USDC)
- `payTo`: Treasury address receiving payment
- `asset`: USDC contract on Base (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)
- `network`: Must be `"base"` (not `"base-mainnet"`)

### X-PAYMENT Header (Client → Server)

The client sends a base64-encoded JSON payload:

```json
{
  "x402Version": 1,
  "scheme": "exact",
  "network": "base",
  "payload": {
    "signature": "0x4ce4557e610807334a24cadebb38a1b39d392a23...",
    "authorization": {
      "from": "0xE3E6604323Ea5d0bF926255a72daC8c04FDc6891",
      "to": "0x742D35cc6634C0532925a3B844bc9E7595f5BE91",
      "value": "4990000",
      "validAfter": "1769918598",
      "validBefore": "1769922258",
      "nonce": "0xb9389efa8490ac6f35e59701eaecdf7863df931c..."
    }
  }
}
```

**Critical insight:** This is an EIP-3009 authorization, NOT a completed transaction. The server's relayer executes `transferWithAuthorization` on the USDC contract using this signed authorization.

## EIP-3009 Relayer

The backend includes a relayer that executes EIP-3009 `transferWithAuthorization` calls on the USDC contract. This enables gasless payments for users.

### How It Works

1. User signs an EIP-3009 authorization (off-chain, no gas required)
2. Server relayer submits `transferWithAuthorization` to USDC contract
3. Relayer pays gas fees on behalf of the user
4. USDC transfers directly from user to treasury

### Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `RELAYER_PRIVATE_KEY` | Yes (prod) | Private key of wallet that pays gas |
| `BASE_RPC_URL` | No | Base network RPC (default: `https://mainnet.base.org`) |

### Relayer Wallet Setup

```bash
# Generate a new wallet for the relayer
node -e "const w = require('ethers').Wallet.createRandom(); console.log('Address:', w.address, '\nPrivate Key:', w.privateKey)"

# Add to backend/.env
RELAYER_PRIVATE_KEY=0x...your_private_key...

# Fund with ETH on Base for gas (~0.01 ETH = 100+ transactions)
# Send ETH to the relayer address on Base network
```

**Important:** The relayer wallet only needs ETH for gas. USDC goes directly from payer to treasury.

---

## Deployment

### Railway (Recommended)

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed Railway deployment instructions.

Quick steps:
1. Create Railway project
2. Add Python service from `backend/` directory
3. Configure environment variables
4. Deploy

### Docker

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8402"]
```

```bash
cd backend
docker build -t clawd-backend .
docker run -p 8402:8402 --env-file .env clawd-backend
```

### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Set `RELAYER_PRIVATE_KEY` and fund relayer with ETH on Base
- [ ] Configure specific `ALLOWED_ORIGINS` (not wildcard)
- [ ] Use HTTPS for `PUBLIC_URL`
- [ ] Set up PostgreSQL instead of SQLite
- [ ] Configure proper rate limits
- [ ] Set up monitoring and logging
- [ ] Never enable `SKIP_PAYMENT_VERIFICATION`

## Security

### Wallet-Based Multi-Tenancy

Each user's wallet address acts as their unique identifier (like an API key):

```
┌─────────────────────────────────────────────────────────────┐
│                    User Isolation Model                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Wallet A (0x123...)          Wallet B (0x456...)           │
│  ├── myproject.xyz            ├── coolapp.dev               │
│  ├── mysite.com               └── example.org               │
│  └── DNS records...               └── DNS records...        │
│                                                              │
│  ✅ Wallet A can only see/manage Wallet A's domains         │
│  ✅ Wallet B can only see/manage Wallet B's domains         │
│  ❌ Wallets cannot see or access each other's domains       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key points:**
- Domains are owned by the wallet that paid for them (via x402)
- All domain/DNS operations require the owning wallet address
- Users cannot list, view, or manage other users' domains
- No shared state between different wallet users

### Built-in Protections

| Protection | Description |
|------------|-------------|
| **Wallet Isolation** | Each wallet only sees its own domains |
| **Rate Limiting** | 20/min search, 10/min purchase, 30/min DNS |
| **CORS** | Specific origins only (no wildcard in production) |
| **Input Validation** | Strict Pydantic validation on all inputs |
| **Wallet Validation** | Ethereum address regex verification |
| **Access Control** | Wallet-based domain ownership verification |
| **Error Sanitization** | No file paths or secrets in error messages |
| **Production Guards** | Payment bypass disabled in production |

### Security Best Practices

1. **Never commit `.env` files** - Use `.env.example` as template
2. **Protect `RELAYER_PRIVATE_KEY`** - Has access to gas funds
3. **Rotate API keys** if accidentally exposed
4. **Use HTTPS** in production
5. **Monitor rate limits** for abuse patterns
6. **Keep dependencies updated**

## Testing

- **API Testing**: See [TESTING.md](./TESTING.md) for curl-based test commands
- **MCP Testing**: See [MCP_TESTING.md](./MCP_TESTING.md) for Claude Desktop/Code testing

## Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for comprehensive troubleshooting guide.

### Common Issues

> For comprehensive troubleshooting, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

**"Insufficient funds" from Porkbun** → [Full details](./TROUBLESHOOTING.md#insufficient-funds)
```
Solution: Add funds to your Porkbun account at porkbun.com
```

**"Rate limit exceeded"** → [Full details](./TROUBLESHOOTING.md#rate-limit-hit)
```
Solution: Wait 1 minute for rate limits to reset
Note: Porkbun also has 1 domain check per 10 seconds limit
```

**Payment fails with 500** → [Full details](./TROUBLESHOOTING.md#payment-fails-with-500-error)
```
1. Check backend logs: tail -f /tmp/backend.log
2. Verify PUBLIC_URL is accessible (use ngrok for local dev)
3. Check relayer wallet has ETH for gas
4. Check Porkbun account has sufficient funds
```

**"You don't own this domain"** → [Full details](./TROUBLESHOOTING.md#you-dont-own-this-domain)
```
Solution: Use the same wallet address that purchased the domain
```

**"bad address checksum"** → [Full details](./TROUBLESHOOTING.md#bad-address-checksum-error-ethersjs--clawd-wallet)
```
Solution: Use properly checksummed address in TREASURY_ADDRESS
```

## MCP Tools Reference

| Tool | Description | Parameters |
|------|-------------|------------|
| `clawd_domain_search` | Search domain availability | `query`, `tlds?` |
| `clawd_domain_purchase` | Initiate x402 purchase | `domain`, `first_name`, `last_name`, `email`, `years?` |
| `clawd_domain_confirm` | Confirm purchase after payment | `purchase_id`, `tx_hash` |
| `clawd_domain_list` | List domains owned by wallet | `wallet` |
| `clawd_dns_list` | List DNS records | `domain`, `wallet` |
| `clawd_dns_create` | Create DNS record | `domain`, `record_type`, `name`, `content`, `wallet` |
| `clawd_dns_delete` | Delete DNS record | `domain`, `record_id`, `wallet` |
| `clawd_domain_nameservers` | Update nameservers | `domain`, `nameservers`, `wallet` |
| `clawd_domain_auth_code` | Get transfer auth code | `domain`, `wallet` |

## Project Structure

```
clawd-domain-marketplace/
├── README.md                 # This file
├── CLAUDE.md                 # Claude Code context
├── DEPLOYMENT.md             # Deployment guide
├── TROUBLESHOOTING.md        # Common issues & solutions
├── TESTING.md                # API/curl testing guide
├── MCP_TESTING.md            # MCP tools testing guide
├── LICENSE                   # MIT License
├── .gitignore
├── .gitmodules               # Submodule configuration
│
├── backend/                  # FastAPI backend
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py          # API endpoints
│   │   ├── config.py        # Configuration
│   │   ├── database.py      # SQLite/PostgreSQL
│   │   ├── porkbun.py       # Porkbun API client
│   │   ├── payments.py      # x402 verification
│   │   └── relayer.py       # EIP-3009 payment relayer
│   ├── requirements.txt
│   ├── .env.example
│   └── pyproject.toml
│
├── mcp-server/              # MCP server for domains
│   ├── src/
│   │   └── index.ts         # MCP tool definitions
│   ├── package.json
│   └── tsconfig.json
│
└── clawd-wallet/            # MCP server for payments (submodule)
    └── (git submodule → github.com/csmoove530/clawd-wallet)
```

## License

MIT License - See [LICENSE](./LICENSE)

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

Built with [Claude Code](https://claude.ai/code)
