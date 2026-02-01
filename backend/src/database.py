"""Database module for persistent storage of purchases and domain ownership."""
import json
from datetime import datetime
from typing import Optional
from decimal import Decimal
import os

from . import config

# Determine database type from URL
DATABASE_URL = config.DATABASE_URL
IS_POSTGRES = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")

if IS_POSTGRES:
    import asyncpg
    _pool = None
else:
    import aiosqlite
    DB_PATH = DATABASE_URL.replace("sqlite:///", "")


async def init_db():
    """Initialize the database with required tables."""
    if IS_POSTGRES:
        global _pool
        _pool = await asyncpg.create_pool(DATABASE_URL)
        async with _pool.acquire() as conn:
            # Purchases table
            await conn.execute("""
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
            await conn.execute("""
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
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_domains_owner ON domains(owner_wallet)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status)")
    else:
        async with aiosqlite.connect(DB_PATH) as db:
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

            await db.execute("CREATE INDEX IF NOT EXISTS idx_domains_owner ON domains(owner_wallet)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status)")
            await db.commit()


# Purchase operations
async def create_purchase(purchase_data: dict) -> None:
    """Create a new purchase record."""
    registrant_json = json.dumps(purchase_data.get("registrant")) if purchase_data.get("registrant") else None

    if IS_POSTGRES:
        async with _pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO purchases (id, domain, years, amount, status, created_at, expires_at, registrant)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                purchase_data["id"],
                purchase_data["domain"],
                purchase_data["years"],
                str(purchase_data["amount"]),
                purchase_data["status"],
                purchase_data["created_at"],
                purchase_data["expires_at"],
                registrant_json,
            )
    else:
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
                registrant_json,
            ))
            await db.commit()


async def get_purchase(purchase_id: str) -> Optional[dict]:
    """Get a purchase by ID."""
    if IS_POSTGRES:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM purchases WHERE id = $1", purchase_id)
            if row:
                data = dict(row)
                data["amount"] = Decimal(data["amount"])
                if data["registrant"]:
                    data["registrant"] = json.loads(data["registrant"])
                return data
            return None
    else:
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
    if IS_POSTGRES:
        async with _pool.acquire() as conn:
            set_clauses = []
            values = []
            for i, (key, value) in enumerate(updates.items(), 1):
                if key == "registrant" and value:
                    value = json.dumps(value)
                elif key == "amount":
                    value = str(value)
                set_clauses.append(f"{key} = ${i}")
                values.append(value)
            values.append(purchase_id)

            await conn.execute(
                f"UPDATE purchases SET {', '.join(set_clauses)} WHERE id = ${len(values)}",
                *values
            )
    else:
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
    nameservers_json = json.dumps(domain_data["nameservers"])
    registrant_json = json.dumps(domain_data.get("registrant")) if domain_data.get("registrant") else None

    if IS_POSTGRES:
        async with _pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO domains (domain, owner_wallet, expires_at, nameservers, registered_at, registrant)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (domain) DO UPDATE SET
                    owner_wallet = EXCLUDED.owner_wallet,
                    expires_at = EXCLUDED.expires_at,
                    nameservers = EXCLUDED.nameservers,
                    registered_at = EXCLUDED.registered_at,
                    registrant = EXCLUDED.registrant
            """,
                domain_data["domain_name"],
                domain_data["owner_wallet"],
                domain_data["expires_at"],
                nameservers_json,
                domain_data["registered_at"],
                registrant_json,
            )
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO domains (domain, owner_wallet, expires_at, nameservers, registered_at, registrant)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                domain_data["domain_name"],
                domain_data["owner_wallet"],
                domain_data["expires_at"],
                nameservers_json,
                domain_data["registered_at"],
                registrant_json,
            ))
            await db.commit()


async def get_domain(domain: str) -> Optional[dict]:
    """Get a domain by name."""
    if IS_POSTGRES:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM domains WHERE domain = $1", domain)
            if row:
                data = dict(row)
                data["domain_name"] = data.pop("domain")
                data["nameservers"] = json.loads(data["nameservers"])
                if data["registrant"]:
                    data["registrant"] = json.loads(data["registrant"])
                return data
            return None
    else:
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
    if IS_POSTGRES:
        async with _pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM domains ORDER BY registered_at DESC")
            domains = []
            for row in rows:
                data = dict(row)
                data["domain_name"] = data.pop("domain")
                data["nameservers"] = json.loads(data["nameservers"])
                if data["registrant"]:
                    data["registrant"] = json.loads(data["registrant"])
                domains.append(data)
            return domains
    else:
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
    """Get all domains owned by a specific wallet address."""
    if IS_POSTGRES:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM domains WHERE LOWER(owner_wallet) = LOWER($1) ORDER BY registered_at DESC",
                wallet_address
            )
            domains = []
            for row in rows:
                data = dict(row)
                data["domain_name"] = data.pop("domain")
                data["nameservers"] = json.loads(data["nameservers"])
                if data["registrant"]:
                    data["registrant"] = json.loads(data["registrant"])
                domains.append(data)
            return domains
    else:
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
    if IS_POSTGRES:
        async with _pool.acquire() as conn:
            await conn.execute(
                "UPDATE domains SET nameservers = $1 WHERE domain = $2",
                json.dumps(nameservers), domain
            )
    else:
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
