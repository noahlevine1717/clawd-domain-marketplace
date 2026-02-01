"""EIP-3009 Relayer for executing transferWithAuthorization on USDC."""
import logging
from web3 import Web3
from eth_account import Account
from src import config

logger = logging.getLogger(__name__)

# USDC EIP-3009 ABI (only the functions we need)
USDC_ABI = [
    {
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
            {"name": "v", "type": "uint8"},
            {"name": "r", "type": "bytes32"},
            {"name": "s", "type": "bytes32"}
        ],
        "name": "transferWithAuthorization",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]


class Relayer:
    """Executes EIP-3009 transferWithAuthorization calls."""

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(config.BASE_RPC_URL))
        self.usdc = self.w3.eth.contract(
            address=Web3.to_checksum_address(config.USDC_CONTRACT),
            abi=USDC_ABI
        )

        if config.RELAYER_PRIVATE_KEY:
            self.account = Account.from_key(config.RELAYER_PRIVATE_KEY)
            self.address = self.account.address
            logger.info(f"Relayer initialized with address: {self.address}")
        else:
            self.account = None
            self.address = None
            logger.warning("Relayer initialized without private key (mock mode)")

    def parse_signature(self, signature: str) -> tuple:
        """Parse signature into v, r, s components."""
        sig_bytes = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)

        if len(sig_bytes) != 65:
            raise ValueError(f"Invalid signature length: {len(sig_bytes)}")

        r = sig_bytes[:32]
        s = sig_bytes[32:64]
        v = sig_bytes[64]

        # Handle EIP-155 v values
        if v < 27:
            v += 27

        return v, r, s

    async def execute_transfer(
        self,
        authorization: dict,
        signature: str,
        expected_recipient: str,
        expected_amount: float
    ) -> dict:
        """
        Execute transferWithAuthorization on USDC contract.

        Args:
            authorization: Dict with from, to, value, validAfter, validBefore, nonce
            signature: EIP-712 signature from the payer
            expected_recipient: Expected recipient address (treasury)
            expected_amount: Expected amount in dollars (will be converted to micro-units)

        Returns:
            Dict with verified, tx_hash, sender, error
        """
        try:
            # Validate authorization matches expected values
            from_addr = Web3.to_checksum_address(authorization["from"])
            to_addr = Web3.to_checksum_address(authorization["to"])
            value = int(authorization["value"])
            valid_after = int(authorization["validAfter"])
            valid_before = int(authorization["validBefore"])
            nonce = authorization["nonce"]

            # Convert nonce to bytes32 if it's a hex string
            if isinstance(nonce, str):
                nonce = bytes.fromhex(nonce[2:] if nonce.startswith("0x") else nonce)

            # Verify recipient matches treasury
            if to_addr.lower() != expected_recipient.lower():
                return {
                    "verified": False,
                    "error": f"Recipient mismatch: {to_addr} != {expected_recipient}"
                }

            # Verify amount (convert dollars to micro-units)
            expected_micro = int(expected_amount * 1_000_000)
            if value < expected_micro:
                return {
                    "verified": False,
                    "error": f"Amount too low: {value} < {expected_micro}"
                }

            # Check if authorization is still valid
            import time
            current_time = int(time.time())
            if current_time < valid_after:
                return {
                    "verified": False,
                    "error": f"Authorization not yet valid (validAfter: {valid_after})"
                }
            if current_time > valid_before:
                return {
                    "verified": False,
                    "error": f"Authorization expired (validBefore: {valid_before})"
                }

            # Check if relayer has enough ETH for gas
            if not self.account:
                # Mock mode - simulate success
                logger.warning("Mock mode: simulating successful transfer")
                return {
                    "verified": True,
                    "tx_hash": "0x" + "0" * 64,
                    "sender": from_addr,
                    "mock": True
                }

            relayer_balance = self.w3.eth.get_balance(self.address)
            min_gas_balance = Web3.to_wei(0.001, 'ether')  # ~0.001 ETH for gas
            if relayer_balance < min_gas_balance:
                logger.error(f"Relayer has insufficient ETH: {relayer_balance} wei")
                return {
                    "verified": False,
                    "error": "Relayer has insufficient gas. Please try again later."
                }

            # Parse signature
            v, r, s = self.parse_signature(signature)

            # Build transaction
            tx = self.usdc.functions.transferWithAuthorization(
                from_addr,
                to_addr,
                value,
                valid_after,
                valid_before,
                nonce,
                v,
                r,
                s
            ).build_transaction({
                'from': self.address,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'gas': 100000,  # Estimate, will be adjusted
                'maxFeePerGas': self.w3.eth.gas_price * 2,
                'maxPriorityFeePerGas': Web3.to_wei(0.001, 'gwei'),
            })

            # Estimate gas
            try:
                gas_estimate = self.w3.eth.estimate_gas(tx)
                tx['gas'] = int(gas_estimate * 1.2)  # 20% buffer
            except Exception as e:
                logger.error(f"Gas estimation failed: {e}")
                return {
                    "verified": False,
                    "error": f"Transaction would fail: {str(e)[:100]}"
                }

            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            logger.info(f"Submitted transferWithAuthorization tx: {tx_hash.hex()}")

            # Wait for confirmation (with timeout)
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

                if receipt['status'] == 1:
                    logger.info(f"Transfer successful: {tx_hash.hex()}")
                    return {
                        "verified": True,
                        "tx_hash": tx_hash.hex(),
                        "sender": from_addr,
                        "gas_used": receipt['gasUsed']
                    }
                else:
                    logger.error(f"Transfer failed (reverted): {tx_hash.hex()}")
                    return {
                        "verified": False,
                        "tx_hash": tx_hash.hex(),
                        "error": "Transaction reverted"
                    }
            except Exception as e:
                logger.error(f"Waiting for receipt failed: {e}")
                # Transaction was sent but we couldn't confirm
                return {
                    "verified": False,
                    "tx_hash": tx_hash.hex(),
                    "error": f"Transaction sent but confirmation failed: {str(e)[:100]}"
                }

        except Exception as e:
            logger.error(f"Transfer execution error: {e}")
            return {
                "verified": False,
                "error": f"Execution failed: {str(e)[:100]}"
            }


# Global relayer instance
relayer = Relayer()
