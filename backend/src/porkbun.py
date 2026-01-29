"""Porkbun API client with mock mode for development."""
import httpx
import random
from typing import Optional
from . import config


class PorkbunClient:
    """Client for Porkbun Domain Registrar API."""

    BASE_URL = "https://api.porkbun.com/api/json/v3"
    SANDBOX_URL = "https://api-ipv4.porkbun.com/api/json/v3"

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        sandbox: bool = False,
        mock_mode: bool = False,
    ):
        self.api_key = api_key or config.PORKBUN_API_KEY
        self.secret = secret or config.PORKBUN_SECRET
        self.sandbox = sandbox or config.PORKBUN_SANDBOX
        self.mock_mode = mock_mode or config.MOCK_MODE
        self.base_url = self.SANDBOX_URL if self.sandbox else self.BASE_URL

    def _auth_body(self) -> dict:
        """Return authentication fields for API requests."""
        return {"apikey": self.api_key, "secretapikey": self.secret}

    async def check_availability(self, domain: str) -> dict:
        """Check if a domain is available for registration."""
        if self.mock_mode:
            return self._mock_availability(domain)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/domain/checkDomain/{domain}",
                json=self._auth_body(),
            )
            data = resp.json()

            # Transform Porkbun response to our format
            if data.get("status") == "SUCCESS":
                response = data.get("response", {})
                return {
                    "status": "SUCCESS",
                    "avail": response.get("avail") == "yes",
                    "domain": domain,
                    "pricing": {
                        "registration": response.get("price"),
                        "renewal": response.get("additional", {}).get("renewal", {}).get("price"),
                    },
                    "premium": response.get("premium") == "yes",
                }
            return data

    async def get_pricing(self, domain: str) -> dict:
        """Get pricing for a domain."""
        if self.mock_mode:
            return self._mock_pricing(domain)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/domain/getPricing/{domain}",
                json=self._auth_body(),
            )
            return resp.json()

    async def register_domain(
        self,
        domain: str,
        years: int = 1,
        registrant: Optional[dict] = None,
        price_dollars: Optional[float] = None,
    ) -> dict:
        """Register a domain with customer as the legal registrant.

        Args:
            domain: The domain name to register
            years: Number of years to register
            registrant: ICANN registrant contact info (becomes legal owner)
            price_dollars: Pre-fetched price (avoids rate limit on checkDomain)
        """
        if self.mock_mode:
            return self._mock_register(domain, years)

        # Get pricing if not provided (may hit rate limit)
        if price_dollars is None:
            async with httpx.AsyncClient(timeout=30.0) as client:
                price_resp = await client.post(
                    f"{self.base_url}/domain/checkDomain/{domain}",
                    json=self._auth_body(),
                )
                price_data = price_resp.json()

            if price_data.get("status") != "SUCCESS":
                return {"status": "ERROR", "message": "Could not get pricing - rate limited or unavailable"}

            price_dollars = float(price_data.get("response", {}).get("price", 0))

        cost_pennies = int(price_dollars * 100)

        # Use provided registrant or fall back to default
        reg = registrant or config.DEFAULT_REGISTRANT

        # Build registration request with CUSTOMER as legal owner
        # Porkbun field names for registrant contact
        body = {
            **self._auth_body(),
            "cost": cost_pennies,
            "agreeToTerms": "yes",
            # Registrant info - THIS IS WHO LEGALLY OWNS THE DOMAIN
            "firstName": reg.get("firstName", ""),
            "lastName": reg.get("lastName", ""),
            "email": reg.get("email", ""),
            "phone": reg.get("phone", ""),
            "address": reg.get("address", ""),
            "city": reg.get("city", ""),
            "state": reg.get("state", ""),
            "zip": reg.get("zip", ""),
            "country": reg.get("country", "US"),
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/domain/create/{domain}",
                json=body,
            )
            result = resp.json()

            # Log the registration result for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Porkbun registration result for {domain}: {result}")

            if result.get("status") == "SUCCESS":
                # Add expiration date (1 year from now by default)
                from datetime import datetime, timedelta
                expiration = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d")
                result["expiration"] = expiration
                result["ns"] = ["ns1.porkbun.com", "ns2.porkbun.com"]

            return result

    async def get_auth_code(self, domain: str) -> dict:
        """Get auth/EPP code for domain transfer out.

        Note: Porkbun API does not expose auth code retrieval.
        Auth codes must be obtained via the Porkbun dashboard.
        """
        if self.mock_mode:
            return {"status": "SUCCESS", "code": "MOCK-AUTH-CODE-12345"}

        # Porkbun doesn't have an API endpoint for auth codes
        # Return instructions for getting it manually
        return {
            "status": "MANUAL_REQUIRED",
            "message": "Auth codes must be retrieved from the Porkbun dashboard",
            "instructions": [
                "1. Log in to porkbun.com",
                "2. Go to Domain Management",
                "3. Click the Details dropdown for your domain",
                "4. Select 'Get Authorization Code'",
                "5. Copy the auth code from the popup",
            ],
            "dashboard_url": f"https://porkbun.com/account/domain-details/{domain}",
            "note": "Porkbun generates a new code each time you request one",
        }

    async def update_nameservers(self, domain: str, nameservers: list[str]) -> dict:
        """Update nameservers for a domain (lets customer point to their hosting)."""
        if self.mock_mode:
            return {"status": "SUCCESS", "message": "Nameservers updated"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            body = {
                **self._auth_body(),
                "ns": nameservers,
            }
            resp = await client.post(
                f"{self.base_url}/domain/updateNs/{domain}",
                json=body,
            )
            return resp.json()

    async def create_dns_record(
        self, domain: str, record_type: str, name: str, content: str, ttl: int = 600
    ) -> dict:
        """Create a DNS record (lets customer set up their website)."""
        if self.mock_mode:
            return {"status": "SUCCESS", "id": "12345"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            body = {
                **self._auth_body(),
                "type": record_type,
                "name": name,
                "content": content,
                "ttl": str(ttl),
            }
            resp = await client.post(
                f"{self.base_url}/dns/create/{domain}",
                json=body,
            )
            return resp.json()

    async def delete_dns_record(self, domain: str, record_id: str) -> dict:
        """Delete a DNS record."""
        if self.mock_mode:
            return {"status": "SUCCESS"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/dns/delete/{domain}/{record_id}",
                json=self._auth_body(),
            )
            return resp.json()

    async def list_domains(self) -> dict:
        """List all domains in the account."""
        if self.mock_mode:
            return self._mock_list_domains()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/domain/listAll",
                json=self._auth_body(),
            )
            return resp.json()

    async def get_dns_records(self, domain: str) -> dict:
        """Get DNS records for a domain."""
        if self.mock_mode:
            return self._mock_dns_records(domain)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/dns/retrieve/{domain}",
                json=self._auth_body(),
            )
            return resp.json()

    # Mock responses for development without API keys
    def _mock_availability(self, domain: str) -> dict:
        """Mock availability check."""
        # Simulate some domains being taken
        taken_domains = {"google.com", "facebook.com", "amazon.com", "example.com"}
        is_available = domain.lower() not in taken_domains

        return {
            "status": "SUCCESS",
            "avail": is_available,
            "domain": domain,
            "pricing": self._get_mock_pricing(domain),
        }

    def _mock_pricing(self, domain: str) -> dict:
        """Mock pricing response."""
        return {
            "status": "SUCCESS",
            "pricing": self._get_mock_pricing(domain),
        }

    def _get_mock_pricing(self, domain: str) -> dict:
        """Get mock pricing for a domain."""
        tld = domain.split(".")[-1].lower()
        if tld in config.TLD_PRICING:
            prices = config.TLD_PRICING[tld]
            return {
                "registration": str(prices["first_year"]),
                "renewal": str(prices["renewal"]),
            }
        return {"registration": "19.99", "renewal": "24.99"}

    def _mock_register(self, domain: str, years: int) -> dict:
        """Mock domain registration."""
        return {
            "status": "SUCCESS",
            "domain": domain,
            "years": years,
            "message": f"[MOCK] Domain {domain} registered for {years} year(s)",
            "expiration": "2027-01-28",
            "ns": ["ns1.porkbun.com", "ns2.porkbun.com"],
        }

    def _mock_list_domains(self) -> dict:
        """Mock domain list."""
        return {
            "status": "SUCCESS",
            "domains": [],
        }

    def _mock_dns_records(self, domain: str) -> dict:
        """Mock DNS records."""
        return {
            "status": "SUCCESS",
            "records": [],
        }


# Global client instance
porkbun = PorkbunClient()
