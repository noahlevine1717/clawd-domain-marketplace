"""Configuration for Clawd Domain Backend."""
import os
import re
from dotenv import load_dotenv

load_dotenv()

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# Porkbun API
PORKBUN_API_KEY = os.getenv("PORKBUN_API_KEY", "")
PORKBUN_SECRET = os.getenv("PORKBUN_SECRET", "")
PORKBUN_SANDBOX = os.getenv("PORKBUN_SANDBOX", "false").lower() == "true"

# Use mock mode if no API keys provided
MOCK_MODE = not PORKBUN_API_KEY or not PORKBUN_SECRET

# Skip payment verification for testing (DANGEROUS - only for dev!)
SKIP_PAYMENT_VERIFICATION = os.getenv("SKIP_PAYMENT_VERIFICATION", "false").lower() == "true"

# CRITICAL: Prevent skip verification in production
if IS_PRODUCTION and SKIP_PAYMENT_VERIFICATION:
    raise RuntimeError("SKIP_PAYMENT_VERIFICATION cannot be enabled in production!")

# Payment settings
TREASURY_ADDRESS = os.getenv("TREASURY_ADDRESS", "0x742D35cc6634C0532925a3B844bc9E7595f5BE91")
BASE_RPC_URL = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base

# Relayer wallet for executing EIP-3009 transfers (pays gas)
RELAYER_PRIVATE_KEY = os.getenv("RELAYER_PRIVATE_KEY", "")
if IS_PRODUCTION and not RELAYER_PRIVATE_KEY:
    raise RuntimeError("RELAYER_PRIVATE_KEY is required in production for payment execution")

# CORS - specific origins for security
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8402").split(",")
if IS_PRODUCTION and "*" in ALLOWED_ORIGINS:
    raise RuntimeError("Wildcard CORS origin not allowed in production!")

# Default registrant info (for MVP - replace with real user data)
DEFAULT_REGISTRANT = {
    "firstName": os.getenv("REGISTRANT_FIRST_NAME", "Demo"),
    "lastName": os.getenv("REGISTRANT_LAST_NAME", "User"),
    "email": os.getenv("REGISTRANT_EMAIL", "demo@clawd.dev"),
    "phone": os.getenv("REGISTRANT_PHONE", "+1.5551234567"),
    "address": os.getenv("REGISTRANT_ADDRESS", "123 Demo Street"),
    "city": os.getenv("REGISTRANT_CITY", "San Francisco"),
    "state": os.getenv("REGISTRANT_STATE", "CA"),
    "zip": os.getenv("REGISTRANT_ZIP", "94102"),
    "country": os.getenv("REGISTRANT_COUNTRY", "US"),
}

# Pricing (markup over Porkbun costs)
TLD_PRICING = {
    "com": {"first_year": 12.99, "renewal": 14.99},
    "net": {"first_year": 12.99, "renewal": 14.99},
    "org": {"first_year": 12.99, "renewal": 14.99},
    "dev": {"first_year": 14.99, "renewal": 16.99},
    "app": {"first_year": 16.99, "renewal": 18.99},
    "io": {"first_year": 34.99, "renewal": 39.99},
    "co": {"first_year": 29.99, "renewal": 34.99},
    "xyz": {"first_year": 4.99, "renewal": 14.99},
    "ai": {"first_year": 79.99, "renewal": 89.99},
}

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8402"))

# Public URL for x402 callbacks (set to ngrok URL or production URL)
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8402")

# Database (SQLite for MVP, PostgreSQL for production)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clawd_domains.db")

# Rate limiting
RATE_LIMIT_SEARCH = os.getenv("RATE_LIMIT_SEARCH", "20/minute")
RATE_LIMIT_PURCHASE = os.getenv("RATE_LIMIT_PURCHASE", "10/minute")
RATE_LIMIT_DNS = os.getenv("RATE_LIMIT_DNS", "30/minute")


# Validation helpers
def is_valid_eth_address(address: str) -> bool:
    """Validate Ethereum address format."""
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))


def sanitize_error(error: Exception) -> str:
    """Remove sensitive details from error messages for user display."""
    msg = str(error)
    # Remove file paths
    msg = re.sub(r'/[^\s]+/', '[path]/', msg)
    # Remove line numbers
    msg = re.sub(r'line \d+', 'line [N]', msg)
    # Remove potential secrets
    msg = re.sub(r'(api[_-]?key|secret|password|token)[=:]\s*\S+', r'\1=[REDACTED]', msg, flags=re.IGNORECASE)
    # Truncate
    return msg[:200] + "..." if len(msg) > 200 else msg
