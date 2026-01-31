# Third-Party Setup Guide

This guide is for third parties who want to use the Clawd Domain Marketplace to purchase and manage domains. You don't need a Porkbun account - the marketplace operator handles domain registration. You just need a crypto wallet with USDC on Base.

## Overview

```
Your Wallet (USDC on Base)
        │
        ▼
┌───────────────────┐     x402 Payment     ┌─────────────────────┐
│  clawd-wallet     │ ──────────────────▶  │  Marketplace        │
│  (MCP Server)     │                      │  Backend            │
└───────────────────┘                      └─────────────────────┘
        │                                           │
        │                                           ▼
        │                                  ┌─────────────────────┐
        │                                  │  Porkbun API        │
        │                                  │  (Operator Account) │
        │                                  └─────────────────────┘
        │
        ▼
   You manage your domain via wallet signature
   (DNS, nameservers, transfer auth code)
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
- **USDC on Base** - For domain purchases ($8-15 per domain)
- **ETH on Base** - For gas fees (~0.001 ETH is plenty)

---

## Step 1: Clone and Build clawd-wallet

```bash
# Clone the repository
git clone https://github.com/csmoove530/clawd-wallet.git
cd clawd-wallet

# Install dependencies
npm install

# Build
npm run build
```

---

## Step 2: Configure Claude Code MCP

Add the clawd-wallet MCP server to your Claude Code configuration.

### Find your config file:

| OS | Location |
|----|----------|
| macOS | `~/.claude/claude_desktop_config.json` |
| Linux | `~/.config/claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

### Add this configuration:

```json
{
  "mcpServers": {
    "clawd-wallet": {
      "command": "node",
      "args": ["/FULL/PATH/TO/clawd-wallet/dist/index.js"],
      "env": {
        "CLAWD_BACKEND_URL": "https://marketplace-backend-url.com"
      }
    }
  }
}
```

**Important:**
- Replace `/FULL/PATH/TO/clawd-wallet` with the actual path (use `pwd` in the clawd-wallet directory)
- Replace `https://marketplace-backend-url.com` with the URL provided by the marketplace operator

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

You need two things on Base network:

### 1. ETH for Gas (~0.001 ETH minimum)

Options to get ETH on Base:
- Bridge from Ethereum mainnet via [Base Bridge](https://bridge.base.org)
- Buy on Coinbase and withdraw to Base
- Use a cross-chain bridge like [Across](https://across.to)

### 2. USDC for Domain Purchases

Options to get USDC on Base:
- Bridge USDC from Ethereum via [Base Bridge](https://bridge.base.org)
- Buy USDC on Coinbase and withdraw to Base
- Swap ETH for USDC on [Uniswap](https://app.uniswap.org) (Base network)

**USDC Contract on Base:** `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`

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

### "Insufficient ETH for gas fees"

You need ETH on Base for transaction fees, even when paying with USDC.

```
> Use x402_check_balance
```

If ETH balance is 0, send ~0.001 ETH to your wallet address on Base network.

### "Insufficient balance"

Your USDC balance is too low for the domain price.

### "Invalid recipient address" or "bad address checksum"

The marketplace backend may have a misconfigured treasury address. Contact the marketplace operator.

### "Server rejected payment intent"

The marketplace backend is not responding or rejecting payments. Verify:
1. The `CLAWD_BACKEND_URL` is correct
2. The marketplace backend is running
3. Try again in a few seconds

### MCP Server Not Loading

1. Check the path in your config is absolute (starts with `/`)
2. Ensure `npm run build` completed without errors
3. Restart Claude Code completely
4. Check Claude Code logs for errors

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
