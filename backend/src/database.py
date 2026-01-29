"""Database module for persistent storage of purchases and domain ownership."""
import json
from datetime import datetime
from typing import Optional
from decimal import Decimal

import aiosqlite

from . import config

DB_PATH = config.DATABASE_URL.replace("sqlite:///", "")


async def init_db():
    """Initialize the database with required tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Purchases table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
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
            )
        """)

        # Registered domains table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS domains (
                domain TEXT PRIMARY KEY,
                owner_wallet TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                nameservers TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                registrant TEXT
            )
        """)

        # Create indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_domains_owner ON domains(owner_wallet)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status)")

        await db.commit()


# Purchase operations
async def create_purchase(purchase_data: dict) -> None:
    """Create a new purchase record."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO purchases (id, domain, years, amount, status, created_at, expires_at, registrant)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            purchase_data["id"],
            purchase_data["domain"],
            purchase_data["years"],
            str(purchase_data["amount"]),
            purchase_data["status"],
            purchase_data["created_at"],
            purchase_data["expires_at"],
            json.dumps(purchase_data.get("registrant")) if purchase_data.get("registrant") else None,
        ))
        await db.commit()


async def get_purchase(purchase_id: str) -> Optional[dict]:
    """Get a purchase by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM purchases WHERE id = ?", (purchase_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                data = dict(row)
                data["amount"] = Decimal(data["amount"])
                if data["registrant"]:
                    data["registrant"] = json.loads(data["registrant"])
                return data
            return None


async def update_purchase(purchase_id: str, updates: dict) -> None:
    """Update a purchase record."""
    async with aiosqlite.connect(DB_PATH) as db:
        set_clauses = []
        values = []
        for key, value in updates.items():
            if key == "registrant" and value:
                value = json.dumps(value)
            elif key == "amount":
                value = str(value)
            set_clauses.append(f"{key} = ?")
            values.append(value)
        values.append(purchase_id)

        await db.execute(
            f"UPDATE purchases SET {', '.join(set_clauses)} WHERE id = ?",
            values
        )
        await db.commit()


# Domain operations
async def create_domain(domain_data: dict) -> None:
    """Create a new domain record."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO domains (domain, owner_wallet, expires_at, nameservers, registered_at, registrant)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            domain_data["domain_name"],
            domain_data["owner_wallet"],
            domain_data["expires_at"],
            json.dumps(domain_data["nameservers"]),
            domain_data["registered_at"],
            json.dumps(domain_data.get("registrant")) if domain_data.get("registrant") else None,
        ))
        await db.commit()


async def get_domain(domain: str) -> Optional[dict]:
    """Get a domain by name."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM domains WHERE domain = ?", (domain,)) as cursor:
            row = await cursor.fetchone()
            if row:
                data = dict(row)
                data["domain_name"] = data.pop("domain")
                data["nameservers"] = json.loads(data["nameservers"])
                if data["registrant"]:
                    data["registrant"] = json.loads(data["registrant"])
                return data
            return None


async def get_all_domains() -> list[dict]:
    """Get all registered domains. DEPRECATED - use get_domains_by_wallet instead."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM domains ORDER BY registered_at DESC") as cursor:
            rows = await cursor.fetchall()
            domains = []
            for row in rows:
                data = dict(row)
                data["domain_name"] = data.pop("domain")
                data["nameservers"] = json.loads(data["nameservers"])
                if data["registrant"]:
                    data["registrant"] = json.loads(data["registrant"])
                domains.append(data)
            return domains


async def get_domains_by_wallet(wallet_address: str) -> list[dict]:
    """Get all domains owned by a specific wallet address.

    This ensures users can only see their own domains.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM domains WHERE LOWER(owner_wallet) = LOWER(?) ORDER BY registered_at DESC",
            (wallet_address,)
        ) as cursor:
            rows = await cursor.fetchall()
            domains = []
            for row in rows:
                data = dict(row)
                data["domain_name"] = data.pop("domain")
                data["nameservers"] = json.loads(data["nameservers"])
                if data["registrant"]:
                    data["registrant"] = json.loads(data["registrant"])
                domains.append(data)
            return domains


async def update_domain_nameservers(domain: str, nameservers: list[str]) -> None:
    """Update domain nameservers."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE domains SET nameservers = ? WHERE domain = ?",
            (json.dumps(nameservers), domain)
        )
        await db.commit()


async def verify_domain_owner(domain: str, wallet_address: str) -> bool:
    """Verify the wallet address owns this domain."""
    domain_info = await get_domain(domain)
    if not domain_info:
        return False
    return domain_info.get("owner_wallet", "").lower() == wallet_address.lower()
