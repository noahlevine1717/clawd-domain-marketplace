"""Payment verification for USDC on Base."""
import asyncio
from decimal import Decimal
from typing import Optional
from web3 import Web3
from web3.exceptions import TransactionNotFound
from . import config


# USDC has 6 decimals
USDC_DECIMALS = 6

# ERC20 Transfer event signature
TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()


class PaymentVerifier:
    """Verify USDC payments on Base network."""

    def __init__(self, rpc_url: Optional[str] = None, mock_mode: bool = False):
        self.rpc_url = rpc_url or config.BASE_RPC_URL
        self.mock_mode = mock_mode or config.MOCK_MODE
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url)) if not mock_mode else None

    async def verify_payment(
        self,
        tx_hash: str,
        expected_amount: Decimal,
        expected_recipient: str,
        expected_memo: Optional[str] = None,
    ) -> dict:
        """
        Verify a USDC payment transaction.

        Returns:
            {
                "verified": bool,
                "amount": Decimal or None,
                "sender": str or None,
                "recipient": str or None,
                "error": str or None,
            }
        """
        if self.mock_mode:
            return self._mock_verify(tx_hash, expected_amount, expected_recipient)

        try:
            # Get transaction receipt
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)

            if receipt is None:
                return {
                    "verified": False,
                    "error": "Transaction not found",
                }

            if receipt["status"] != 1:
                return {
                    "verified": False,
                    "error": "Transaction failed",
                }

            # Look for USDC Transfer event
            usdc_address = config.USDC_CONTRACT.lower()
            for log in receipt["logs"]:
                if log["address"].lower() != usdc_address:
                    continue

                if log["topics"][0].hex() != TRANSFER_TOPIC:
                    continue

                # Decode Transfer event
                # topics[1] = from (padded address)
                # topics[2] = to (padded address)
                # data = amount
                sender = "0x" + log["topics"][1].hex()[-40:]
                recipient = "0x" + log["topics"][2].hex()[-40:]
                amount_raw = int(log["data"].hex(), 16)
                amount = Decimal(amount_raw) / Decimal(10**USDC_DECIMALS)

                # Verify recipient matches
                if recipient.lower() != expected_recipient.lower():
                    continue

                # Verify amount (allow small tolerance for gas)
                if amount < expected_amount:
                    return {
                        "verified": False,
                        "amount": amount,
                        "sender": sender,
                        "recipient": recipient,
                        "error": f"Amount {amount} less than expected {expected_amount}",
                    }

                return {
                    "verified": True,
                    "amount": amount,
                    "sender": sender,
                    "recipient": recipient,
                    "error": None,
                }

            return {
                "verified": False,
                "error": "No matching USDC transfer found",
            }

        except TransactionNotFound:
            return {
                "verified": False,
                "error": "Transaction not found on chain",
            }
        except Exception as e:
            return {
                "verified": False,
                "error": f"Verification error: {str(e)}",
            }

    def _mock_verify(
        self, tx_hash: str, expected_amount: Decimal, expected_recipient: str
    ) -> dict:
        """Mock payment verification for development."""
        # In mock mode, accept any tx_hash that looks valid
        if tx_hash.startswith("0x") and len(tx_hash) == 66:
            return {
                "verified": True,
                "amount": expected_amount,
                "sender": "0x1234567890123456789012345678901234567890",
                "recipient": expected_recipient,
                "error": None,
                "mock": True,
            }
        return {
            "verified": False,
            "error": "Invalid transaction hash format",
        }

    async def wait_for_confirmation(
        self, tx_hash: str, max_attempts: int = 30, delay: float = 2.0
    ) -> dict:
        """Wait for transaction to be confirmed."""
        for _ in range(max_attempts):
            try:
                if self.mock_mode:
                    return {"confirmed": True, "block": 12345678}

                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt is not None:
                    return {
                        "confirmed": receipt["status"] == 1,
                        "block": receipt["blockNumber"],
                    }
            except TransactionNotFound:
                pass

            await asyncio.sleep(delay)

        return {"confirmed": False, "error": "Timeout waiting for confirmation"}


# Global verifier instance
verifier = PaymentVerifier()
