# Clawd Domain Marketplace

A CLI-native domain registration marketplace that enables purchasing domains with USDC using the x402 payment protocol. Built for AI agents and developers who want programmatic domain management.

## Features

- **x402 Payment Protocol**: HTTP 402-based payment flow for USDC on Base network
- **Porkbun Integration**: Real domain registration through Porkbun's API
- **Full DNS Management**: Create, list, and delete DNS records (A, AAAA, CNAME, MX, TXT, NS, SRV)
- **Wallet-Based Access Control**: Domain owners can only manage their own domains
- **MCP Server**: Claude Desktop integration for AI-assisted domain management
- **Security Hardened**: Rate limiting, CORS protection, input validation, error sanitization

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Clawd Domain Marketplace                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   MCP Server │────▶│   Backend    │────▶│   Porkbun    │    │
│  │  (TypeScript)│     │   (FastAPI)  │     │     API      │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         │                    │                                   │
│         │                    ▼                                   │
│         │             ┌──────────────┐                          │
│         │             │   SQLite DB  │                          │
│         │             │  (Purchases  │                          │
│         │             │   & Domains) │                          │
│         │             └──────────────┘                          │
│         │                    │                                   │
│         ▼                    ▼                                   │
│  ┌──────────────┐     ┌──────────────┐                          │
│  │    Claude    │     │  x402 Wallet │                          │
│  │   Desktop    │     │  (USDC/Base) │                          │
│  └──────────────┘     └──────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Backend** | API server handling purchases, DNS, payments | FastAPI (Python) |
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

   Add to your Claude Desktop MCP config (`~/.config/claude-desktop/claude_desktop_config.json` on Linux, `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):
   ```json
   {
     "mcpServers": {
       "clawd-domains": {
         "command": "node",
         "args": ["/path/to/clawd-domain-marketplace/mcp-server/dist/index.js"],
         "env": {
           "CLAWD_API_URL": "https://your-backend-url.com"
         }
       }
     }
   }
   ```

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

#### 1. Clone and Setup Backend

```bash
git clone https://github.com/noahlevine1717/clawd-domain-marketplace.git
cd clawd-domain-marketplace/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials (see Configuration section)
```

#### 2. Configure Your Credentials

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

#### 3. Start the Backend

```bash
cd backend
source venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8402 --reload
```

#### 4. Setup MCP Server

```bash
cd mcp-server
npm install
npm run build
```

## Configuration

### Backend Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PORKBUN_API_KEY` | Yes | Your Porkbun API key (starts with `pk1_`) |
| `PORKBUN_SECRET` | Yes | Your Porkbun secret key (starts with `sk1_`) |
| `TREASURY_ADDRESS` | Yes | Ethereum address to receive USDC payments |
| `PUBLIC_URL` | Yes | Public URL for x402 callbacks |
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
export CLAWD_API_URL=http://localhost:8402  # or your production URL
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

The x402 protocol enables HTTP-native cryptocurrency payments.

### Flow

```
┌─────────┐          ┌─────────┐          ┌─────────┐
│  Client │          │ Backend │          │  Chain  │
└────┬────┘          └────┬────┘          └────┬────┘
     │                    │                    │
     │  GET /pay/{id}     │                    │
     │───────────────────▶│                    │
     │                    │                    │
     │  402 + WWW-Auth    │                    │
     │◀───────────────────│                    │
     │                    │                    │
     │  Pay USDC          │                    │
     │────────────────────┼───────────────────▶│
     │                    │                    │
     │  GET /pay/{id}     │                    │
     │  + Authorization   │                    │
     │───────────────────▶│                    │
     │                    │   Verify Payment   │
     │                    │───────────────────▶│
     │                    │                    │
     │  200 + Domain Info │                    │
     │◀───────────────────│                    │
     │                    │                    │
```

### WWW-Authenticate Header Format

```
WWW-Authenticate: x402 recipient="0x...", amount="4.99", currency="USDC", nonce="clawd-uuid", description="Domain: example.xyz (1 year)"
```

### Authorization Header Format

```
Authorization: x402 signature="0x...", payer="0x...", amount="4.99", recipient="0x...", nonce="clawd-uuid"
```

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
- [ ] Configure specific `ALLOWED_ORIGINS` (not wildcard)
- [ ] Use HTTPS for `PUBLIC_URL`
- [ ] Set up PostgreSQL instead of SQLite
- [ ] Configure proper rate limits
- [ ] Set up monitoring and logging
- [ ] Never enable `SKIP_PAYMENT_VERIFICATION`

## Security

### Built-in Protections

| Protection | Description |
|------------|-------------|
| **Rate Limiting** | 20/min search, 10/min purchase, 30/min DNS |
| **CORS** | Specific origins only (no wildcard in production) |
| **Input Validation** | Strict Pydantic validation on all inputs |
| **Wallet Validation** | Ethereum address regex verification |
| **Access Control** | Wallet-based domain ownership verification |
| **Error Sanitization** | No file paths or secrets in error messages |
| **Production Guards** | Payment bypass disabled in production |

### Security Best Practices

1. **Never commit `.env` files** - Use `.env.example` as template
2. **Rotate API keys** if accidentally exposed
3. **Use HTTPS** in production
4. **Monitor rate limits** for abuse patterns
5. **Keep dependencies updated**

## Troubleshooting

See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for comprehensive troubleshooting guide.

### Common Issues

**"Insufficient funds" from Porkbun**
```
Solution: Add funds to your Porkbun account at porkbun.com
```

**"Rate limit exceeded"**
```
Solution: Wait 1 minute for rate limits to reset
Note: Porkbun also has 1 domain check per 10 seconds limit
```

**Payment fails with 500**
```
1. Check backend logs: tail -f /tmp/clawd-backend.log
2. Verify PUBLIC_URL is accessible (use ngrok for local dev)
3. Check Porkbun account has sufficient funds
```

**"You don't own this domain"**
```
Solution: Use the same wallet address that purchased the domain
```

## MCP Tools Reference

| Tool | Description | Parameters |
|------|-------------|------------|
| `clawd_domain_search` | Search domain availability | `query`, `tlds?` |
| `clawd_domain_purchase` | Initiate x402 purchase | `domain`, `years?` |
| `clawd_dns_list` | List DNS records | `domain`, `wallet` |
| `clawd_dns_create` | Create DNS record | `domain`, `type`, `name`, `content`, `wallet` |
| `clawd_dns_delete` | Delete DNS record | `domain`, `record_id`, `wallet` |
| `clawd_domain_nameservers` | Update nameservers | `domain`, `nameservers`, `wallet` |

## Project Structure

```
clawd-domain-marketplace/
├── README.md                 # This file
├── CLAUDE.md                 # Claude Code context
├── DEPLOYMENT.md             # Deployment guide
├── TROUBLESHOOTING.md        # Common issues
├── LICENSE                   # MIT License
├── .gitignore
│
├── backend/                  # FastAPI backend
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py          # API endpoints
│   │   ├── config.py        # Configuration
│   │   ├── database.py      # SQLite/PostgreSQL
│   │   ├── porkbun.py       # Porkbun API client
│   │   └── payments.py      # x402 verification
│   ├── requirements.txt
│   ├── .env.example
│   └── pyproject.toml
│
└── mcp-server/              # MCP server for Claude
    ├── src/
    │   └── index.ts         # MCP tool definitions
    ├── package.json
    └── tsconfig.json
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
