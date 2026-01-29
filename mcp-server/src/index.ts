#!/usr/bin/env node
/**
 * Clawd Domain Marketplace MCP Server
 *
 * Provides domain search and purchase capabilities via MCP protocol.
 * Works with Claude Code and clawd-wallet for end-to-end domain registration.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";

// Configuration
const BACKEND_URL = process.env.CLAWD_BACKEND_URL || "http://localhost:8402";

// Tool definitions
const TOOLS: Tool[] = [
  {
    name: "clawd_domain_search",
    description:
      "Search for available domain names. Returns availability and pricing for each TLD. " +
      "Use this when a user wants to find a domain for their project.",
    inputSchema: {
      type: "object" as const,
      properties: {
        query: {
          type: "string",
          description:
            "The domain name to search (without TLD), e.g., 'myproject' or 'coolapp'",
        },
        tlds: {
          type: "array",
          items: { type: "string" },
          description:
            "Optional list of TLDs to check. Defaults to [com, dev, io, app, xyz, co, org]",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "clawd_domain_purchase",
    description:
      "Initiate a domain purchase. Returns payment details that should be used with " +
      "the clawd-wallet x402_payment_request tool. After payment, call clawd_domain_confirm.",
    inputSchema: {
      type: "object" as const,
      properties: {
        domain: {
          type: "string",
          description: "Full domain name to purchase, e.g., 'myproject.dev'",
        },
        years: {
          type: "number",
          description: "Number of years to register (1-10). Default is 1.",
        },
      },
      required: ["domain"],
    },
  },
  {
    name: "clawd_domain_confirm",
    description:
      "Confirm a domain purchase after payment has been made. " +
      "Call this with the purchase_id from clawd_domain_purchase and the tx_hash from the payment.",
    inputSchema: {
      type: "object" as const,
      properties: {
        purchase_id: {
          type: "string",
          description: "The purchase_id returned from clawd_domain_purchase",
        },
        tx_hash: {
          type: "string",
          description:
            "The transaction hash from the USDC payment (from x402_payment_request result)",
        },
      },
      required: ["purchase_id", "tx_hash"],
    },
  },
  {
    name: "clawd_domain_list",
    description: "List all domains registered through Clawd Domain Marketplace.",
    inputSchema: {
      type: "object" as const,
      properties: {},
    },
  },
  // DNS Management Tools
  {
    name: "clawd_dns_list",
    description:
      "List all DNS records for a domain. Shows A, AAAA, CNAME, MX, TXT, and other records. " +
      "Requires wallet address that purchased the domain.",
    inputSchema: {
      type: "object" as const,
      properties: {
        domain: {
          type: "string",
          description: "The domain name, e.g., 'myproject.dev'",
        },
        wallet: {
          type: "string",
          description: "Your wallet address (must be the one that purchased the domain)",
        },
      },
      required: ["domain", "wallet"],
    },
  },
  {
    name: "clawd_dns_create",
    description:
      "Create a DNS record for your domain. Use this to point your domain to a server (A record), " +
      "set up a subdomain (CNAME), configure email (MX), or verify ownership (TXT). " +
      "Requires wallet address that purchased the domain.",
    inputSchema: {
      type: "object" as const,
      properties: {
        domain: {
          type: "string",
          description: "The domain name, e.g., 'myproject.dev'",
        },
        wallet: {
          type: "string",
          description: "Your wallet address (must be the one that purchased the domain)",
        },
        record_type: {
          type: "string",
          enum: ["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SRV"],
          description:
            "Type of DNS record: A (IPv4), AAAA (IPv6), CNAME (alias), MX (email), TXT (text/verification)",
        },
        name: {
          type: "string",
          description:
            "Subdomain or record name. Use empty string '' for root domain, 'www' for www subdomain, etc.",
        },
        content: {
          type: "string",
          description:
            "Record value: IP address for A/AAAA, target domain for CNAME, mail server for MX, text for TXT",
        },
        ttl: {
          type: "number",
          description: "Time-to-live in seconds (300-86400). Default is 600.",
        },
      },
      required: ["domain", "wallet", "record_type", "name", "content"],
    },
  },
  {
    name: "clawd_dns_delete",
    description: "Delete a DNS record by its ID. Get record IDs from clawd_dns_list. " +
      "Requires wallet address that purchased the domain.",
    inputSchema: {
      type: "object" as const,
      properties: {
        domain: {
          type: "string",
          description: "The domain name, e.g., 'myproject.dev'",
        },
        wallet: {
          type: "string",
          description: "Your wallet address (must be the one that purchased the domain)",
        },
        record_id: {
          type: "string",
          description: "The ID of the DNS record to delete (from clawd_dns_list)",
        },
      },
      required: ["domain", "wallet", "record_id"],
    },
  },
  {
    name: "clawd_domain_nameservers",
    description:
      "Update nameservers for your domain. Use this to point your domain to external DNS providers " +
      "like Cloudflare, Vercel, or AWS Route53. Requires wallet address that purchased the domain.",
    inputSchema: {
      type: "object" as const,
      properties: {
        domain: {
          type: "string",
          description: "The domain name, e.g., 'myproject.dev'",
        },
        wallet: {
          type: "string",
          description: "Your wallet address (must be the one that purchased the domain)",
        },
        nameservers: {
          type: "array",
          items: { type: "string" },
          description:
            "List of nameservers (2-6). Example: ['ns1.vercel-dns.com', 'ns2.vercel-dns.com']",
        },
      },
      required: ["domain", "wallet", "nameservers"],
    },
  },
  {
    name: "clawd_domain_auth_code",
    description:
      "Get the authorization/EPP code to transfer your domain to another registrar. " +
      "You legally own the domain and can transfer it anytime. Requires wallet address that purchased the domain.",
    inputSchema: {
      type: "object" as const,
      properties: {
        domain: {
          type: "string",
          description: "The domain name to get auth code for, e.g., 'myproject.dev'",
        },
        wallet: {
          type: "string",
          description: "Your wallet address (must be the one that purchased the domain)",
        },
      },
      required: ["domain", "wallet"],
    },
  },
];

// API helper
async function callBackend(
  endpoint: string,
  method: "GET" | "POST" | "DELETE" = "POST",
  body?: unknown
): Promise<unknown> {
  const url = `${BACKEND_URL}${endpoint}`;

  const options: RequestInit = {
    method,
    headers: {
      "Content-Type": "application/json",
    },
  };

  if (body && (method === "POST" || method === "DELETE")) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API error (${response.status}): ${error}`);
  }

  return response.json();
}

// Tool handlers
async function handleDomainSearch(args: {
  query: string;
  tlds?: string[];
}): Promise<string> {
  const result = await callBackend("/search", "POST", {
    query: args.query,
    tlds: args.tlds || ["com", "dev", "io", "app", "xyz", "co", "org"],
  });

  const data = result as {
    query: string;
    results: Array<{
      domain: string;
      available: boolean;
      first_year_price_usdc?: string;
      renewal_price_usdc?: string;
    }>;
    mock_mode: boolean;
  };

  // Format results nicely
  let output = `## Domain Search Results for "${data.query}"\n\n`;

  if (data.mock_mode) {
    output += `⚠️ **Mock Mode** - Using simulated data\n\n`;
  }

  output += `| Domain | Status | First Year | Renewal |\n`;
  output += `|--------|--------|------------|----------|\n`;

  for (const r of data.results) {
    const status = r.available ? "✅ Available" : "❌ Taken";
    const firstYear = r.first_year_price_usdc
      ? `$${r.first_year_price_usdc}`
      : "-";
    const renewal = r.renewal_price_usdc ? `$${r.renewal_price_usdc}` : "-";
    output += `| ${r.domain} | ${status} | ${firstYear} | ${renewal} |\n`;
  }

  output += `\n*Prices in USDC. Renewal price applies from year 2.*`;

  return output;
}

async function handleDomainPurchase(args: {
  domain: string;
  years?: number;
}): Promise<string> {
  const result = await callBackend("/purchase/initiate", "POST", {
    domain: args.domain,
    years: args.years || 1,
  });

  const data = result as {
    purchase_id: string;
    domain: string;
    years: number;
    payment_request: {
      amount_usdc: string;
      recipient: string;
      chain_id: number;
      memo: string;
      expires_at: string;
    };
  };

  // Return structured info for the next step
  let output = `## Purchase Initiated: ${data.domain}\n\n`;
  output += `**Purchase ID:** \`${data.purchase_id}\`\n\n`;
  output += `### Payment Required\n\n`;
  output += `| Field | Value |\n`;
  output += `|-------|-------|\n`;
  output += `| Amount | **${data.payment_request.amount_usdc} USDC** |\n`;
  output += `| Recipient | \`${data.payment_request.recipient}\` |\n`;
  output += `| Network | Base (Chain ID: ${data.payment_request.chain_id}) |\n`;
  output += `| Expires | ${data.payment_request.expires_at} |\n\n`;

  output += `### Next Steps\n\n`;
  output += `1. Use the **clawd-wallet x402_payment_request** tool to make the payment\n`;
  output += `2. After payment, call **clawd_domain_confirm** with:\n`;
  output += `   - \`purchase_id\`: \`${data.purchase_id}\`\n`;
  output += `   - \`tx_hash\`: (from payment result)\n\n`;

  output += `**Payment Details for x402:**\n\`\`\`json\n${JSON.stringify(data.payment_request, null, 2)}\n\`\`\``;

  return output;
}

async function handleDomainConfirm(args: {
  purchase_id: string;
  tx_hash: string;
}): Promise<string> {
  const result = await callBackend("/purchase/confirm", "POST", {
    purchase_id: args.purchase_id,
    tx_hash: args.tx_hash,
  });

  const data = result as {
    status: string;
    domain?: {
      domain_name: string;
      expires_at: string;
      nameservers: string[];
      registered_at: string;
    };
    error?: string;
    mock_mode: boolean;
  };

  if (data.status === "success" || data.status === "already_completed") {
    let output = `## 🎉 Domain Registered Successfully!\n\n`;

    if (data.mock_mode) {
      output += `⚠️ **Mock Mode** - This is a simulated registration\n\n`;
    }

    if (data.domain) {
      output += `| Field | Value |\n`;
      output += `|-------|-------|\n`;
      output += `| Domain | **${data.domain.domain_name}** |\n`;
      output += `| Expires | ${data.domain.expires_at} |\n`;
      output += `| Nameservers | ${data.domain.nameservers.join(", ")} |\n`;
      output += `| Registered | ${data.domain.registered_at} |\n\n`;

      output += `### What's Next?\n\n`;
      output += `- **Configure DNS**: Point your domain to your hosting provider\n`;
      output += `- **Add to Vercel**: \`vercel domains add ${data.domain.domain_name}\`\n`;
      output += `- **Add to Netlify**: Settings → Domain management → Add domain\n`;
    }

    return output;
  } else {
    return `## ❌ Registration Failed\n\n**Status:** ${data.status}\n**Error:** ${data.error || "Unknown error"}\n\nPlease try again or contact support.`;
  }
}

async function handleDomainList(): Promise<string> {
  const result = await callBackend("/domains", "GET");

  const data = result as {
    domains: Array<{
      domain_name: string;
      expires_at: string;
      nameservers: string[];
      registered_at: string;
    }>;
    total: number;
    mock_mode: boolean;
  };

  if (data.total === 0) {
    return "## Your Domains\n\nNo domains registered yet. Use `clawd_domain_search` to find a domain!";
  }

  let output = `## Your Domains (${data.total})\n\n`;

  if (data.mock_mode) {
    output += `⚠️ **Mock Mode** - Using simulated data\n\n`;
  }

  output += `| Domain | Expires | Nameservers |\n`;
  output += `|--------|---------|-------------|\n`;

  for (const d of data.domains) {
    output += `| ${d.domain_name} | ${d.expires_at} | ${d.nameservers[0]} |\n`;
  }

  return output;
}

// DNS Management Handlers
async function handleDnsList(args: { domain: string; wallet: string }): Promise<string> {
  const result = await callBackend(`/domains/${args.domain}/dns?wallet=${args.wallet}`, "GET");

  const data = result as {
    domain: string;
    records: Array<{
      id: string;
      type: string;
      name: string;
      content: string;
      ttl: string;
      prio?: string;
    }>;
  };

  if (!data.records || data.records.length === 0) {
    return `## DNS Records for ${args.domain}\n\nNo DNS records configured. Use \`clawd_dns_create\` to add records.`;
  }

  let output = `## DNS Records for ${args.domain}\n\n`;
  output += `| ID | Type | Name | Content | TTL |\n`;
  output += `|----|------|------|---------|-----|\n`;

  for (const r of data.records) {
    const name = r.name || "@";
    output += `| ${r.id} | ${r.type} | ${name} | ${r.content} | ${r.ttl} |\n`;
  }

  output += `\n*Use record ID with \`clawd_dns_delete\` to remove a record.*`;

  return output;
}

async function handleDnsCreate(args: {
  domain: string;
  wallet: string;
  record_type: string;
  name: string;
  content: string;
  ttl?: number;
}): Promise<string> {
  const result = await callBackend("/domains/dns", "POST", {
    domain: args.domain,
    wallet: args.wallet,
    record_type: args.record_type,
    name: args.name,
    content: args.content,
    ttl: args.ttl || 600,
  });

  const data = result as {
    status: string;
    domain: string;
    record_id: string;
    message: string;
  };

  let output = `## DNS Record Created\n\n`;
  output += `| Field | Value |\n`;
  output += `|-------|-------|\n`;
  output += `| Domain | ${args.domain} |\n`;
  output += `| Type | ${args.record_type} |\n`;
  output += `| Name | ${args.name || "@"} |\n`;
  output += `| Content | ${args.content} |\n`;
  output += `| Record ID | ${data.record_id} |\n\n`;
  output += `${data.message}`;

  return output;
}

async function handleDnsDelete(args: {
  domain: string;
  wallet: string;
  record_id: string;
}): Promise<string> {
  const result = await callBackend("/domains/dns", "DELETE", {
    domain: args.domain,
    wallet: args.wallet,
    record_id: args.record_id,
  });

  const data = result as { status: string; message: string };

  return `## DNS Record Deleted\n\n${data.message}`;
}

async function handleNameservers(args: {
  domain: string;
  wallet: string;
  nameservers: string[];
}): Promise<string> {
  const result = await callBackend("/domains/nameservers", "POST", {
    domain: args.domain,
    wallet: args.wallet,
    nameservers: args.nameservers,
  });

  const data = result as {
    status: string;
    domain: string;
    nameservers: string[];
    message: string;
  };

  let output = `## Nameservers Updated\n\n`;
  output += `**Domain:** ${data.domain}\n\n`;
  output += `**New Nameservers:**\n`;
  for (const ns of data.nameservers) {
    output += `- ${ns}\n`;
  }
  output += `\n${data.message}`;

  return output;
}

async function handleAuthCode(args: { domain: string; wallet: string }): Promise<string> {
  const result = await callBackend(`/domains/${args.domain}/auth-code?wallet=${args.wallet}`, "GET");

  const data = result as {
    domain: string;
    auth_code: string | null;
    message: string;
    manual_required?: boolean;
    instructions?: string[];
    dashboard_url?: string;
  };

  let output = `## Authorization Code for ${data.domain}\n\n`;

  if (data.auth_code) {
    output += `**Auth Code:** \`${data.auth_code}\`\n\n`;
    output += `### How to Transfer\n\n`;
    output += `1. Go to your new registrar (Cloudflare, Namecheap, etc.)\n`;
    output += `2. Start a domain transfer for \`${data.domain}\`\n`;
    output += `3. Enter this auth code when prompted\n`;
    output += `4. Approve the transfer email sent to your registrant email\n`;
    output += `5. Transfer completes in 5-7 days\n\n`;
  } else if (data.manual_required) {
    output += `### Manual Retrieval Required\n\n`;
    output += `The auth code must be retrieved from the Porkbun dashboard:\n\n`;
    if (data.instructions) {
      for (const step of data.instructions) {
        output += `${step}\n`;
      }
    }
    output += `\n**Dashboard URL:** ${data.dashboard_url}\n\n`;
    output += `### After Getting the Code\n\n`;
    output += `1. Go to your new registrar (Cloudflare, Namecheap, etc.)\n`;
    output += `2. Start a domain transfer for \`${data.domain}\`\n`;
    output += `3. Enter the auth code when prompted\n`;
    output += `4. Approve the transfer email sent to your registrant email\n`;
    output += `5. Transfer completes in 5-7 days\n\n`;
  }

  output += `*${data.message}*`;

  return output;
}

// Main server setup
async function main() {
  const server = new Server(
    {
      name: "clawd-domains",
      version: "0.1.0",
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // List tools handler
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: TOOLS,
  }));

  // Call tool handler
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      let result: string;

      switch (name) {
        case "clawd_domain_search":
          result = await handleDomainSearch(
            args as { query: string; tlds?: string[] }
          );
          break;

        case "clawd_domain_purchase":
          result = await handleDomainPurchase(
            args as { domain: string; years?: number }
          );
          break;

        case "clawd_domain_confirm":
          result = await handleDomainConfirm(
            args as { purchase_id: string; tx_hash: string }
          );
          break;

        case "clawd_domain_list":
          result = await handleDomainList();
          break;

        // DNS Management
        case "clawd_dns_list":
          result = await handleDnsList(args as { domain: string; wallet: string });
          break;

        case "clawd_dns_create":
          result = await handleDnsCreate(
            args as {
              domain: string;
              wallet: string;
              record_type: string;
              name: string;
              content: string;
              ttl?: number;
            }
          );
          break;

        case "clawd_dns_delete":
          result = await handleDnsDelete(
            args as { domain: string; wallet: string; record_id: string }
          );
          break;

        case "clawd_domain_nameservers":
          result = await handleNameservers(
            args as { domain: string; wallet: string; nameservers: string[] }
          );
          break;

        case "clawd_domain_auth_code":
          result = await handleAuthCode(args as { domain: string; wallet: string });
          break;

        default:
          throw new Error(`Unknown tool: ${name}`);
      }

      return {
        content: [{ type: "text", text: result }],
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return {
        content: [
          {
            type: "text",
            text: `## Error\n\n${message}\n\nMake sure the Clawd backend is running at ${BACKEND_URL}`,
          },
        ],
        isError: true,
      };
    }
  });

  // Connect via stdio
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error("Clawd Domain MCP server running");
}

main().catch(console.error);
