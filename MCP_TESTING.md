# MCP Testing Guide

This guide provides step-by-step tests for users interacting with Clawd Domain Marketplace through **Claude Desktop** or **Claude Code** using the MCP tools.

## Prerequisites

### 1. MCP Servers Configured

Verify both MCP servers are in your Claude configuration:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/claude-desktop/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "clawd-domains": {
      "command": "node",
      "args": ["/path/to/clawd-domain-marketplace/mcp-server/dist/index.js"],
      "env": {
        "CLAWD_BACKEND_URL": "http://localhost:8402"
      }
    },
    "clawd-wallet": {
      "command": "node",
      "args": ["/path/to/clawd-wallet/dist/mcp-server/index.js"]
    }
  }
}
```

### 2. Backend Running

```bash
cd clawd-domain-marketplace/backend
source venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8402
```

### 3. Wallet Funded (for payment tests)

- USDC on Base network (minimum $5 for .xyz domain)
- ETH on Base network (minimum 0.001 ETH for gas)

---

## Test Suite for MCP Users

Copy and paste these prompts into Claude to test each feature.

---

### Test 1: Wallet Balance Check

**Prompt:**
```
What's my wallet balance?
```

**Expected:** Claude uses `x402_check_balance` and shows:
- Wallet address
- USDC balance
- Network (Base)

**Example response:**
```
Your wallet balance:
- Address: 0x10c4B8A12604a79b9f5534Cfdd763c3182C8EFd4
- Balance: 8.02 USDC
- Network: Base mainnet
```

**If it fails:**
- Verify clawd-wallet MCP server is configured
- Check wallet was initialized (`clawd-wallet init`)

---

### Test 2: Get Wallet Address

**Prompt:**
```
What's my wallet address for receiving funds?
```

**Expected:** Claude uses `x402_get_address` and shows:
- Your wallet address
- Instructions for funding

---

### Test 3: Domain Search

**Prompt:**
```
Search for available domains with "myproject"
```

**Expected:** Claude uses `clawd_domain_search` and shows:
- Table of available domains
- Pricing (first year and renewal)
- Multiple TLDs (.com, .dev, .xyz, etc.)

**Example response:**
```
Domain Search Results for "myproject"

| Domain | Status | First Year | Renewal |
|--------|--------|------------|---------|
| myproject.xyz | ✅ Available | $4.54 | $15.98 |
| myproject.dev | ✅ Available | $14.99 | $16.99 |
| myproject.com | ❌ Taken | - | - |
```

**If it fails:**
- Verify backend is running on port 8402
- Check CLAWD_BACKEND_URL in MCP config

---

### Test 4: Domain Search with Specific TLDs

**Prompt:**
```
Check if "coolstartup" is available as .ai and .io domains
```

**Expected:** Claude uses `clawd_domain_search` with specific TLDs:
```
| Domain | Status | First Year |
|--------|--------|------------|
| coolstartup.ai | ✅ Available | $79.99 |
| coolstartup.io | ✅ Available | $34.99 |
```

---

### Test 5: Purchase Domain (Full Flow)

**Prompt:**
```
I want to buy testdomain123.xyz. My name is John Doe and my email is john@example.com
```

**Expected sequence:**
1. Claude uses `clawd_domain_purchase` to initiate
2. Claude uses `x402_payment_request` to pay
3. Shows success with:
   - Domain registered
   - Transaction hash
   - Expiration date
   - Nameservers

**Example response:**
```
Domain testdomain123.xyz registered successfully!

- Transaction: 0x74483d5a58f5c7b42c79998b478670133fbad2170881276c2951aa36607008aa
- Expires: 2027-01-30
- Nameservers: ns1.porkbun.com, ns2.porkbun.com
- Owner: 0x10c4B8A12604a79b9f5534Cfdd763c3182C8EFd4
```

**If it fails:**
- Check wallet has enough USDC (need ~$5 for .xyz)
- Check wallet has ETH for gas (need ~0.001 ETH)
- Verify domain is actually available

---

### Test 6: List My Domains

**Prompt:**
```
Show me all the domains I own
```

**Expected:** Claude uses `clawd_domain_list` and shows:
- All domains owned by your wallet
- Expiration dates
- Nameservers

**Example response:**
```
Your Domains (3)

| Domain | Expires | Nameservers |
|--------|---------|-------------|
| mysite.xyz | 2027-01-30 | ns1.porkbun.com |
| coolapp.dev | 2027-02-15 | ns1.porkbun.com |
| project.io | 2026-12-01 | ns1.porkbun.com |
```

---

### Test 7: List DNS Records

**Prompt:**
```
Show me the DNS records for mysite.xyz
```

**Expected:** Claude uses `clawd_dns_list` and shows:
- All DNS records (A, AAAA, CNAME, MX, TXT, NS)
- Record IDs for management

**Example response:**
```
DNS Records for mysite.xyz

| ID | Type | Name | Content | TTL |
|----|------|------|---------|-----|
| 12345 | A | mysite.xyz | 192.168.1.1 | 600 |
| 12346 | NS | mysite.xyz | ns1.porkbun.com | 86400 |
```

---

### Test 8: Create A Record

**Prompt:**
```
Point mysite.xyz to IP address 203.0.113.50
```

**Expected:** Claude uses `clawd_dns_create` with:
- record_type: A
- name: "" (root domain)
- content: 203.0.113.50

**Example response:**
```
DNS Record Created

| Field | Value |
|-------|-------|
| Domain | mysite.xyz |
| Type | A |
| Name | @ |
| Content | 203.0.113.50 |
| Record ID | 519371782 |
```

---

### Test 9: Create Subdomain

**Prompt:**
```
Create a CNAME record pointing www.mysite.xyz to mysite.xyz
```

**Expected:** Claude uses `clawd_dns_create` with:
- record_type: CNAME
- name: "www"
- content: "mysite.xyz"

---

### Test 10: Create TXT Record (SPF)

**Prompt:**
```
Add an SPF record to mysite.xyz for Google Workspace email
```

**Expected:** Claude uses `clawd_dns_create` with:
- record_type: TXT
- content: "v=spf1 include:_spf.google.com ~all"

---

### Test 11: Create MX Records

**Prompt:**
```
Set up Google Workspace email for mysite.xyz
```

**Expected:** Claude creates multiple MX records:
- ASPMX.L.GOOGLE.COM (priority 1)
- ALT1.ASPMX.L.GOOGLE.COM (priority 5)
- etc.

---

### Test 12: Delete DNS Record

**Prompt:**
```
Delete the A record with ID 519371782 from mysite.xyz
```

**Expected:** Claude uses `clawd_dns_delete` and confirms deletion.

---

### Test 13: Update Nameservers

**Prompt:**
```
Point mysite.xyz to Cloudflare nameservers: ns1.cloudflare.com and ns2.cloudflare.com
```

**Expected:** Claude uses `clawd_domain_nameservers` to update.

---

### Test 14: Get Domain Transfer Code

**Prompt:**
```
I want to transfer mysite.xyz to another registrar. Get me the auth code.
```

**Expected:** Claude uses `clawd_domain_auth_code` and provides:
- EPP/Auth code for transfer
- Instructions for using it

---

### Test 15: Transaction History

**Prompt:**
```
Show me my recent payment transactions
```

**Expected:** Claude uses `x402_transaction_history` and shows:
- Recent payments
- Amounts, dates, services
- Transaction hashes

---

## Multi-Step Workflow Tests

### Test A: Complete Domain Setup

**Prompt:**
```
I want to set up a new website. Please:
1. Search for available domains with "awesomeproject"
2. Buy awesomeproject.xyz if available (name: Jane Smith, email: jane@email.com)
3. Point it to my server at 198.51.100.25
4. Add a www subdomain pointing to the same IP
```

**Expected:** Claude performs all steps in sequence, confirming each action.

---

### Test B: Email Setup

**Prompt:**
```
Set up mysite.xyz for Google Workspace email with all the necessary DNS records
```

**Expected:** Claude creates:
- MX records for Google
- SPF TXT record
- Optionally DKIM if provided

---

### Test C: Domain Audit

**Prompt:**
```
Give me a complete audit of mysite.xyz - show me all DNS records and check if anything looks misconfigured
```

**Expected:** Claude:
- Lists all DNS records
- Identifies potential issues
- Suggests improvements

---

## Error Handling Tests

### Test E1: Insufficient Funds

**Prompt:**
```
Buy expensivedomaintest.ai
```

**Expected (if wallet has < $80):**
- Clear error about insufficient USDC
- Shows current balance vs required amount

---

### Test E2: Domain Already Taken

**Prompt:**
```
Buy google.com
```

**Expected:**
- Clear message that domain is not available
- Suggestion to search for alternatives

---

### Test E3: Invalid Domain

**Prompt:**
```
Buy -invalid-.xyz
```

**Expected:**
- Error about invalid domain format

---

### Test E4: Unauthorized DNS Access

**Prompt:**
```
Show DNS records for a domain I don't own: randomdomain12345.xyz
```

**Expected:**
- Error: "You don't own this domain"
- Only wallet owner can manage DNS

---

## Checklist

Use this checklist to verify your MCP integration:

### Wallet Tools (clawd-wallet)
- [ ] `x402_check_balance` - Shows USDC balance
- [ ] `x402_get_address` - Shows wallet address
- [ ] `x402_transaction_history` - Shows past payments
- [ ] `x402_payment_request` - Can make payments

### Domain Tools (clawd-domains)
- [ ] `clawd_domain_search` - Finds available domains
- [ ] `clawd_domain_purchase` - Initiates purchase
- [ ] `clawd_domain_list` - Lists owned domains
- [ ] `clawd_dns_list` - Shows DNS records
- [ ] `clawd_dns_create` - Creates records
- [ ] `clawd_dns_delete` - Deletes records
- [ ] `clawd_domain_nameservers` - Updates nameservers
- [ ] `clawd_domain_auth_code` - Gets transfer code

---

## Troubleshooting

### Tools not appearing in Claude

1. Restart Claude Desktop/Code after config changes
2. Verify JSON syntax in config file
3. Check MCP server paths are absolute
4. Look for errors in Claude's developer console

### "API error (500)"

1. Check backend is running: `curl http://localhost:8402/health`
2. Check backend logs: `tail -f /tmp/backend.log`
3. Verify CLAWD_BACKEND_URL in MCP config

### Payment fails with "insufficient funds"

Two possible causes:
1. **Not enough USDC** - Check balance, need ~$5 for .xyz
2. **Not enough ETH for gas** - Need ~0.001 ETH on Base

### "bad address checksum"

Treasury address has wrong casing. Fix in backend `.env`:
```bash
# Get correct checksum
node -e "const{ethers}=require('ethers');console.log(ethers.getAddress('YOUR_ADDRESS'.toLowerCase()))"
```

### DNS changes not appearing

- DNS propagation takes time (up to 24-48 hours globally)
- Check immediately at: https://dnschecker.org
- TTL affects how fast changes propagate

---

## Quick Reference

| Task | What to Say |
|------|-------------|
| Check balance | "What's my wallet balance?" |
| Find domain | "Search for domains with 'myname'" |
| Buy domain | "Buy myname.xyz, name: John Doe, email: john@example.com" |
| List domains | "Show my domains" |
| Point to IP | "Point mysite.xyz to 192.168.1.1" |
| Add subdomain | "Create www.mysite.xyz pointing to mysite.xyz" |
| Setup email | "Add Google Workspace MX records to mysite.xyz" |
| Delete record | "Delete DNS record 12345 from mysite.xyz" |
| Transfer domain | "Get auth code for mysite.xyz" |

---

## Support

If tests fail after following this guide:

1. Check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for detailed solutions
2. Review backend logs for specific errors
3. Open an issue on GitHub with:
   - Test that failed
   - Error message
   - Backend logs
   - Your environment (OS, Node version)
