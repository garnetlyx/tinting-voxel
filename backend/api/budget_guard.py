"""Server-side backstop for over-budget heavy jobs.

The browser asks the user before submitting an oversized job (via
/api/v2/estimate-job); this guard is the second line of defense for clients
that skip the estimate, refusing the job with a structured 422 that carries
the same suggestion the dialog would have shown. ``forceOversize`` on the
request marks the user's explicit "run it anyway".
"""
import logging

from fastapi import HTTPException

from config.settings import settings
from services.memory_estimate import Reduction
from services.telemetry import emit

logger = logging.getLogger(__name__)

JOB_TOO_LARGE = "job_too_large"


def check_memory_budget(
    kind: str,
    estimated_mb: float,
    suggestion: Reduction | None,
    forced: bool,
) -> None:
    """Emit the estimate verdict and refuse over-budget jobs unless forced."""
    budget_mb = settings.heavy_memory_budget_mb
    over = estimated_mb > budget_mb
    emit(
        "memory_estimate",
        kind=kind,
        estimated_mb=round(estimated_mb),
        budget_mb=round(budget_mb),
        verdict="forced" if over and forced else ("oversize" if over else "ok"),
    )
    if not over or forced:
        return
    detail = {
        "code": JOB_TOO_LARGE,
        "estimatedMb": round(estimated_mb),
        "budgetMb": round(budget_mb),
        "message": (
            f"This job is estimated to need {estimated_mb / 1024:.1f} GB of memory, "
            f"over the {budget_mb / 1024:.1f} GB server budget, and could crash it. "
            "Scale down, or confirm to run it anyway."
        ),
    }
    if suggestion is not None:
        detail["suggestion"] = suggestion.as_dict()
    logger.info(
        "Refusing over-budget job: kind=%s estimated=%.0fMB budget=%.0fMB",
        kind, estimated_mb, budget_mb,
    )
    raise HTTPException(status_code=422, detail=detail)
