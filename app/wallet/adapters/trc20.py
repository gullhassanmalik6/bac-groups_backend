from uuid import uuid4

from app.wallet.base import WalletProvider, WalletTransferRequest, WalletTransferResult


class Trc20WalletProvider(WalletProvider):
    """TRC20 USDT wallet adapter (sandbox-capable transfer simulation)."""

    network_name = "trc20"

    async def validate_address(self, address: str) -> bool:
        return address.startswith("T") and 30 <= len(address) <= 42

    async def transfer(self, request: WalletTransferRequest) -> WalletTransferResult:
        if not await self.validate_address(request.to_address):
            return WalletTransferResult(
                success=False,
                tx_hash=None,
                error_message="Invalid TRC20 wallet address",
            )
        tx_hash = f"trc20_{uuid4().hex}"
        return WalletTransferResult(
            success=True,
            tx_hash=tx_hash,
            confirmation_count=1,
            raw_response={
                "network": self.network_name,
                "to": request.to_address,
                "amount": str(request.amount),
                "currency": request.currency,
            },
        )

    async def get_transfer_status(self, tx_hash: str) -> WalletTransferResult:
        return WalletTransferResult(
            success=True,
            tx_hash=tx_hash,
            confirmation_count=19,
            raw_response={"network": self.network_name, "tx_hash": tx_hash},
        )
