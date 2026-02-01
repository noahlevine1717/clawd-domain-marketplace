# Clawd Domain Marketplace - Deployment Guide

## Marketplace Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    END USER EXPERIENCE                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  What user needs:                                                       │
│  ✓ clawd-wallet with USDC balance                                      │
│  ✓ That's it!                                                          │
│                                                                         │
│  What user does NOT need:                                               │
│  ✗ Porkbun account                                                     │
│  ✗ Credit card                                                         │
│  ✗ API keys                                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    MARKETPLACE OPERATOR (YOU)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  You need:                                                              │
│  1. Porkbun account with API access                                    │
│  2. Credit/funds in Porkbun account                                    │
│  3. Treasury wallet to receive USDC payments                           │
│  4. Deployed backend (Railway, Render, etc.)                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Flow

```
Customer                        Your Marketplace                 Porkbun
    │                                  │                            │
    │── "Buy example.dev" ────────────▶│                            │
    │                                  │                            │
    │◀── "Pay $4.99 USDC" ─────────────│                            │
    │                                  │                            │
    │── Pays via x402 ────────────────▶│                            │
    │   (USDC to YOUR treasury)        │                            │
    │                                  │                            │
    │                                  │── Register domain ────────▶│
    │                                  │   (YOUR API keys)          │
    │                                  │   (YOUR account credit)    │
    │                                  │   (Customer as registrant) │
    │                                  │                            │
    │                                  │◀── Domain created ─────────│
    │                                  │                            │
    │◀── "Success! Domain is yours" ───│                            │
    │                                  │                            │
```

## Setup Instructions

### 1. Create Your Porkbun Reseller Account

1. Go to https://porkbun.com
2. Create account with YOUR email/info
3. Verify email and phone
4. Enable API access: https://porkbun.com/account/api
5. Generate API key and secret
6. Add credit to account ($50-100 to start)

### 2. Create Treasury Wallet

Create a dedicated wallet for receiving customer payments:
- Can use a hardware wallet, Coinbase account, etc.
- This receives all USDC payments from customers
- Keep this separate from personal funds

### 3. Configure Environment

Create `.env` for local development:

```bash
# YOUR Porkbun credentials (not customer's!)
PORKBUN_API_KEY=pk1_YOUR_KEY_HERE
PORKBUN_SECRET=sk1_YOUR_SECRET_HERE

# YOUR treasury wallet
TREASURY_ADDRESS=0xYOUR_TREASURY_WALLET

# Production URL (where backend is deployed)
PUBLIC_URL=https://domains.clawd.dev

# Don't skip payment verification in production!
SKIP_PAYMENT_VERIFICATION=false
```

---

## Deploy to Railway (Recommended)

Railway provides easy deployment with automatic SSL, custom domains, and PostgreSQL.

### Prerequisites

- Railway account: https://railway.app
- Railway CLI installed: `npm install -g @railway/cli`
- GitHub repository with your code

### Step 1: Login to Railway

```bash
railway login
```

### Step 2: Create New Project

```bash
cd clawd-domain-marketplace/backend
railway init
```

Select "Empty Project" when prompted.

### Step 3: Add PostgreSQL Database (Recommended)

For production, add persistent storage:

```bash
railway add
```

Select "PostgreSQL" from the list. Railway will provision a database and provide `DATABASE_URL`.

### Step 4: Configure Environment Variables

In Railway dashboard (https://railway.app) or via CLI:

```bash
# Required secrets (use Railway's secrets UI for sensitive values)
railway variables set PORKBUN_API_KEY=pk1_YOUR_KEY
railway variables set PORKBUN_SECRET=sk1_YOUR_SECRET
railway variables set TREASURY_ADDRESS=0xYOUR_WALLET
railway variables set RELAYER_PRIVATE_KEY=0xYOUR_RELAYER_KEY

# Security settings
railway variables set SKIP_PAYMENT_VERIFICATION=false
railway variables set ENVIRONMENT=production

# CORS (replace with your actual domain)
railway variables set ALLOWED_ORIGINS=https://yourdomain.com
```

> **Generate relayer key:** `node -e "const w=require('ethers').Wallet.createRandom();console.log(w.privateKey)"`
> Then fund the relayer address with ~0.01 ETH on Base.

### Step 5: Create railway.json

Create `backend/railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn src.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

### Step 6: Create Procfile (Alternative)

If you prefer a Procfile, create `backend/Procfile`:

```
web: uvicorn src.main:app --host 0.0.0.0 --port $PORT
```

### Step 7: Deploy

```bash
railway up
```

Railway will:
1. Detect Python project
2. Install dependencies from `requirements.txt`
3. Run the start command
4. Provide a public URL (e.g., `https://clawd-backend-production.up.railway.app`)

### Step 8: Set Custom Domain (Optional)

In Railway dashboard:
1. Go to your service → Settings → Domains
2. Add custom domain (e.g., `api.domains.clawd.dev`)
3. Configure DNS CNAME record pointing to Railway

### Step 9: Update PUBLIC_URL

After deployment, update the environment variable:

```bash
railway variables set PUBLIC_URL=https://your-railway-url.up.railway.app
```

### Railway Project Structure

```
clawd-domain-marketplace/
├── backend/
│   ├── src/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── porkbun.py
│   │   └── payments/
│   ├── requirements.txt
│   ├── railway.json        # Railway config
│   └── Procfile            # Alternative start command
└── mcp-server/
    └── ...
```

### Railway Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `PORKBUN_API_KEY` | Yes | Your Porkbun API key |
| `PORKBUN_SECRET` | Yes | Your Porkbun API secret |
| `TREASURY_ADDRESS` | Yes | Your wallet to receive payments |
| `RELAYER_PRIVATE_KEY` | Yes | Private key for EIP-3009 relayer (pays gas) |
| `PUBLIC_URL` | Yes | Your Railway public URL |
| `SKIP_PAYMENT_VERIFICATION` | Yes | Must be `false` in production |
| `DATABASE_URL` | Recommended | PostgreSQL connection string (auto-set by Railway) |
| `ALLOWED_ORIGINS` | Recommended | Comma-separated allowed CORS origins |
| `ENVIRONMENT` | Recommended | Set to `production` |
| `PORT` | Auto | Railway sets this automatically |

> **Relayer Setup:** The relayer wallet pays gas fees for EIP-3009 transfers. Generate one with:
> ```bash
> node -e "const w=require('ethers').Wallet.createRandom();console.log(w.privateKey)"
> ```
> Fund it with ~0.01 ETH on Base network.

### Monitoring on Railway

Railway provides:
- **Logs**: View real-time logs in dashboard
- **Metrics**: CPU, memory, network usage
- **Deployments**: Automatic deploys on git push
- **Rollbacks**: One-click rollback to previous versions

---

## Alternative: Deploy to Render

### Step 1: Create render.yaml

Create `render.yaml` in project root:

```yaml
services:
  - type: web
    name: clawd-domain-backend
    runtime: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: uvicorn src.main:app --host 0.0.0.0 --port $PORT
    rootDir: backend
    envVars:
      - key: PORKBUN_API_KEY
        sync: false
      - key: PORKBUN_SECRET
        sync: false
      - key: TREASURY_ADDRESS
        sync: false
      - key: SKIP_PAYMENT_VERIFICATION
        value: "false"
```

### Step 2: Deploy

1. Go to https://render.com
2. Connect GitHub repo
3. Select "Web Service"
4. Configure environment variables
5. Deploy

---

## Alternative: Deploy to Any VPS

```bash
# On server
git clone <repo>
cd clawd-domain-marketplace/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with secrets
cp .env.example .env
nano .env  # Edit with your values

# Run with gunicorn (production)
pip install gunicorn
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8402

# Or use systemd for auto-restart
sudo systemctl enable clawd-backend
sudo systemctl start clawd-backend
```

### Nginx Configuration (for VPS)

```nginx
server {
    listen 80;
    server_name api.domains.clawd.dev;

    location / {
        proxy_pass http://127.0.0.1:8402;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## Configure MCP Server

After deploying the backend, update Claude Code's configuration:

### ~/.claude.json

```json
{
  "mcpServers": {
    "clawd-domains": {
      "command": "node",
      "args": ["/path/to/mcp-server/dist/index.js"],
      "env": {
        "CLAWD_BACKEND_URL": "https://your-railway-url.up.railway.app"
      }
    }
  }
}
```

---

## Revenue Model

| Item | You Pay | You Charge | Margin |
|------|---------|------------|--------|
| .xyz domain | ~$2 | $4.99 | $2.99 |
| .com domain | ~$10 | $12.99 | $2.99 |
| .dev domain | ~$11 | $14.99 | $3.99 |

**Your costs:**
- Porkbun domain wholesale price
- Server hosting (~$5-20/month on Railway)
- Gas fees (minimal on Base)

**You keep:**
- USDC in treasury
- Periodically convert to USD to refill Porkbun credit

---

## Scaling

### Automate Porkbun Funding
```
1. Monitor treasury balance
2. When threshold reached ($100+):
   - Convert USDC to USD via Coinbase
   - Add credit to Porkbun
3. Continue operations
```

### Multi-Registrar Support
Add Namecheap, Cloudflare Registrar, etc. for:
- Better pricing on some TLDs
- Redundancy
- More TLD options

### Railway Scaling
```bash
# Scale to multiple instances
railway service update --replicas 3

# Or configure in dashboard:
# Settings → Scaling → Horizontal Scaling
```

---

## Security Checklist

See `SECURITY-AUDIT.md` for detailed security analysis.

### Pre-Deployment
- [ ] Review SECURITY-AUDIT.md findings
- [ ] Use dedicated treasury wallet (not personal)
- [ ] Store API keys in Railway secrets (not in code)
- [ ] Enable 2FA on Porkbun account
- [ ] Set `SKIP_PAYMENT_VERIFICATION=false`
- [ ] Configure CORS with specific origins
- [ ] Add PostgreSQL for persistent storage

### Post-Deployment
- [ ] Test full purchase flow
- [ ] Verify payment verification works
- [ ] Monitor treasury for transactions
- [ ] Set up alerts for errors
- [ ] Regular audit of registered domains

---

## Monitoring

Track these metrics:
- Domains registered per day
- Revenue (USDC received)
- Porkbun credit balance
- Failed registrations
- x402 payment success rate

### Railway Observability
- View logs: `railway logs`
- Monitor metrics in dashboard
- Set up alerts via integrations (Slack, Discord, etc.)

### Recommended Tools
- **Sentry**: Error tracking
- **Datadog/New Relic**: APM
- **Uptime Robot**: Uptime monitoring
