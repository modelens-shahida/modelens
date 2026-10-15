"""Job refunds: every credit refund for a job goes through here, so a job is
refunded at most once however many attempts, retries, cancels, admin actions
or callbacks reach it.

Job credits live in one of two places:

* The user's balance (``users.credits``): ghost, sketch and catalog jobs
  (``credits_reserved`` on the job) and AIJob generation, workflow and
  training jobs (a fixed price). ``refund_job`` refunds these.
* A brand reservation: a ``reserved`` credit_transactions row per generation
  id (ghost batches, FASHN, Rosanne catalog, productions, NestJS callbacks).
  ``lock_reservation`` + ``refund_reservation`` refund these.

Every refund writes one credit_transactions row (``transaction_type`` "refund")
whose ``refund_key`` names what it refunds, e.g. ``ghost_job:12`` or
``generation:gen_abc``. Before writing, the job row (or the reservation row)
and then the balance row are locked with SELECT ... FOR UPDATE, so concurrent
attempts wait for each other, and the refunds already written are checked. The
unique index on ``refund_key`` is the database's own guarantee on top: a second
refund with the same key cannot be committed.

The amount is never more than the job was charged: a job's refunds together
stay within what it reserved minus what it consumed. Nothing here commits; the
caller commits along with its own changes (job status, error message).
"""
from typing import Optional

from sqlalchemy import func, select

from app.models.db import Brand, CreditTransaction, User

REFUND = "refund"


def refund_key(kind: str, ref, part: Optional[str] = None) -> str:
    return f"{kind}:{ref}" + (f":{part}" if part else "")


async def _locked(db, model, *where):
    """The row, locked until the transaction ends and reloaded with its committed values.
    (SQLite ignores FOR UPDATE; it allows one writer at a time anyway.)"""
    stmt = select(model).where(*where).with_for_update().execution_options(populate_existing=True)
    return (await db.execute(stmt)).scalars().first()


async def _already_refunded(db, key: str) -> bool:
    return (await db.execute(
        select(CreditTransaction.id).where(CreditTransaction.refund_key == key))).first() is not None


async def _record(db, *, key: str, amount: int, user_id: int, brand_id: Optional[int], to_brand: bool,
                  reference_type: Optional[str], reference_id: str, description: str) -> Optional[CreditTransaction]:
    """Credit ``amount`` back and write the refund row, unless ``key`` was refunded already.
    The caller holds the lock on the job or reservation row."""
    if amount <= 0 or await _already_refunded(db, key):
        return None
    holder = await _locked(db, Brand, Brand.id == brand_id) if to_brand else await _locked(db, User, User.id == user_id)
    if holder is not None:
        holder.credits = (holder.credits or 0) + amount
    row = CreditTransaction(
        user_id=user_id, brand_id=brand_id, transaction_type=REFUND, amount=amount,
        reference_type=reference_type, reference_id=reference_id, refund_key=key,
        balance_after=holder.credits if holder is not None else 0,
        status="completed", description=description[:500],
    )
    db.add(row)
    await db.flush()
    return row


# ========================== User-balance jobs ======================

async def refunded_so_far(db, kind: str, job_id) -> int:
    return (await db.execute(select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(
        CreditTransaction.transaction_type == REFUND,
        CreditTransaction.reference_type == kind,
        CreditTransaction.reference_id == str(job_id),
    ))).scalar_one()


async def refund_job(db, kind: str, job, reason: str, *, reserved: Optional[int] = None,
                     amount: Optional[int] = None, part: Optional[str] = None) -> int:
    """Refund a job paid from the user's balance, once. Returns the credits refunded (0 if
    it was refunded already or nothing is left to refund).

    kind:     the job type, also the refund rows' reference_type ("ghost_job", "sketch_job",
              "catalog_job", "job" for AIJob).
    reserved: what the job charged; defaults to ``job.credits_reserved``.
    amount:   refund only this much (one catalog item); default: everything still refundable.
    part:     a refund of one part of the job (a catalog item) has its own key, so each part
              is refunded once and all of them together stay within the job's charge.
    """
    await db.flush()  # pending changes to the job are kept; the reload below sees them
    model = type(job)
    locked = await _locked(db, model, model.id == job.id)
    if locked is None:
        return 0
    charged = locked.credits_reserved if reserved is None else reserved
    refundable = (charged or 0) - (getattr(locked, "credits_consumed", 0) or 0) \
        - await refunded_so_far(db, kind, locked.id)
    amount = refundable if amount is None else min(amount, refundable)
    row = await _record(
        db, key=refund_key(kind, locked.id, part), amount=amount, user_id=locked.user_id,
        brand_id=getattr(locked, "brand_id", None), to_brand=False, reference_type=kind,
        reference_id=str(locked.id), description=f"Refund for {kind.replace('_', ' ')} {locked.id}: {reason}",
    )
    return row.amount if row is not None else 0


# ========================== Brand reservations =====================

async def lock_reservation(db, generation_id: str) -> Optional[CreditTransaction]:
    """The generation's pending reservation, locked; None once finalized or refunded."""
    await db.flush()
    return await _locked(db, CreditTransaction, CreditTransaction.reference_id == generation_id,
                         CreditTransaction.status == "pending")


async def refund_reservation(db, reservation: CreditTransaction, reason: str, *, partial: Optional[int] = None,
                             reference_id: Optional[str] = None, description: Optional[str] = None) -> int:
    """Refund a reservation from ``lock_reservation`` to its brand, once. The full refund marks the
    reservation refunded; ``partial`` refunds unused credits of a completed generation (at most
    the reservation). Returns the credits refunded."""
    generation_id = reservation.reference_id
    charged = abs(reservation.amount or 0)
    if partial is None:
        reservation.status = "refunded"
        amount, part, default_ref = charged, None, f"refund_{generation_id}"
    else:
        amount, part, default_ref = min(partial, charged), "partial", generation_id
    row = await _record(
        db, key=refund_key("generation", generation_id, part), amount=amount, user_id=reservation.user_id,
        brand_id=reservation.brand_id, to_brand=True, reference_type=None,
        reference_id=reference_id or default_ref, description=description or f"Auto refund: {reason}",
    )
    return row.amount if row is not None else 0

