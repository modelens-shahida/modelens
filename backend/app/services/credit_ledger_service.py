"""
Immutable Credit Transaction Ledger
Cryptographic hash chaining for audit-proof credit transactions.
"""
import hashlib
import json
import csv
import io
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any


class CreditLedgerService:
    """
    Immutable credit ledger with SHA-256 hash chaining.
    Each transaction references the hash of the previous transaction,
    creating an unbreakable audit chain.
    """

    def compute_transaction_hash(
        self,
        transaction_id: int,
        user_id: int,
        brand_id: int,
        transaction_type: str,
        amount: int,
        balance_after: int,
        previous_hash: str,
        created_at: str,
    ) -> str:
        """Compute SHA-256 hash for a transaction."""
        payload = json.dumps({
            "transaction_id": transaction_id,
            "user_id": user_id,
            "brand_id": brand_id,
            "transaction_type": transaction_type,
            "amount": amount,
            "balance_after": balance_after,
            "previous_hash": previous_hash,
            "created_at": created_at,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def verify_chain_integrity(
        self,
        transactions: List[Dict],
    ) -> Dict[str, Any]:
        """Verify the integrity of the hash chain."""
        if not transactions:
            return {"valid": True, "message": "Empty ledger", "broken_at": None}

        broken_at = None
        for i, txn in enumerate(transactions):
            expected_hash = self.compute_transaction_hash(
                transaction_id=txn["id"],
                user_id=txn["user_id"],
                brand_id=txn["brand_id"],
                transaction_type=txn["transaction_type"],
                amount=txn["amount"],
                balance_after=txn.get("balance_after", 0),
                previous_hash=txn.get("previous_hash", "GENESIS"),
                created_at=str(txn["created_at"]),
            )
            if expected_hash != txn.get("chain_hash"):
                broken_at = i
                break

        return {
            "valid": broken_at is None,
            "total_transactions": len(transactions),
            "broken_at": broken_at,
            "message": "Chain intact" if broken_at is None else f"Chain broken at index {broken_at}",
        }

    def export_ledger_csv(
        self,
        transactions: List[Dict],
        brand_id: int,
    ) -> str:
        """Export credit ledger as CSV."""
        output = io.StringIO()
        fieldnames = [
            "transaction_id", "created_at", "transaction_type",
            "amount", "balance_after", "description",
            "reference_id", "chain_hash", "previous_hash", "status"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for txn in transactions:
            writer.writerow({
                "transaction_id": txn.get("id"),
                "created_at": txn.get("created_at"),
                "transaction_type": txn.get("transaction_type"),
                "amount": txn.get("amount"),
                "balance_after": txn.get("balance_after", ""),
                "description": txn.get("description", ""),
                "reference_id": txn.get("reference_id", ""),
                "chain_hash": txn.get("chain_hash", ""),
                "previous_hash": txn.get("previous_hash", ""),
                "status": txn.get("status", "completed"),
            })

        return output.getvalue()


# Singleton
credit_ledger_service = CreditLedgerService()
