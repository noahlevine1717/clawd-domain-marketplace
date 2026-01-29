# Clawd Domain Marketplace
## Product Requirements Document v2.0

**Version:** 2.0
**Date:** January 28, 2026
**Classification:** Internal / Strategic
**Owner:** Product Team

---

## Executive Summary

Clawd Domain Marketplace is a domain registration service designed for Claude Code users. It enables developers to search, purchase, and configure domain names without leaving their terminal, using USDC cryptocurrency payments via the x402 payment protocol.

**Key Differentiator:** Zero context-switching. From "I need a domain" to "domain is live" in under 2 minutes, all within the same terminal session.

**MVP Goal:** Demonstrate end-to-end domain purchase via Claude Code using the clawd-wallet MCP tools.

---

## Problem Statement

Developers using Claude Code face workflow interruption when deploying:
1. Leave terminal → open browser → navigate to registrar → create account → search → checkout
2. Payment friction with traditional methods
3. Manual DNS configuration
4. 15-30 minutes of context-switching

**Opportunity:** USDC + x402 protocol enables fully terminal-native domain acquisition.

---

## Architecture Overview

### MVP Architecture (Phase 1)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MVP: CLAUDE CODE NATIVE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    │
│  │   Claude Code   │───▶│  Clawd Service   │───▶│   Porkbun API   │    │
│  │   + MCP Tools   │    │  (x402 enabled)  │    │                 │    │
│  └────────┬────────┘    └────────┬─────────┘    └─────────────────┘    │
│           │                      │                                      │
│           │                      │                                      │
│           ▼                      ▼                                      │
│  ┌─────────────────┐    ┌──────────────────┐                           │
│  │  Clawd Wallet   │───▶│   Base Network   │                           │
│  │  (MCP Server)   │    │   USDC Payment   │                           │
│  └─────────────────┘    └──────────────────┘                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Production Architecture (Phase 2+)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       PRODUCTION: FULL PLATFORM                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐    │
│  │   Claude    │     │   Clawd CLI      │     │   Clawd Backend   │    │
│  │   Code      │────▶│   (Rust)         │────▶│   (Rust + Postgres)│   │
│  │   Terminal  │     └──────────────────┘     └─────────┬─────────┘    │
│  └─────────────┘                                        │              │
│        │                 ┌──────────────────────────────┼──────────┐   │
│        │                 │                              │          │   │
│        ▼                 ▼                              ▼          ▼   │
│  ┌───────────┐   ┌───────────────┐          ┌──────────────┐ ┌──────┐ │
│  │  Clawd    │   │  x402 Payment │          │   Porkbun    │ │ User │ │
│  │  Wallet   │   │  Gateway      │          │   API        │ │  DB  │ │
│  │  MCP      │   └───────┬───────┘          └──────────────┘ └──────┘ │
│  └───────────┘           │                                            │
│                          ▼                                            │
│                  ┌───────────────┐                                    │
│                  │ Base/Ethereum │                                    │
│                  │ USDC          │                                    │
│                  └───────────────┘                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Domain Industry Compliance

### Reseller Model Structure

We operate as a **reseller** under Porkbun's ICANN accreditation:

| Aspect | Our Responsibility | Porkbun's Responsibility |
|--------|-------------------|-------------------------|
| ICANN Compliance | Follow reseller agreement | RAA compliance, data escrow |
| WHOIS/RDAP | Collect accurate registrant data | Publish to RDAP, handle queries |
| Disputes (UDRP) | Notify user, pass through | Handle formal process |
| Transfers | Provide auth codes, unlock domains | Process transfer requests |

### Domain Ownership Model

**Recommended: User as Registrant**
- User's contact info used for WHOIS registration
- Clawd listed as admin/tech contact for operational access
- User retains full ownership and transfer rights
- Clear liability boundaries

### Required ICANN Data Collection

```
Required for domain registration (ICANN mandate):
├── Registrant Name (full legal name)
├── Organization (optional)
├── Email (verified)
├── Phone (E.164 format)
├── Address
│   ├── Street
│   ├── City
│   ├── State/Province
│   ├── Postal Code
│   └── Country (ISO 3166-1 alpha-2)
└── WHOIS Privacy preference
```

---

## Security Architecture

### Threat Model & Mitigations

| Threat | Risk | Mitigation |
|--------|------|------------|
| **SSRF via domain search** | Medium | Validate all URLs, block internal IPs, no user-provided URLs in backend requests |
| **Payment front-running** | Medium | Unique memo per transaction, server-side verification, short expiry windows |
| **API key theft** | High | Encrypted storage (OS keychain), rotatable keys, scoped permissions |
| **DNS hijacking** | High | Email verification for changes, change notifications, optional registry lock |
| **Account takeover** | High | Email + wallet signature verification, MFA for sensitive operations |
| **SQL injection** | High | Parameterized queries only, ORM with prepared statements |
| **Path traversal** | Medium | Sanitize all file paths, no user input in paths |
| **Error info leakage** | Low | Sanitize all error messages, no internal paths/details |

### Input Validation Requirements

```python
# Domain name validation
def validate_domain(domain: str) -> tuple[bool, str]:
    """Validate domain name format."""
    import re

    # Basic format check
    pattern = r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z]{2,})+$'
    if not re.match(pattern, domain.lower()):
        return False, "Invalid domain format"

    # Length check
    if len(domain) > 253:
        return False, "Domain too long"

    # No consecutive hyphens at positions 3-4 (reserved for IDN)
    labels = domain.split('.')
    for label in labels:
        if len(label) > 63:
            return False, "Label too long"
        if label.startswith('-') or label.endswith('-'):
            return False, "Labels cannot start/end with hyphen"

    return True, ""

# TLD whitelist (only supported TLDs)
SUPPORTED_TLDS = {'com', 'net', 'org', 'io', 'dev', 'app', 'co', 'xyz', 'ai'}
```

### Secrets Management

```yaml
# Production: Environment variables only
PORKBUN_API_KEY: ${PORKBUN_API_KEY}
PORKBUN_SECRET: ${PORKBUN_SECRET}
DATABASE_URL: ${DATABASE_URL}
JWT_SECRET: ${JWT_SECRET}

# Development: .env file (gitignored)
# NEVER commit secrets to repository
```

### Error Handling

```python
def safe_error_response(error: Exception) -> dict:
    """Return safe error without internal details."""
    import re

    # Map known errors to safe messages
    error_map = {
        "ConnectionError": "Unable to connect to service",
        "TimeoutError": "Request timed out",
        "ValidationError": str(error),  # These are safe
    }

    error_type = type(error).__name__
    if error_type in error_map:
        return {"error": error_map[error_type]}

    # Generic fallback - never expose internal details
    return {"error": "An unexpected error occurred", "code": "INTERNAL_ERROR"}
```

---

## Domain Lifecycle Management

### Lifecycle States

```
┌──────────┐     ┌─────────────────┐     ┌────────────┐     ┌───────────────┐
│  Active  │────▶│  Grace Period   │────▶│ Redemption │────▶│ Pending Delete│
│          │     │  (0-45 days)    │     │ (~30 days) │     │   (5 days)    │
└──────────┘     └─────────────────┘     └────────────┘     └───────────────┘
     │                   │                      │                    │
     │                   │                      │                    ▼
     │                   │                      │              ┌──────────┐
     │                   ▼                      ▼              │ Released │
     │            Renew at normal        Restore at           └──────────┘
     │               price               premium ($80+)
     │
     ▼
  Renew/Auto-renew
```

### Notification Schedule

| Event | Timing | Priority |
|-------|--------|----------|
| Renewal reminder | 60, 30, 14, 7, 3, 1 days before | Normal → Urgent |
| Renewal success | Immediate | Low |
| Renewal failed | Immediate | Critical |
| Entering grace period | Day of expiry | Critical |
| Entering redemption | Day of transition | Critical |
| Domain released | Day of release | Info |

### Pricing Transparency

**Always show both first-year and renewal pricing:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🔍 Search results for "coolproject"                                    │
│                                                                         │
│  DOMAIN              STATUS      FIRST YEAR    RENEWAL     AVAILABLE    │
│  ─────────────────────────────────────────────────────────────────────  │
│  coolproject.com     ❌ Taken    -             -           -            │
│  coolproject.dev     ✅ Avail    $14.99        $16.99      ✓            │
│  coolproject.io      ✅ Avail    $34.99        $39.99      ✓            │
│  coolproject.app     ✅ Avail    $16.99        $18.99      ✓            │
│  coolproject.xyz     ✅ Avail    $12.99        $14.99      ✓            │
│                                                                         │
│  [i] Prices in USDC. Renewal prices apply from year 2.                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### User Entity

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Primary key |
| email | String(255) | UNIQUE, NOT NULL | User email |
| email_verified | Boolean | DEFAULT false | Verification status |
| full_name | String(255) | NOT NULL | WHOIS registrant name |
| organization | String(255) | NULLABLE | WHOIS organization |
| address_line_1 | String(255) | NOT NULL | Street address |
| address_line_2 | String(255) | NULLABLE | Address line 2 |
| city | String(100) | NOT NULL | City |
| state_province | String(100) | NOT NULL | State/province |
| postal_code | String(20) | NOT NULL | Postal code |
| country_code | String(2) | NOT NULL | ISO 3166-1 alpha-2 |
| phone | String(20) | NOT NULL | E.164 format |
| wallet_addresses | JSONB | DEFAULT '[]' | Associated wallets |
| api_key_hash | String(64) | NOT NULL | Bcrypt hash |
| created_at | Timestamp | DEFAULT NOW() | Creation time |
| updated_at | Timestamp | DEFAULT NOW() | Last update |

### Domain Entity

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Primary key |
| user_id | UUID | FK → users | Owner |
| domain_name | String(253) | UNIQUE, NOT NULL | Full domain |
| tld | String(20) | NOT NULL | Extension |
| registrar_domain_id | String(100) | NOT NULL | Porkbun ID |
| lifecycle_status | Enum | NOT NULL | active/grace/redemption/pending_delete |
| registered_at | Timestamp | NOT NULL | Registration date |
| expires_at | Timestamp | NOT NULL | Expiration date |
| grace_period_ends_at | Timestamp | NULLABLE | Grace period end |
| redemption_ends_at | Timestamp | NULLABLE | Redemption end |
| auto_renew | Boolean | DEFAULT true | Auto-renewal |
| whois_privacy | Boolean | DEFAULT true | WHOIS privacy |
| locked | Boolean | DEFAULT true | Transfer lock |
| dnssec_enabled | Boolean | DEFAULT false | DNSSEC status |
| nameservers | JSONB | NOT NULL | NS records |
| dns_records | JSONB | DEFAULT '[]' | DNS config |
| purchase_price_usdc | Decimal(10,2) | NOT NULL | Initial price |
| renewal_price_usdc | Decimal(10,2) | NOT NULL | Renewal price |

### Transaction Entity

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Primary key |
| user_id | UUID | FK → users | User |
| domain_id | UUID | FK → domains, NULLABLE | Associated domain |
| type | Enum | NOT NULL | purchase/renewal/restore/transfer |
| amount_usdc | Decimal(10,2) | NOT NULL | Amount |
| chain | String(20) | NOT NULL | Blockchain |
| tx_hash | String(66) | UNIQUE | On-chain hash |
| status | Enum | NOT NULL | pending/confirmed/failed |
| memo | String(255) | NOT NULL | Unique payment memo |
| created_at | Timestamp | DEFAULT NOW() | Initiation |
| confirmed_at | Timestamp | NULLABLE | Confirmation |
| registrar_tx_id | String(100) | NULLABLE | Porkbun reference |

**Indexes:**
```sql
CREATE INDEX idx_domains_user_id ON domains(user_id);
CREATE INDEX idx_domains_expires_at ON domains(expires_at);
CREATE INDEX idx_domains_lifecycle_status ON domains(lifecycle_status);
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_status ON transactions(status);
CREATE INDEX idx_transactions_tx_hash ON transactions(tx_hash);
```

---

## API Specification

### Authentication

All requests require Bearer token:
```
Authorization: Bearer <api_key>
```

Rate limits:
| Endpoint Category | Limit | Window |
|-------------------|-------|--------|
| Search | 60 req | 1 min |
| Purchase | 10 req | 1 min |
| DNS Updates | 30 req | 1 min |
| Account | 20 req | 1 min |

### Endpoints

#### POST /v1/auth/signup
Create account.

**Request:**
```json
{
  "email": "dev@example.com",
  "full_name": "Jane Developer",
  "organization": "Acme Labs",
  "address": {
    "line_1": "123 Main St",
    "line_2": "Suite 100",
    "city": "San Francisco",
    "state_province": "CA",
    "postal_code": "94102",
    "country_code": "US"
  },
  "phone": "+15551234567"
}
```

**Response (201):**
```json
{
  "user_id": "uuid",
  "api_key": "clwd_live_xxx",
  "message": "Verification email sent"
}
```

#### GET /v1/domains/search
Search availability.

**Query params:** `q` (required), `tlds` (optional, comma-separated)

**Response (200):**
```json
{
  "query": "coolproject",
  "results": [
    {
      "domain": "coolproject.dev",
      "available": true,
      "first_year_price_usdc": "14.99",
      "renewal_price_usdc": "16.99",
      "premium": false
    },
    {
      "domain": "cool.dev",
      "available": true,
      "first_year_price_usdc": "2499.00",
      "renewal_price_usdc": "16.99",
      "premium": true,
      "premium_type": "registry"
    }
  ],
  "cached": false,
  "expires_at": "2026-01-28T12:05:00Z"
}
```

#### POST /v1/domains/purchase
Initiate purchase (returns x402 payment request).

**Request:**
```json
{
  "domain": "coolproject.dev",
  "years": 1,
  "whois_privacy": true
}
```

**Response (402 Payment Required):**
```json
{
  "purchase_id": "uuid",
  "payment_request": {
    "amount_usdc": "14.99",
    "recipient": "0x...",
    "chain_id": 8453,
    "memo": "clawd:purchase:coolproject.dev:uuid",
    "expires_at": "2026-01-28T12:10:00Z"
  },
  "domain": "coolproject.dev",
  "years": 1
}
```

#### POST /v1/domains/purchase/{purchase_id}/confirm
Confirm payment.

**Request:**
```json
{
  "tx_hash": "0x..."
}
```

**Response (200):**
```json
{
  "status": "confirmed",
  "domain": {
    "domain_name": "coolproject.dev",
    "expires_at": "2027-01-28",
    "nameservers": ["ns1.porkbun.com", "ns2.porkbun.com"]
  },
  "receipt_url": "/v1/receipts/uuid"
}
```

#### GET /v1/domains
List user's domains.

**Response (200):**
```json
{
  "domains": [
    {
      "domain_name": "coolproject.dev",
      "lifecycle_status": "active",
      "expires_at": "2027-01-28",
      "auto_renew": true,
      "days_until_expiry": 365
    }
  ],
  "total": 1
}
```

#### GET /v1/domains/{domain}/auth-code
Get transfer auth code (unlocks domain if locked).

**Response (200):**
```json
{
  "domain": "coolproject.dev",
  "auth_code": "abc123xyz",
  "valid_until": "2026-02-28T00:00:00Z",
  "transfer_lock_removed": true,
  "note": "60-day lock from registration still applies until 2026-03-28"
}
```

#### PUT /v1/domains/{domain}/dns
Update DNS records.

**Request:**
```json
{
  "records": [
    {"type": "A", "name": "@", "value": "76.76.21.21", "ttl": 300},
    {"type": "CNAME", "name": "www", "value": "cname.vercel-dns.com", "ttl": 300}
  ]
}
```

#### POST /v1/domains/{domain}/dns/preset
Apply DNS preset.

**Request:**
```json
{
  "preset": "vercel"
}
```

**Available presets:** `vercel`, `netlify`, `railway`, `cloudflare-pages`, `github-pages`

---

## MVP Scope

### In Scope (MVP)

| Feature | Description | Priority |
|---------|-------------|----------|
| Domain search | Check availability across TLDs | P0 |
| USDC payment | x402 payment via clawd-wallet | P0 |
| Domain purchase | Register via Porkbun API | P0 |
| Basic DNS | A/AAAA/CNAME records | P0 |
| User accounts | ICANN-compliant registration | P0 |
| Transfer-out | Auth code + unlock | P1 |
| Auto-renewal | Basic renewal flow | P1 |
| DNS presets | Vercel/Netlify configs | P1 |

### Out of Scope (MVP)

| Feature | Rationale | Future Phase |
|---------|-----------|--------------|
| Transfer-in | Complex, low initial demand | Phase 2 |
| Premium domains | Requires pricing integration | Phase 2 |
| Multiple registrars | Start with one to validate | Phase 3 |
| DNSSEC management | Add after core stable | Phase 2 |
| Standalone CLI | Start with MCP integration | Phase 2 |
| Fiat payments | Adds compliance complexity | Phase 3 |

---

## Success Metrics

### MVP Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| End-to-end purchase | Works | Demo successful |
| Time to purchase | < 2 min | From search to confirmed |
| Payment success rate | 100% | Test transactions |

### Production KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first purchase | < 5 min | Signup to purchase |
| Search-to-purchase rate | > 15% | Conversion |
| Payment success rate | > 98% | Transactions |
| Renewal success rate | > 95% | Auto-renewals |
| Transfer-out completion | < 24 hrs | Request to complete |

---

## Pricing

### Margin Structure

| TLD | Porkbun Cost | First Year | Renewal | Margin |
|-----|--------------|------------|---------|--------|
| .com | $9.73/$10.18 | $12.99 | $14.99 | $3.26/$4.81 |
| .dev | $12.00 | $14.99 | $16.99 | $2.99/$4.99 |
| .io | $29.88 | $34.99 | $39.99 | $5.11/$10.11 |
| .app | $14.00 | $16.99 | $18.99 | $2.99/$4.99 |
| .xyz | $9.06 | $12.99 | $14.99 | $3.93/$5.93 |
| .ai | $70.00 | $79.99 | $89.99 | $9.99/$19.99 |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Porkbun API changes | Medium | High | Abstract registrar layer, maintain relationship |
| Payment verification delay | Medium | Medium | Polling + webhooks, clear status UI |
| Domain registration fails after payment | Low | Critical | Escrow pattern: hold payment until confirmed |
| User loses domain (missed renewal) | Medium | High | Aggressive notifications, auto-renew default |
| UDRP claim | Low | Medium | Clear ToS, pass-through to Porkbun |
| Regulatory scrutiny | Low | High | Legal review, compliance monitoring |

---

## Appendix A: CLI Command Reference (Future)

```
CLAWD DOMAIN MARKETPLACE - CLI REFERENCE

ACCOUNT
  clawd signup                  Create account
  clawd login                   Authenticate
  clawd account                 View account

DOMAINS
  clawd search <query>          Search domains
    --tld <ext>                 Filter TLDs
    --max-price <n>             Price filter

  clawd buy <domain>            Purchase domain
    --years <n>                 Registration years

  clawd list                    List your domains
  clawd info <domain>           Domain details
  clawd renew <domain>          Renew domain
  clawd restore <domain>        Restore from redemption

TRANSFERS
  clawd unlock <domain>         Remove transfer lock
  clawd auth-code <domain>      Get auth code
  clawd lock <domain>           Enable transfer lock

DNS
  clawd dns <domain>            Show DNS records
  clawd dns <domain> add        Add record
  clawd dns <domain> remove     Remove record
  clawd dns <domain> --vercel   Apply Vercel preset
  clawd dns <domain> --netlify  Apply Netlify preset

SECURITY
  clawd dnssec <domain> enable  Enable DNSSEC
  clawd privacy <domain> on     Enable WHOIS privacy
  clawd whois <domain>          View RDAP data
```

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **EPP** | Extensible Provisioning Protocol - registrar-registry communication |
| **RAA** | Registrar Accreditation Agreement - ICANN-registrar contract |
| **RDAP** | Registration Data Access Protocol - modern WHOIS replacement |
| **RGP** | Redemption Grace Period - expensive restoration window |
| **UDRP** | Uniform Domain-Name Dispute-Resolution Policy |
| **Auth Code** | Secret code to authorize domain transfer |
| **DNSSEC** | DNS Security Extensions - cryptographic signing |
| **x402** | HTTP payment protocol using 402 status |
| **USDC** | USD Coin stablecoin |
| **Base** | Coinbase's L2 blockchain |

---

*Document Version 2.0 - Incorporating domain industry expertise and security requirements*
