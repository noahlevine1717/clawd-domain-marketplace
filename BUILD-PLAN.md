# Clawd Domain Marketplace - MVP Build Plan

## Goal

**Demonstrate end-to-end domain purchase via Claude Code using clawd-wallet MCP tools.**

A developer should be able to:
1. Ask Claude Code to search for a domain
2. See availability and pricing
3. Purchase with USDC via clawd-wallet
4. Get confirmation that domain is registered

---

## Build Philosophy

**Simplest possible path to working demo:**
- No standalone CLI initially - use Claude Code as the interface
- Minimal backend - just enough to bridge wallet ↔ registrar
- Single registrar (Porkbun)
- Single payment method (USDC on Base)
- Focus on happy path first

---

## Architecture: MVP

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MVP ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   CLAUDE CODE (User Interface)                                      │
│   ├── Natural language: "find me a domain for my project"         │
│   ├── Calls Clawd MCP tools for domain operations                  │
│   └── Calls clawd-wallet MCP for payments                          │
│                                                                     │
│   CLAWD MCP SERVER (New - we build this)                           │
│   ├── domain_search(query, tlds?)                                  │
│   ├── domain_purchase(domain) → returns x402 payment request       │
│   ├── domain_confirm(purchase_id, tx_hash)                         │
│   └── domain_list() → user's domains                               │
│                                                                     │
│   CLAWD BACKEND SERVICE (Minimal)                                  │
│   ├── Porkbun API integration                                      │
│   ├── Payment verification                                         │
│   ├── User/domain state                                            │
│   └── x402 payment request generation                              │
│                                                                     │
│   EXISTING: clawd-wallet MCP                                       │
│   ├── x402_payment_request(url) → handles payment                  │
│   ├── x402_check_balance()                                         │
│   └── x402_get_address()                                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Foundation (Week 1)

### 1.1 Porkbun API Integration

**Goal:** Prove we can search and register domains via Porkbun API.

**Tasks:**
```
□ Get Porkbun API credentials (API key + secret)
□ Create Porkbun API client library
  □ POST /domain/checkAvailability/{domain}
  □ POST /domain/create/{domain}
  □ POST /dns/create/{domain}
  □ GET /domain/listAll
  □ GET /domain/getDomains/{domain}
□ Test: Search for domain, verify response
□ Test: Register a test domain manually
```

**Porkbun API Notes:**
- Base URL: https://api.porkbun.com/api/json/v3
- Auth: API key + secret in request body
- All requests are POST (even reads)
- Sandbox available for testing

**Sample Code (Python):**
```python
import httpx

class PorkbunClient:
    BASE_URL = "https://api.porkbun.com/api/json/v3"

    def __init__(self, api_key: str, secret: str):
        self.api_key = api_key
        self.secret = secret

    def _auth_body(self) -> dict:
        return {"apikey": self.api_key, "secretapikey": self.secret}

    async def check_availability(self, domain: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/domain/checkAvailability/{domain}",
                json=self._auth_body()
            )
            return resp.json()

    async def register_domain(self, domain: str, years: int = 1) -> dict:
        body = {
            **self._auth_body(),
            "years": years,
            # Registrant info would go here
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/domain/create/{domain}",
                json=body
            )
            return resp.json()
```

**Deliverable:** Working Porkbun client that can search and register.

---

### 1.2 Backend Service (Minimal)

**Goal:** Simple API that handles domain operations and payment flow.

**Tech Stack:**
- Python + FastAPI (fastest to MVP) OR Rust + Axum (if performance critical)
- SQLite for MVP (PostgreSQL for production)
- No auth for MVP (add API keys in Phase 2)

**Endpoints:**
```
POST /search
  Body: {"query": "coolproject", "tlds": ["dev", "io"]}
  Returns: availability + pricing

POST /purchase/initiate
  Body: {"domain": "coolproject.dev", "years": 1}
  Returns: x402 payment request

POST /purchase/confirm
  Body: {"purchase_id": "...", "tx_hash": "0x..."}
  Returns: domain registration result

GET /domains
  Returns: list of user's domains
```

**Sample FastAPI Structure:**
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class SearchRequest(BaseModel):
    query: str
    tlds: list[str] = ["com", "dev", "io", "app", "xyz"]

class PurchaseRequest(BaseModel):
    domain: str
    years: int = 1

class ConfirmRequest(BaseModel):
    purchase_id: str
    tx_hash: str

@app.post("/search")
async def search_domains(req: SearchRequest):
    results = []
    for tld in req.tlds:
        domain = f"{req.query}.{tld}"
        avail = await porkbun.check_availability(domain)
        if avail["status"] == "SUCCESS":
            results.append({
                "domain": domain,
                "available": avail.get("avail", False),
                "price_usdc": get_price(tld),
            })
    return {"results": results}

@app.post("/purchase/initiate")
async def initiate_purchase(req: PurchaseRequest):
    # Verify availability
    # Create pending purchase record
    # Return x402 payment request
    purchase_id = create_purchase(req.domain, req.years)
    return {
        "purchase_id": purchase_id,
        "payment_request": {
            "amount_usdc": get_price(req.domain),
            "recipient": TREASURY_ADDRESS,
            "chain_id": 8453,  # Base
            "memo": f"clawd:{purchase_id}",
        }
    }

@app.post("/purchase/confirm")
async def confirm_purchase(req: ConfirmRequest):
    # Verify payment onchain
    # Register domain via Porkbun
    # Update records
    purchase = get_purchase(req.purchase_id)
    if verify_payment(req.tx_hash, purchase.amount):
        result = await porkbun.register_domain(purchase.domain)
        return {"status": "success", "domain": purchase.domain}
    raise HTTPException(400, "Payment not verified")
```

**Deliverable:** Running backend that can process domain purchases.

---

### 1.3 Payment Verification

**Goal:** Verify USDC payments on Base.

**Approach:**
```python
from web3 import Web3

USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_ABI = [...]  # ERC20 Transfer event ABI

async def verify_payment(tx_hash: str, expected_amount: float, expected_memo: str) -> bool:
    w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
    receipt = w3.eth.get_transaction_receipt(tx_hash)

    if receipt["status"] != 1:
        return False

    # Parse Transfer event
    for log in receipt["logs"]:
        if log["address"].lower() == USDC_BASE.lower():
            # Decode and verify amount + recipient
            # Check memo in transaction data
            pass

    return True
```

**Deliverable:** Function that verifies USDC payment matches expected amount.

---

## Phase 2: MCP Integration (Week 2)

### 2.1 Clawd Domain MCP Server

**Goal:** MCP server that Claude Code can use for domain operations.

**Tools to expose:**
```typescript
// Tool definitions for MCP
const tools = [
  {
    name: "clawd_domain_search",
    description: "Search for available domain names",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Domain name to search (without TLD)" },
        tlds: { type: "array", items: { type: "string" }, description: "TLDs to check" }
      },
      required: ["query"]
    }
  },
  {
    name: "clawd_domain_purchase",
    description: "Initiate domain purchase. Returns payment details for x402.",
    inputSchema: {
      type: "object",
      properties: {
        domain: { type: "string", description: "Full domain name (e.g., example.dev)" },
        years: { type: "number", description: "Registration years", default: 1 }
      },
      required: ["domain"]
    }
  },
  {
    name: "clawd_domain_confirm",
    description: "Confirm domain purchase after payment",
    inputSchema: {
      type: "object",
      properties: {
        purchase_id: { type: "string" },
        tx_hash: { type: "string" }
      },
      required: ["purchase_id", "tx_hash"]
    }
  },
  {
    name: "clawd_domain_list",
    description: "List user's registered domains",
    inputSchema: { type: "object", properties: {} }
  }
];
```

**MCP Server Structure:**
```typescript
// Using @modelcontextprotocol/sdk
import { Server } from "@modelcontextprotocol/sdk/server";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio";

const server = new Server({
  name: "clawd-domains",
  version: "1.0.0"
}, {
  capabilities: { tools: {} }
});

server.setRequestHandler("tools/list", async () => ({
  tools: tools
}));

server.setRequestHandler("tools/call", async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "clawd_domain_search":
      const results = await fetch(`${BACKEND_URL}/search`, {
        method: "POST",
        body: JSON.stringify(args)
      }).then(r => r.json());
      return { content: [{ type: "text", text: JSON.stringify(results, null, 2) }] };

    case "clawd_domain_purchase":
      // Returns x402 payment request
      const purchase = await fetch(`${BACKEND_URL}/purchase/initiate`, {
        method: "POST",
        body: JSON.stringify(args)
      }).then(r => r.json());
      return { content: [{ type: "text", text: JSON.stringify(purchase, null, 2) }] };

    // ... other handlers
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

**Deliverable:** MCP server that Claude Code can discover and use.

---

### 2.2 Claude Code Integration

**Goal:** Add MCP server to Claude Code config.

**~/.claude.json addition:**
```json
{
  "mcpServers": {
    "clawd-domains": {
      "command": "node",
      "args": ["/path/to/clawd-domain-mcp/dist/index.js"],
      "env": {
        "CLAWD_BACKEND_URL": "http://localhost:8000"
      }
    }
  }
}
```

**Deliverable:** Claude Code can call clawd domain tools.

---

### 2.3 Payment Flow Integration

**Goal:** Seamless flow from domain selection to payment to confirmation.

**Flow:**
```
1. User: "I want to buy coolproject.dev"

2. Claude calls clawd_domain_search("coolproject", ["dev"])
   → Returns: available, $14.99 USDC

3. Claude calls clawd_domain_purchase("coolproject.dev")
   → Returns: {purchase_id, payment_request: {amount: 14.99, recipient: 0x...}}

4. Claude calls x402_payment_request with payment details
   → User confirms in wallet
   → Returns: {tx_hash: "0x..."}

5. Claude calls clawd_domain_confirm(purchase_id, tx_hash)
   → Backend verifies payment
   → Backend registers domain via Porkbun
   → Returns: {status: success, domain: "coolproject.dev", expires: "2027-01-28"}

6. Claude: "Done! coolproject.dev is registered and ready."
```

**Deliverable:** Complete purchase flow working in Claude Code.

---

## Phase 3: Polish & Demo (Week 3)

### 3.1 Error Handling

```python
class DomainError(Exception):
    pass

class DomainUnavailableError(DomainError):
    pass

class PaymentFailedError(DomainError):
    pass

class RegistrationFailedError(DomainError):
    pass

# In API handlers:
@app.post("/purchase/confirm")
async def confirm_purchase(req: ConfirmRequest):
    try:
        purchase = get_purchase(req.purchase_id)
        if not purchase:
            raise HTTPException(404, "Purchase not found")

        if not await verify_payment(req.tx_hash, purchase.amount):
            raise PaymentFailedError("Payment verification failed")

        result = await porkbun.register_domain(purchase.domain)
        if result["status"] != "SUCCESS":
            # CRITICAL: Payment received but registration failed
            # Log for manual resolution, notify user
            await alert_ops_team(purchase, req.tx_hash, result)
            raise RegistrationFailedError(
                "Domain registration failed. Your payment has been recorded. "
                "Our team will resolve this within 24 hours or issue a refund."
            )

        return {"status": "success", "domain": purchase.domain}

    except Exception as e:
        # Sanitize error for response
        return {"status": "error", "message": safe_error_message(e)}
```

### 3.2 Demo Script

**Scenario:** Developer building a new project wants a domain.

```markdown
## Demo Flow

### Setup
- Claude Code running with clawd-domains MCP
- clawd-wallet configured with USDC balance
- Backend running locally or deployed

### Script

Developer: "I'm building a task management app called 'taskflow'.
Can you help me find and register a domain for it?"

Claude:
1. Searches for "taskflow" across popular TLDs
2. Presents options with pricing
3. Asks which domain to purchase

Developer: "Let's go with taskflow.dev"

Claude:
1. Initiates purchase
2. Shows payment request
3. Asks for payment confirmation

Developer: [Confirms payment in wallet]

Claude:
1. Confirms payment received
2. Registers domain
3. Shows confirmation with next steps

Claude: "taskflow.dev is now yours! Here's what you can do next:
- Configure DNS for Vercel: `clawd dns taskflow.dev --vercel`
- View your domain: `clawd info taskflow.dev`"
```

### 3.3 Video Recording

- Screen recording of full demo
- Clean terminal, good font size
- Narration or captions
- Post to Twitter/YouTube

---

## Technical Decisions

### Language Choice

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Python** | Fast iteration, team familiarity, great libs | Slower runtime | ✅ MVP |
| **Rust** | Performance, type safety | Slower development | Production |
| **TypeScript** | MCP SDK native, full-stack | Less performant | Alternative |

**Decision:** Python for backend, TypeScript for MCP server.

### Database

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **SQLite** | Zero setup, portable | Single writer | ✅ MVP |
| **PostgreSQL** | Robust, scalable | Setup overhead | Production |

**Decision:** SQLite for MVP, migrate to Postgres before launch.

### Hosting (MVP)

| Component | Option | Cost |
|-----------|--------|------|
| Backend | Railway / Render | ~$5/mo |
| MCP Server | Local (user machine) | $0 |
| Database | SQLite (Railway) | Included |

---

## File Structure

```
clawd-domain-marketplace/
├── PRD-v2.md                    # This document
├── BUILD-PLAN.md                # This file
│
├── backend/                     # Python FastAPI backend
│   ├── pyproject.toml
│   ├── src/
│   │   ├── main.py              # FastAPI app
│   │   ├── porkbun.py           # Porkbun API client
│   │   ├── payments.py          # Payment verification
│   │   ├── models.py            # SQLAlchemy models
│   │   └── config.py            # Settings
│   └── tests/
│
├── mcp-server/                  # TypeScript MCP server
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       └── index.ts             # MCP server
│
└── scripts/
    ├── setup.sh                 # Dev setup
    └── demo.sh                  # Demo helper
```

---

## Milestones

| Milestone | Target | Success Criteria |
|-----------|--------|------------------|
| M1: Porkbun Integration | Week 1, Day 3 | Can search and register via API |
| M2: Backend Running | Week 1, Day 5 | All endpoints working locally |
| M3: MCP Server | Week 2, Day 2 | Claude Code can call tools |
| M4: Payment Flow | Week 2, Day 4 | End-to-end payment works |
| M5: Demo Ready | Week 3 | Polished demo recording |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Porkbun API issues | Test thoroughly in sandbox first |
| Payment verification complexity | Start with simple polling, add webhooks later |
| MCP integration issues | Test with simple tools first |
| Demo fails live | Record backup demo, have fallback domain ready |

---

## Next Steps

1. **Today:** Get Porkbun API credentials
2. **Tomorrow:** Build and test Porkbun client
3. **Day 3:** Basic backend with search endpoint
4. **Day 4:** Purchase flow backend
5. **Day 5:** Payment verification
6. **Week 2:** MCP server + integration
7. **Week 3:** Polish + demo

---

## Commands to Get Started

```bash
# Create project structure
mkdir -p clawd-domain-marketplace/{backend/src,mcp-server/src,scripts}
cd clawd-domain-marketplace

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn httpx sqlalchemy python-dotenv web3

# Create initial files
touch src/{main,porkbun,payments,models,config}.py

# MCP server setup
cd ../mcp-server
npm init -y
npm install @modelcontextprotocol/sdk typescript
npx tsc --init

# Run backend
cd ../backend
uvicorn src.main:app --reload

# Run MCP server (after building)
cd ../mcp-server
npm run build && node dist/index.js
```

---

*Let's build this! Start with the Porkbun integration and work forward.*
