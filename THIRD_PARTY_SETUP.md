# Third-Party Setup Guide

*Last Updated: January 31, 2026*

This guide is for third parties who want to use the Clawd Domain Marketplace to purchase and manage domains. You don't need a Porkbun account - the marketplace operator handles domain registration. You just need a crypto wallet with USDC on Base.

> **TL;DR:** Clone repo → Build both MCP servers → Add to Claude config → Fund wallet with USDC → Buy domains!

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Claude Session                      │
│                                                              │
│  ┌─────────────────┐         ┌─────────────────┐            │
│  │  clawd-domains  │         │  clawd-wallet   │            │
│  │  (search, DNS,  │         │  (USDC balance, │            │
│  │   purchase)     │         │   x402 payment) │            │
│  └────────┬────────┘         └────────┬────────┘            │
└───────────┼────────────────────────────┼────────────────────┘
            │                            │
            └──────────┬─────────────────┘
                       ▼
              ┌─────────────────────┐
              │  Marketplace        │
              │  Backend            │
              │  (Operator runs)    │
              └─────────┬───────────┘
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
   ┌─────────────────┐     ┌─────────────────┐
   │  Porkbun API    │     │  Base Network   │
   │  (Registration) │     │  (USDC Payment) │
   └─────────────────┘     └─────────────────┘
```

**Key Points:**
- Domains are registered under the marketplace operator's Porkbun account
- Your wallet address proves ownership in the marketplace database
- You can fully manage DNS, change nameservers, or transfer to another registrar
- Payments are onchain USDC on Base network

---

## Prerequisites

- **Node.js 18+** - [Download](https://nodejs.org/)
- **Claude Code** - For MCP server integration
- **Git** - To clone the repository
- **USDC on Base** - For domain purchases ($5-15 per domain)

> **No ETH required!** The marketplace uses EIP-3009 gasless payments. You only need USDC - the marketplace operator pays gas fees.

---

## Step 1: Clone and Build

The marketplace repository includes everything you need:
- **clawd-domains** (mcp-server/) - for searching and purchasing domains
- **clawd-wallet** (submodule) - for USDC payments

```bash
# Clone the marketplace with submodules
git clone --recurse-submodules https://github.com/noahlevine1717/clawd-domain-marketplace.git
cd clawd-domain-marketplace

# If you already cloned without --recurse-submodules:
# git submodule update --init --recursive

# Build clawd-domains MCP server
cd mcp-server && npm install && npm run build

# Build clawd-wallet MCP server
cd ../clawd-wallet && npm install && npm run build
```

---

## Step 2: Configure Claude Code MCP

Add **both** MCP servers to your Claude Code configuration.

### Find your config file:

| OS | Location |
|----|----------|
| macOS | `~/.claude/claude_desktop_config.json` |
| Linux | `~/.config/claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

### Add this configuration:

First, get the absolute path:
```bash
cd clawd-domain-marketplace && pwd
# Copy the output (e.g., /Users/you/clawd-domain-marketplace)
```

You need **both** MCP servers configured:

```json
{
  "mcpServers": {
    "clawd-domains": {
      "command": "node",
      "args": ["/YOUR/PATH/clawd-domain-marketplace/mcp-server/dist/index.js"],
      "env": {
        "CLAWD_BACKEND_URL": "BACKEND_URL_HERE"
      }
    },
    "clawd-wallet": {
      "command": "node",
      "args": ["/YOUR/PATH/clawd-domain-marketplace/clawd-wallet/dist/index.js"],
      "env": {
        "CLAWD_BACKEND_URL": "BACKEND_URL_HERE"
      }
    }
  }
}
```

**Replace these values:**

| Placeholder | Replace with | Example |
|-------------|--------------|---------|
| `/YOUR/PATH` | Output from `pwd` command above | `/Users/john/clawd-domain-marketplace` |
| `BACKEND_URL_HERE` | URL from marketplace operator | `https://clawd-marketplace.example.com` |

> **Note:** Ask the marketplace operator for the backend URL. Both servers must use the same URL.

### Restart Claude Code

After saving the config, restart Claude Code for the MCP server to load.

---

## Step 3: Initialize Your Wallet

In Claude Code, use the wallet tools:

```
Get your wallet address:
> Use x402_get_address

Check your balance:
> Use x402_check_balance
```

Your wallet is automatically created and stored securely in your system keychain on first use.

---

## Step 4: Fund Your Wallet

You only need USDC on Base network. No ETH required for gas!

### Get USDC on Base

Options to get USDC:
- **Coinbase**: Buy USDC and withdraw directly to Base network
- **Bridge**: Transfer USDC from Ethereum via [Base Bridge](https://bridge.base.org)
- **Swap**: Exchange ETH for USDC on [Uniswap](https://app.uniswap.org) (select Base network)

**USDC Contract on Base:** `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`

### Why No ETH?

The marketplace uses **EIP-3009 gasless payments**. You sign an authorization (free), and the marketplace's relayer executes the transfer and pays gas on your behalf. You only pay the domain price in USDC.

### Verify Funding

```
> Use x402_check_balance
```

You should see your USDC balance. Minimum recommended: $15 USDC for testing.

---

## Step 5: Search for a Domain

```
> Search for domains with name "myproject"
```

This uses the `clawd_domain_search` tool and returns available TLDs with pricing.

Example response:
```
Available domains:
- myproject.xyz - $8.00/year (available)
- myproject.dev - $12.00/year (available)
- myproject.com - $10.00/year (taken)
```

---

## Step 6: Purchase a Domain

```
> Purchase myproject.xyz for 1 year
> My name is [Your Name], email is [your@email.com]
```

This uses `clawd_domain_purchase` and requires:
- **first_name**: Your first name (required for ICANN)
- **last_name**: Your last name (required for ICANN)
- **email**: Your email (required for domain transfer verification)

The purchase flow:
1. Initiates purchase with marketplace
2. You approve the USDC payment
3. Onchain transfer executes
4. Marketplace registers domain
5. Domain is linked to your wallet address

---

## Step 7: Verify Ownership

```
> List my domains
```

This uses `clawd_domain_list` with your wallet address. You should see your newly purchased domain.

---

## Step 8: Manage Your Domain

### View DNS Records

```
> Show DNS records for myproject.xyz
```

### Add DNS Records

```
> Add an A record for myproject.xyz pointing to 192.168.1.1
> Add a CNAME record for www.myproject.xyz pointing to myproject.xyz
```

### Change Nameservers (for external DNS like Cloudflare/Vercel)

```
> Set nameservers for myproject.xyz to ns1.vercel-dns.com and ns2.vercel-dns.com
```

### Get Transfer Auth Code

If you want to transfer the domain to another registrar:

```
> Get the auth code for myproject.xyz
```

This returns the EPP/auth code needed to transfer to GoDaddy, Namecheap, etc.

---

## Troubleshooting

### "Insufficient balance"

Your USDC balance is too low for the domain price.

```
> Use x402_check_balance
```

Add more USDC to your wallet on Base network.

### "Invalid recipient address" or "bad address checksum"

The marketplace backend may have a misconfigured treasury address. Contact the marketplace operator.

### "Server rejected payment intent"

The marketplace backend is not responding or rejecting payments. Verify:
1. The `CLAWD_BACKEND_URL` is correct
2. The marketplace backend is running
3. Try again in a few seconds

### MCP Server Not Loading

1. Check the paths in your config are absolute (start with `/`)
2. Ensure `npm run build` completed without errors for **both** mcp-server/ and clawd-wallet/
3. Restart Claude Code completely
4. Check Claude Code logs for errors
5. Verify both `clawd-domains` and `clawd-wallet` appear in your MCP config

### Domain Not Showing in List

The `clawd_domain_list` tool requires your wallet address. Make sure you're using the same wallet that purchased the domain.

---

## Security Notes

- Your wallet private key is stored in your system's secure keychain
- Never share your private key or seed phrase
- The marketplace operator cannot access your wallet
- You can always transfer domains to another registrar using the auth code
- All payments are onchain and verifiable on [BaseScan](https://basescan.org)

---

## Quick Reference

| Action | Tool | Example |
|--------|------|---------|
| Get wallet address | `x402_get_address` | - |
| Check balance | `x402_check_balance` | - |
| Search domains | `clawd_domain_search` | query: "myproject" |
| Buy domain | `clawd_domain_purchase` | domain: "myproject.xyz" |
| List my domains | `clawd_domain_list` | wallet: "0x..." |
| View DNS | `clawd_dns_list` | domain: "myproject.xyz" |
| Add DNS record | `clawd_dns_create` | type: "A", content: "1.2.3.4" |
| Delete DNS record | `clawd_dns_delete` | record_id: "..." |
| Change nameservers | `clawd_domain_nameservers` | nameservers: ["ns1...", "ns2..."] |
| Get transfer code | `clawd_domain_auth_code` | domain: "myproject.xyz" |

---

## Support

If you encounter issues:
1. Check this troubleshooting guide
2. Verify your wallet has both USDC and ETH on Base
3. Contact the marketplace operator with:
   - Your wallet address (not private key!)
   - The error message
   - What action you were trying to perform
