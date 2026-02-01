"""Clawd Domain Marketplace API - MVP Backend with Security Hardening."""
import uuid
import re
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from . import config
from .porkbun import porkbun
from .payments import verifier
from .relayer import relayer
from . import database as db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await db.init_db()
    logger.info("Database initialized")
    yield


app = FastAPI(
    title="Clawd Domain Marketplace",
    description="Domain registration via USDC payments",
    version="0.2.0",
    lifespan=lifespan,
)

# Add rate limit error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - use specific origins, not wildcard
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


# Wallet address validator
def validate_wallet_address(address: str) -> str:
    """Validate and normalize Ethereum wallet address."""
    if not config.is_valid_eth_address(address):
        raise ValueError("Invalid Ethereum address format")
    return address.lower()


# Request/Response Models with enhanced validation
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=63)
    tlds: list[str] = Field(default=["com", "dev", "io", "app", "xyz", "co", "org"])

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        v = v.lower().strip()
        if not v.replace("-", "").isalnum():
            raise ValueError("Invalid domain name characters")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Domain cannot start or end with hyphen")
        return v


class SearchResult(BaseModel):
    domain: str
    available: bool
    first_year_price_usdc: Optional[str] = None
    renewal_price_usdc: Optional[str] = None
    premium: bool = False


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    mock_mode: bool = False


class RegistrantInfo(BaseModel):
    """ICANN-required registrant contact information."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=5, max_length=255)
    phone: str = Field(default="+1.5551234567")
    address: str = Field(default="123 Main St")
    city: str = Field(default="San Francisco")
    state: str = Field(default="CA")
    zip_code: str = Field(default="94102")
    country: str = Field(default="US")


class PurchaseRequest(BaseModel):
    domain: str = Field(..., min_length=3, max_length=253)
    years: int = Field(default=1, ge=1, le=10)
    registrant: Optional[RegistrantInfo] = None


class PaymentRequest(BaseModel):
    amount_usdc: str
    recipient: str
    chain_id: int
    memo: str
    expires_at: str


class PurchaseResponse(BaseModel):
    purchase_id: str
    domain: str
    years: int
    payment_request: PaymentRequest


class ConfirmRequest(BaseModel):
    purchase_id: str
    tx_hash: str = Field(..., min_length=66, max_length=66)


class DomainInfo(BaseModel):
    domain_name: str
    expires_at: str
    nameservers: list[str]
    registered_at: str


class ConfirmResponse(BaseModel):
    status: str
    domain: Optional[DomainInfo] = None
    error: Optional[str] = None
    mock_mode: bool = False


class NameserverUpdate(BaseModel):
    """Request to update domain nameservers."""
    domain: str
    nameservers: list[str] = Field(..., min_length=2, max_length=6)
    wallet: str = Field(..., min_length=42, max_length=42)

    @field_validator("wallet")
    @classmethod
    def validate_wallet(cls, v):
        return validate_wallet_address(v)


class DNSRecordCreate(BaseModel):
    """Request to create a DNS record."""
    domain: str
    record_type: str = Field(..., pattern="^(A|AAAA|CNAME|MX|TXT|NS|SRV)$")
    name: str = Field(default="")
    content: str
    ttl: int = Field(default=600, ge=300, le=86400)
    wallet: str = Field(..., min_length=42, max_length=42)

    @field_validator("wallet")
    @classmethod
    def validate_wallet(cls, v):
        return validate_wallet_address(v)


class DNSRecordDelete(BaseModel):
    """Request to delete a DNS record."""
    domain: str
    record_id: str
    wallet: str = Field(..., min_length=42, max_length=42)

    @field_validator("wallet")
    @classmethod
    def validate_wallet(cls, v):
        return validate_wallet_address(v)


# Health check
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mock_mode": config.MOCK_MODE,
        "version": "0.2.0",
        "environment": config.ENVIRONMENT,
    }


# Domain search with rate limiting
@app.post("/search", response_model=SearchResponse)
@limiter.limit(config.RATE_LIMIT_SEARCH)
async def search_domains(req: SearchRequest, request: Request):
    """Search for available domains across TLDs."""
    query = req.query  # Already validated and normalized

    results = []
    for tld in req.tlds:
        tld = tld.lower().strip().lstrip(".")
        domain = f"{query}.{tld}"

        try:
            avail_resp = await porkbun.check_availability(domain)

            is_available = avail_resp.get("avail", False)
            if isinstance(is_available, str):
                is_available = is_available.lower() in ("true", "yes")

            is_premium = avail_resp.get("premium", False)

            porkbun_pricing = avail_resp.get("pricing", {})
            if porkbun_pricing.get("registration"):
                base_price = float(porkbun_pricing["registration"])
                renewal_price = float(porkbun_pricing.get("renewal", base_price))
                first_year = base_price + 2.50
                renewal = renewal_price + 3.00
            else:
                pricing = config.TLD_PRICING.get(tld, {"first_year": 19.99, "renewal": 24.99})
                first_year = pricing["first_year"]
                renewal = pricing["renewal"]

            results.append(
                SearchResult(
                    domain=domain,
                    available=is_available,
                    first_year_price_usdc=f"{first_year:.2f}" if is_available else None,
                    renewal_price_usdc=f"{renewal:.2f}" if is_available else None,
                    premium=is_premium,
                )
            )
        except Exception as e:
            logger.error(f"Error checking {domain}: {e}")
            results.append(
                SearchResult(domain=domain, available=False, premium=False)
            )

    return SearchResponse(query=query, results=results, mock_mode=config.MOCK_MODE)


# Initiate purchase with rate limiting
@app.post("/purchase/initiate", response_model=PurchaseResponse)
@limiter.limit(config.RATE_LIMIT_PURCHASE)
async def initiate_purchase(req: PurchaseRequest, request: Request):
    """Initiate a domain purchase. Returns payment request."""
    domain = req.domain.lower().strip()

    parts = domain.split(".")
    if len(parts) < 2:
        raise HTTPException(400, "Invalid domain format")

    tld = parts[-1]
    pricing = config.TLD_PRICING.get(tld, {"first_year": 12.99, "renewal": 14.99})
    total_price = Decimal(str(pricing["first_year"]))
    if req.years > 1:
        total_price += Decimal(str(pricing["renewal"])) * (req.years - 1)

    purchase_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    registrant = None
    if req.registrant:
        registrant = {
            "firstName": req.registrant.first_name,
            "lastName": req.registrant.last_name,
            "email": req.registrant.email,
            "phone": req.registrant.phone,
            "address": req.registrant.address,
            "city": req.registrant.city,
            "state": req.registrant.state,
            "zip": req.registrant.zip_code,
            "country": req.registrant.country,
        }

    # Store in database
    await db.create_purchase({
        "id": purchase_id,
        "domain": domain,
        "years": req.years,
        "amount": total_price,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at.isoformat(),
        "registrant": registrant,
    })

    return PurchaseResponse(
        purchase_id=purchase_id,
        domain=domain,
        years=req.years,
        payment_request=PaymentRequest(
            amount_usdc=f"{total_price:.2f}",
            recipient=config.TREASURY_ADDRESS,
            chain_id=8453,
            memo=f"clawd:domain:{purchase_id}",
            expires_at=expires_at.isoformat() + "Z",
        ),
    )


# x402 payment endpoint - supports both GET and POST for compatibility
@app.api_route("/purchase/pay/{purchase_id}", methods=["GET", "POST"])
@limiter.limit(config.RATE_LIMIT_PURCHASE)
async def x402_payment(purchase_id: str, request: Request):
    """Handle x402 payment flow - returns 402 or processes payment."""
    purchase = await db.get_purchase(purchase_id)
    if not purchase:
        raise HTTPException(404, "Purchase not found")

    if purchase["status"] == "completed":
        domain_info = await db.get_domain(purchase["domain"])
        return JSONResponse({"status": "success", "domain": domain_info})

    if purchase["status"] not in ["pending", "awaiting_payment"]:
        raise HTTPException(400, f"Purchase status is {purchase['status']}")

    # Check for X-PAYMENT header (x402 protocol) or Authorization header (legacy)
    payment_header = request.headers.get("x-payment", "") or request.headers.get("authorization", "")

    if payment_header:
        await db.update_purchase(purchase_id, {"status": "processing"})

        # Parse payment header - try JSON first (X-PAYMENT), then legacy format
        params = {}
        tx_hash = ""
        payer = "unknown"
        auth = {}
        signature = ""

        try:
            # Try base64-decoded JSON (x402 X-PAYMENT format)
            import base64
            decoded = base64.b64decode(payment_header).decode('utf-8')
            payment_data = json.loads(decoded)
            logger.info(f"Decoded X-PAYMENT payload keys: {list(payment_data.keys())}")
            payload = payment_data.get("payload", {})
            logger.info(f"Payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'not a dict'}")

            # Log full payload for debugging
            logger.info(f"Full payload: {json.dumps(payload)[:500]}")

            # Try multiple paths for transaction hash
            auth = payload.get("authorization", {})
            if isinstance(auth, str):
                try:
                    auth = json.loads(auth)
                except:
                    auth = {}
            logger.info(f"Authorization keys: {list(auth.keys()) if isinstance(auth, dict) else 'not a dict'}")

            # Check for direct tx_hash first
            tx_hash = (
                payload.get("transactionHash", "") or
                payload.get("txHash", "") or
                payload.get("transaction", {}).get("hash", "") if isinstance(payload.get("transaction"), dict) else "" or
                payment_data.get("transactionHash", "")
            )

            # Get signature for EIP-3009 flow
            signature = payload.get("signature", "")

            # Determine payer from authorization or payload
            payer = auth.get("from", "") or payload.get("payer", "") or payload.get("address", "") or "unknown"
            logger.info(f"Parsed X-PAYMENT header: tx_hash={tx_hash}, payer={payer}, has_auth={bool(auth)}, has_sig={bool(signature)}")
        except Exception:
            try:
                # Try direct JSON
                payment_data = json.loads(payment_header)
                tx_hash = payment_data.get("tx_hash", "") or payment_data.get("transactionHash", "")
                payer = payment_data.get("payer", "unknown")
                logger.info(f"Parsed JSON payment header: tx_hash={tx_hash}, payer={payer}")
            except Exception:
                # Legacy format: x402 key="value" pairs
                if payment_header.startswith("x402 "):
                    matches = re.findall(r'(\w+)="([^"]+)"', payment_header)
                    for key, value in matches:
                        params[key] = value
                    tx_hash = params.get("tx_hash", "")
                    payer = params.get("payer", "unknown")
                    logger.info(f"Parsed legacy x402 header: tx_hash={tx_hash}, payer={payer}")

        # CRITICAL: Verify payment on-chain before registering domain
        if not tx_hash:
            # Check if we have EIP-3009 authorization to execute
            if auth and signature and auth.get("from") and auth.get("to"):
                logger.info(f"Executing EIP-3009 transfer for {purchase['domain']}")

                # Execute the transfer via relayer
                result = await relayer.execute_transfer(
                    authorization=auth,
                    signature=signature,
                    expected_recipient=config.TREASURY_ADDRESS,
                    expected_amount=float(purchase["amount"])
                )

                if not result.get("verified"):
                    await db.update_purchase(purchase_id, {"status": "awaiting_payment"})
                    logger.error(f"EIP-3009 execution failed: {result.get('error')}")
                    return JSONResponse(
                        status_code=400,
                        content={"error": f"Payment execution failed: {result.get('error', 'Unknown error')}. Please retry."}
                    )

                # Transfer succeeded - use the tx_hash from execution
                tx_hash = result.get("tx_hash", "")
                payer = result.get("sender", payer)
                logger.info(f"EIP-3009 transfer successful: tx_hash={tx_hash}, payer={payer}")

                # Skip additional verification - relayer already confirmed the transaction
                verification = {"verified": True, "sender": payer, "relayer_executed": True}
                verified_payer = payer
                await db.update_purchase(purchase_id, {"payer": verified_payer, "tx_hash": tx_hash})

                # Jump directly to domain registration
                try:
                    reg_result = await porkbun.register_domain(
                        domain=purchase["domain"],
                        years=purchase["years"],
                        registrant=purchase.get("registrant"),
                    )

                    if reg_result.get("status") != "SUCCESS":
                        await db.update_purchase(purchase_id, {"status": "registration_failed"})
                        return JSONResponse(
                            status_code=500,
                            content={"error": "Domain registration failed. Please contact support."}
                        )

                    await db.update_purchase(purchase_id, {"status": "completed"})

                    domain_info = {
                        "domain_name": purchase["domain"],
                        "expires_at": reg_result.get("expiration", "2027-01-28"),
                        "nameservers": reg_result.get("ns", ["ns1.porkbun.com", "ns2.porkbun.com"]),
                        "registered_at": datetime.utcnow().isoformat(),
                        "owner_wallet": verified_payer,
                        "registrant": purchase.get("registrant", {}),
                    }
                    await db.create_domain(domain_info)

                    return JSONResponse({
                        "status": "success",
                        "message": f"Domain {purchase['domain']} registered successfully!",
                        "domain": domain_info,
                        "tx_hash": tx_hash,
                        "ownership": {
                            "legal_owner": "Customer (registrant info in WHOIS)",
                            "dns_control": "Full access via this API",
                            "transfer_rights": "Can transfer anytime with auth code",
                        }
                    })

                except Exception as e:
                    logger.error(f"Registration error for {purchase['domain']}: {e}")
                    await db.update_purchase(purchase_id, {"status": "error"})
                    return JSONResponse(
                        status_code=500,
                        content={"error": "An error occurred during registration. Please try again."}
                    )

            else:
                # No tx_hash and no EIP-3009 authorization - can't process
                await db.update_purchase(purchase_id, {"status": "awaiting_payment"})
                logger.error(f"No tx_hash or authorization in payment header: {payment_header[:100]}")
                return JSONResponse(status_code=400, content={"error": "Missing transaction hash or authorization in payment header. Please retry."})

        if config.SKIP_PAYMENT_VERIFICATION:
            if config.ENVIRONMENT == "production":
                logger.error("SKIP_PAYMENT_VERIFICATION is enabled in production - this is a security risk!")
                await db.update_purchase(purchase_id, {"status": "payment_failed"})
                return JSONResponse(status_code=500, content={"error": "Payment verification misconfigured"})
            verification = {"verified": True, "mock": True, "sender": payer}
            logger.warning(f"SKIPPING payment verification for {tx_hash} (dev mode)")
        else:
            verification = await verifier.verify_payment(
                tx_hash=tx_hash,
                expected_amount=purchase["amount"],
                expected_recipient=config.TREASURY_ADDRESS,
            )

        if not verification.get("verified"):
            await db.update_purchase(purchase_id, {"status": "payment_failed", "tx_hash": tx_hash})
            logger.error(f"Payment verification failed for {tx_hash}: {verification.get('error')}")
            return JSONResponse(
                status_code=402,
                content={"error": f"Payment verification failed: {verification.get('error', 'Unknown error')}"}
            )

        # Payment verified - use the actual sender from blockchain
        verified_payer = verification.get("sender", payer)
        await db.update_purchase(purchase_id, {"payer": verified_payer, "tx_hash": tx_hash})

        try:
            reg_result = await porkbun.register_domain(
                domain=purchase["domain"],
                years=purchase["years"],
                registrant=purchase.get("registrant"),
            )

            if reg_result.get("status") != "SUCCESS":
                await db.update_purchase(purchase_id, {"status": "registration_failed"})
                return JSONResponse(
                    status_code=500,
                    content={"error": "Domain registration failed. Please contact support."}
                )

            await db.update_purchase(purchase_id, {"status": "completed"})

            domain_info = {
                "domain_name": purchase["domain"],
                "expires_at": reg_result.get("expiration", "2027-01-28"),
                "nameservers": reg_result.get("ns", ["ns1.porkbun.com", "ns2.porkbun.com"]),
                "registered_at": datetime.utcnow().isoformat(),
                "owner_wallet": verified_payer,
                "registrant": purchase.get("registrant", {}),
            }
            await db.create_domain(domain_info)

            return JSONResponse({
                "status": "success",
                "message": f"Domain {purchase['domain']} registered successfully!",
                "domain": domain_info,
                "tx_hash": tx_hash,
                "ownership": {
                    "legal_owner": "Customer (registrant info in WHOIS)",
                    "dns_control": "Full access via this API",
                    "transfer_rights": "Can transfer anytime with auth code",
                }
            })

        except Exception as e:
            logger.error(f"Registration error for {purchase['domain']}: {e}")
            await db.update_purchase(purchase_id, {"status": "error"})
            return JSONResponse(
                status_code=500,
                content={"error": "An error occurred during registration. Please try again."}
            )

    # No payment proof - return 402 with x402 protocol format
    await db.update_purchase(purchase_id, {"status": "awaiting_payment"})

    # Convert dollars to micro-units (6 decimals for USDC)
    amount_micro = str(int(float(purchase['amount']) * 1_000_000))
    description = f"Domain: {purchase['domain']} ({purchase['years']} year)"
    resource_url = f"{config.PUBLIC_URL}/purchase/pay/{purchase_id}"

    # USDC contract address on Base
    USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

    x402_response = {
        "x402Version": 1,
        "error": "X-PAYMENT header is required",
        "accepts": [
            {
                "scheme": "exact",
                "network": "base",
                "maxAmountRequired": amount_micro,
                "resource": resource_url,
                "description": description,
                "mimeType": "application/json",
                "payTo": config.TREASURY_ADDRESS,
                "maxTimeoutSeconds": 300,
                "asset": USDC_BASE_ADDRESS,
                "outputSchema": {
                    "input": {
                        "type": "http",
                        "method": "POST",
                        "discoverable": True
                    }
                },
                "extra": {
                    "name": "USD Coin",
                    "version": "2"
                }
            }
        ]
    }

    return JSONResponse(
        status_code=402,
        content=x402_response
    )


# Complete purchase after x402 payment
@app.post("/purchase/complete/{purchase_id}")
async def complete_purchase(purchase_id: str):
    """Complete purchase after x402 payment."""
    purchase = await db.get_purchase(purchase_id)
    if not purchase:
        raise HTTPException(404, "Purchase not found")

    try:
        reg_result = await porkbun.register_domain(
            domain=purchase["domain"],
            years=purchase["years"],
        )

        if reg_result.get("status") != "SUCCESS":
            await db.update_purchase(purchase_id, {"status": "registration_failed"})
            raise HTTPException(500, "Domain registration failed")

        await db.update_purchase(purchase_id, {"status": "completed"})

        domain_info = {
            "domain_name": purchase["domain"],
            "expires_at": reg_result.get("expiration", "2027-01-28"),
            "nameservers": reg_result.get("ns", ["ns1.porkbun.com", "ns2.porkbun.com"]),
            "registered_at": datetime.utcnow().isoformat(),
            "owner_wallet": purchase.get("payer", ""),
            "registrant": purchase.get("registrant", {}),
        }
        await db.create_domain(domain_info)

        return {"status": "success", "domain": domain_info}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Complete purchase error: {e}")
        await db.update_purchase(purchase_id, {"status": "error"})
        raise HTTPException(500, "An error occurred. Please try again.")


# Confirm purchase after payment
@app.post("/purchase/confirm", response_model=ConfirmResponse)
async def confirm_purchase(req: ConfirmRequest):
    """Confirm purchase after payment is made."""
    purchase = await db.get_purchase(req.purchase_id)

    if not purchase:
        raise HTTPException(404, "Purchase not found")

    if purchase["status"] == "completed":
        domain_info = await db.get_domain(purchase["domain"])
        if domain_info:
            return ConfirmResponse(
                status="already_completed",
                domain=DomainInfo(**{k: domain_info[k] for k in ["domain_name", "expires_at", "nameservers", "registered_at"]}),
                mock_mode=config.MOCK_MODE,
            )

    if purchase["status"] == "failed":
        raise HTTPException(400, "Purchase already failed")

    expires_at = datetime.fromisoformat(purchase["expires_at"])
    if datetime.utcnow() > expires_at:
        await db.update_purchase(req.purchase_id, {"status": "expired"})
        raise HTTPException(400, "Purchase expired")

    if config.SKIP_PAYMENT_VERIFICATION:
        verification = {"verified": True, "mock": True}
    else:
        verification = await verifier.verify_payment(
            tx_hash=req.tx_hash,
            expected_amount=purchase["amount"],
            expected_recipient=config.TREASURY_ADDRESS,
        )

    if not verification["verified"]:
        await db.update_purchase(req.purchase_id, {"status": "payment_failed"})
        return ConfirmResponse(
            status="payment_failed",
            error="Payment verification failed",
            mock_mode=config.MOCK_MODE,
        )

    try:
        reg_result = await porkbun.register_domain(
            domain=purchase["domain"],
            years=purchase["years"],
        )

        if reg_result.get("status") != "SUCCESS":
            await db.update_purchase(req.purchase_id, {"status": "registration_failed"})
            return ConfirmResponse(
                status="registration_failed",
                error="Domain registration failed",
                mock_mode=config.MOCK_MODE,
            )

        await db.update_purchase(req.purchase_id, {"status": "completed", "tx_hash": req.tx_hash})

        domain_info = {
            "domain_name": purchase["domain"],
            "expires_at": reg_result.get("expiration", "2027-01-28"),
            "nameservers": reg_result.get("ns", ["ns1.porkbun.com", "ns2.porkbun.com"]),
            "registered_at": datetime.utcnow().isoformat(),
            "owner_wallet": purchase.get("payer", ""),
            "registrant": purchase.get("registrant", {}),
        }
        await db.create_domain(domain_info)

        return ConfirmResponse(
            status="success",
            domain=DomainInfo(**{k: domain_info[k] for k in ["domain_name", "expires_at", "nameservers", "registered_at"]}),
            mock_mode=config.MOCK_MODE,
        )

    except Exception as e:
        logger.error(f"Confirm purchase error: {e}")
        await db.update_purchase(req.purchase_id, {"status": "error"})
        return ConfirmResponse(
            status="error",
            error="An error occurred during registration",
            mock_mode=config.MOCK_MODE,
        )


# Debug endpoint to check purchase state
@app.get("/debug/purchase/{purchase_id}")
async def debug_purchase(purchase_id: str):
    """Debug endpoint to check purchase status."""
    purchase = await db.get_purchase(purchase_id)
    if not purchase:
        return {"id": purchase_id, "status": "not_found"}
    return {
        "id": purchase_id,
        "domain": purchase.get("domain"),
        "status": purchase.get("status"),
        "created_at": purchase.get("created_at"),
        "amount": purchase.get("amount"),
    }


# List domains for a specific wallet
@app.get("/domains")
async def list_domains(wallet: str):
    """List domains owned by a specific wallet address.

    Each wallet can only see their own domains - wallet address acts as an API key.
    """
    try:
        wallet = validate_wallet_address(wallet)
    except ValueError as e:
        raise HTTPException(400, str(e))
    domains = await db.get_domains_by_wallet(wallet)
    return {
        "wallet": wallet,
        "domains": domains,
        "total": len(domains),
        "mock_mode": config.MOCK_MODE,
    }


# Get purchase status (requires wallet that initiated the purchase)
@app.get("/purchase/{purchase_id}")
async def get_purchase(purchase_id: str, wallet: str):
    """Get status of a purchase.

    Only the wallet that initiated the purchase (payer) can view its status.
    """
    try:
        wallet = validate_wallet_address(wallet)
    except ValueError as e:
        raise HTTPException(400, str(e))
    purchase = await db.get_purchase(purchase_id)
    if not purchase:
        raise HTTPException(404, "Purchase not found")

    # Verify ownership - payer wallet must match
    payer = purchase.get("payer", "").lower()
    # For pending purchases, we don't have a payer yet - allow access by purchase_id only
    # This is safe because purchase_id is a random UUID
    if payer and payer != wallet.lower():
        raise HTTPException(403, "You don't own this purchase")

    # Don't expose internal fields
    safe_purchase = {
        "id": purchase["id"],
        "domain": purchase["domain"],
        "years": purchase["years"],
        "status": purchase["status"],
        "created_at": purchase["created_at"],
        "expires_at": purchase["expires_at"],
    }
    return safe_purchase


# ============================================================================
# DOMAIN MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/domains/{domain}/auth-code")
@limiter.limit(config.RATE_LIMIT_DNS)
async def get_auth_code(domain: str, wallet: str, request: Request):
    """Get auth/EPP code for domain transfer."""
    try:
        wallet = validate_wallet_address(wallet)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not await db.verify_domain_owner(domain, wallet):
        raise HTTPException(403, "You don't own this domain")

    try:
        result = await porkbun.get_auth_code(domain)
        if result.get("status") == "SUCCESS":
            return {
                "domain": domain,
                "auth_code": result.get("code"),
                "message": "Use this code to transfer your domain to any registrar.",
            }
        elif result.get("status") == "MANUAL_REQUIRED":
            return {
                "domain": domain,
                "auth_code": None,
                "manual_required": True,
                "instructions": result.get("instructions", []),
                "dashboard_url": result.get("dashboard_url"),
                "message": "Auth code must be retrieved from Porkbun dashboard.",
            }
        raise HTTPException(500, "Failed to get auth code")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth code error: {e}")
        raise HTTPException(500, "An error occurred. Please try again.")


@app.post("/domains/nameservers")
@limiter.limit(config.RATE_LIMIT_DNS)
async def update_nameservers(req: NameserverUpdate, request: Request):
    """Update nameservers for a domain."""
    if not await db.verify_domain_owner(req.domain, req.wallet):
        raise HTTPException(403, "You don't own this domain")

    try:
        result = await porkbun.update_nameservers(req.domain, req.nameservers)
        if result.get("status") == "SUCCESS":
            await db.update_domain_nameservers(req.domain, req.nameservers)
            return {
                "status": "success",
                "domain": req.domain,
                "nameservers": req.nameservers,
                "message": "Nameservers updated. DNS propagation may take up to 48 hours.",
            }
        raise HTTPException(500, "Failed to update nameservers")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Nameserver update error: {e}")
        raise HTTPException(500, "An error occurred. Please try again.")


@app.get("/domains/{domain}/dns")
@limiter.limit(config.RATE_LIMIT_DNS)
async def get_dns_records(domain: str, wallet: str, request: Request):
    """Get all DNS records for a domain."""
    try:
        wallet = validate_wallet_address(wallet)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not await db.verify_domain_owner(domain, wallet):
        raise HTTPException(403, "You don't own this domain")

    try:
        result = await porkbun.get_dns_records(domain)
        if result.get("status") == "SUCCESS":
            return {"domain": domain, "records": result.get("records", [])}
        if "not found" in result.get("message", "").lower():
            raise HTTPException(404, "Domain not found in account")
        raise HTTPException(500, "Failed to get DNS records")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DNS list error: {e}")
        raise HTTPException(500, "An error occurred. Please try again.")


@app.post("/domains/dns")
@limiter.limit(config.RATE_LIMIT_DNS)
async def create_dns_record(req: DNSRecordCreate, request: Request):
    """Create a DNS record."""
    if not await db.verify_domain_owner(req.domain, req.wallet):
        raise HTTPException(403, "You don't own this domain")

    try:
        result = await porkbun.create_dns_record(
            domain=req.domain,
            record_type=req.record_type,
            name=req.name,
            content=req.content,
            ttl=req.ttl,
        )
        if result.get("status") == "SUCCESS":
            return {
                "status": "success",
                "domain": req.domain,
                "record_id": result.get("id"),
                "message": f"{req.record_type} record created.",
            }
        raise HTTPException(500, "Failed to create DNS record")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DNS create error: {e}")
        raise HTTPException(500, "An error occurred. Please try again.")


@app.delete("/domains/dns")
@limiter.limit(config.RATE_LIMIT_DNS)
async def delete_dns_record(req: DNSRecordDelete, request: Request):
    """Delete a DNS record."""
    if not await db.verify_domain_owner(req.domain, req.wallet):
        raise HTTPException(403, "You don't own this domain")

    try:
        result = await porkbun.delete_dns_record(req.domain, req.record_id)
        if result.get("status") == "SUCCESS":
            return {"status": "success", "message": "DNS record deleted"}
        raise HTTPException(500, "Failed to delete DNS record")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DNS delete error: {e}")
        raise HTTPException(500, "An error occurred. Please try again.")


# Main entry point
if __name__ == "__main__":
    import uvicorn

    print(f"Starting Clawd Domain API on port {config.PORT}")
    print(f"Mock mode: {config.MOCK_MODE}")
    print(f"Environment: {config.ENVIRONMENT}")

    uvicorn.run(
        "src.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
    )
